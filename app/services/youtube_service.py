import asyncio
import logging
import uuid
from pathlib import Path

import yt_dlp

from app.config import settings
from app.services.types import DownloadedTrack, TrackQuery

log = logging.getLogger(__name__)

_YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noprogress": True,
    "restrictfilenames": True,
    "noplaylist": True,
    "remote_components": ["ejs:github"],
    "postprocessors": [
        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
        {"key": "FFmpegMetadata"},
        {"key": "EmbedThumbnail"},
    ],
    "writethumbnail": True,
}


def _download(url_or_search: str) -> DownloadedTrack:
    outtmpl = str(settings.download_dir / f"%(id)s-{uuid.uuid4().hex[:8]}.%(ext)s")
    opts = {
        **_YDL_OPTS,
        "outtmpl": outtmpl,
        "max_filesize": settings.max_filesize_mb * 1024 * 1024,
    }
    
    # Enable cookies if present in storage to download restricted/age-restricted videos
    cookie_file = Path("storage/cookies.txt")
    if cookie_file.exists():
        opts["cookiefile"] = str(cookie_file)
        log.info("Using cookies.txt from storage for yt-dlp download")

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url_or_search, download=True)
        # ytsearch returns a playlist-like result
        if info.get("_type") == "playlist" and info.get("entries"):
            info = info["entries"][0]
        base = ydl.prepare_filename(info)
        mp3_path = Path(base).with_suffix(".mp3")
        return DownloadedTrack(
            title=info.get("title") or "",
            artist=info.get("uploader") or "",
            duration=int(info.get("duration") or 0),
            youtube_id=info["id"],
            file_path=str(mp3_path),
        )


def _extract_playlist(url: str) -> list[TrackQuery]:
    opts = {"quiet": True, "extract_flat": True, "skip_download": True}
    
    cookie_file = Path("storage/cookies.txt")
    if cookie_file.exists():
        opts["cookiefile"] = str(cookie_file)
        log.info("Using cookies.txt from storage for playlist extraction")

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = info.get("entries") or []
    return [
        TrackQuery(title=e.get("title") or "", artist=e.get("uploader") or "")
        for e in entries if e.get("title")
    ]


async def download_query(query: TrackQuery) -> DownloadedTrack:
    """Search YouTube by 'artist - title' and download the top result as MP3."""
    return await asyncio.to_thread(_download, f"ytsearch1:{query.search_query}")


async def download_url(url: str) -> DownloadedTrack:
    return await asyncio.to_thread(_download, url)


async def list_playlist(url: str) -> list[TrackQuery]:
    return await asyncio.to_thread(_extract_playlist, url)
