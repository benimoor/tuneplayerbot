"""Dispatches a URL to the correct source service.

Returns a list of TrackQuery objects (title + artist). The YouTube service
then searches each one and downloads from YouTube.
"""
import re
from dataclasses import dataclass

from app.services import spotify_service, yandex_service, youtube_service
from app.services.types import TrackQuery

_PATTERNS = {
    "youtube": re.compile(r"(youtube\.com|youtu\.be|music\.youtube\.com)", re.I),
    "spotify": re.compile(r"open\.spotify\.com", re.I),
    "yandex": re.compile(r"music\.yandex\.", re.I),
}


@dataclass(slots=True)
class ResolveResult:
    source: str            # "youtube" | "spotify" | "yandex"
    queries: list[TrackQuery]
    is_playlist: bool
    youtube_url: str | None = None  # direct URL when source == "youtube"


async def resolve(url: str) -> ResolveResult:
    if _PATTERNS["spotify"].search(url):
        qs = await spotify_service.resolve(url)
        return ResolveResult("spotify", qs, is_playlist=len(qs) > 1)
    if _PATTERNS["yandex"].search(url):
        qs = await yandex_service.resolve(url)
        return ResolveResult("yandex", qs, is_playlist=len(qs) > 1)
    if _PATTERNS["youtube"].search(url):
        is_playlist = "list=" in url and "watch?v=" not in url.split("?")[0]
        if is_playlist or "playlist?list=" in url:
            qs = await youtube_service.list_playlist(url)
            return ResolveResult("youtube", qs, is_playlist=True, youtube_url=url)
        return ResolveResult("youtube", [], is_playlist=False, youtube_url=url)
    raise ValueError("Unsupported URL")
