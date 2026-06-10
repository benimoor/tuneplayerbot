"""ARQ worker settings for background task processing."""
import asyncio
import logging

from arq.connections import RedisSettings

from app.config import settings

log = logging.getLogger(__name__)


async def download_task(ctx, url: str, telegram_id: int):
    """Background download task for long playlists."""
    from app.db.session import AsyncSessionLocal
    from app.services.download_service import process
    from app.repositories import user_repo

    async with AsyncSessionLocal() as session:
        user = await user_repo.get_or_create(session, telegram_id, None)
        results = []
        async for track in process(url, session):
            results.append(track)
            log.info("Downloaded: %s - %s", track.artist, track.title)
    return {"count": len(results)}


class WorkerSettings:
    functions = [download_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
