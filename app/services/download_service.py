import asyncio
import logging
import re
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import track_repo
from app.services import youtube_service
from app.services.resolver import ResolveResult, resolve
from app.services.types import DownloadedTrack

log = logging.getLogger(__name__)
_SEM = asyncio.Semaphore(2)  # at most 2 parallel downloads per process


def extract_youtube_id(url: str) -> str | None:
    match = re.search(r"(?:v=|\/shorts\/|\/embed\/|\/v\/|youtu\.be\/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None


async def _download_one(session: AsyncSession, dt: DownloadedTrack):
    return await track_repo.upsert(
        session,
        title=dt.title, artist=dt.artist, duration=dt.duration,
        youtube_id=dt.youtube_id, file_path=dt.file_path,
    )


async def process(url: str, session: AsyncSession) -> AsyncIterator:
    """Yields persisted Track rows as they are downloaded."""
    rr: ResolveResult = await resolve(url)

    # YouTube direct URL → single download by URL
    if rr.source == "youtube" and not rr.is_playlist and rr.youtube_url:
        youtube_id = extract_youtube_id(rr.youtube_url)
        if youtube_id:
            track = await track_repo.get_by_youtube_id(session, youtube_id)
            if track and track.telegram_file_id:
                yield track
                return

        async with _SEM:
            dt = await youtube_service.download_url(rr.youtube_url)
        yield await _download_one(session, dt)
        return

    # Otherwise iterate queries (Spotify/Yandex/YouTube playlist)
    for q in rr.queries:
        try:
            async with _SEM:
                dt = await youtube_service.download_query(q)
            yield await _download_one(session, dt)
        except Exception:
            log.exception("Failed to download %s", q.search_query)
