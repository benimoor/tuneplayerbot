"""Yandex Music metadata scraper — NO account required.

Extracts track name and artist from Yandex Music URLs by scraping
the page's meta tags (og:title, og:description) via httpx + BeautifulSoup.

The extracted {title, artist} is then searched on YouTube for the actual download.
"""
import asyncio
import json
import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.services.types import TrackQuery

log = logging.getLogger(__name__)

_TRACK_RE = re.compile(r"music\.yandex\.[a-z]+/album/(\d+)/track/(\d+)")
_ALBUM_RE = re.compile(r"music\.yandex\.[a-z]+/album/(\d+)(?!/track)")
_PLAYLIST_RE = re.compile(r"music\.yandex\.[a-z]+/users/([^/]+)/playlists/(\d+)")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
}


def _parse_yandex_title(og_title: str) -> TrackQuery:
    """Parse Yandex Music og:title like 'Song Name — Artist Name' or
    'Artist Name — Song Name. Listen online on Yandex Music'."""
    # Remove common suffixes
    cleaned = re.sub(
        r"\s*[\.\-–—]\s*(Слушайте|Listen|Яндекс|Yandex).*$", "", og_title, flags=re.I
    ).strip()

    # Try "Title — Artist" or "Artist — Title" (Yandex uses em-dash)
    for sep in [" — ", " – ", " - "]:
        if sep in cleaned:
            parts = cleaned.split(sep, 1)
            # Heuristic: in Yandex, track pages are usually "Artist — Title"
            return TrackQuery(title=parts[1].strip(), artist=parts[0].strip())

    return TrackQuery(title=cleaned, artist="")


async def _scrape_single(url: str) -> TrackQuery:
    """Scrape a single Yandex Music track URL for metadata."""
    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Try og:title
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return _parse_yandex_title(og_title["content"])

    # Try <title> tag
    if soup.title and soup.title.string:
        return _parse_yandex_title(soup.title.string)

    # Try JSON-LD structured data
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and data.get("name"):
                artist = ""
                if "byArtist" in data:
                    ba = data["byArtist"]
                    if isinstance(ba, dict):
                        artist = ba.get("name", "")
                    elif isinstance(ba, list):
                        artist = ", ".join(a.get("name", "") for a in ba)
                return TrackQuery(title=data["name"], artist=artist)
        except (json.JSONDecodeError, KeyError):
            continue

    raise ValueError(f"Could not extract metadata from Yandex URL: {url}")


async def _scrape_album_or_playlist(url: str) -> list[TrackQuery]:
    """Scrape a Yandex Music album/playlist page for track listing."""
    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=20) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    tracks: list[TrackQuery] = []

    # Try JSON-LD structured data (MusicAlbum or MusicPlaylist)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                track_list = None

                # MusicAlbum schema
                if data.get("@type") == "MusicAlbum" and "track" in data:
                    track_obj = data["track"]
                    if isinstance(track_obj, dict) and "itemListElement" in track_obj:
                        track_list = track_obj["itemListElement"]
                    elif isinstance(track_obj, list):
                        track_list = track_obj

                # MusicPlaylist schema
                if data.get("@type") == "MusicPlaylist" and "track" in data:
                    track_obj = data["track"]
                    if isinstance(track_obj, dict) and "itemListElement" in track_obj:
                        track_list = track_obj["itemListElement"]

                if track_list:
                    for item in track_list:
                        track_data = item.get("item", item) if isinstance(item, dict) else item
                        if isinstance(track_data, dict) and track_data.get("name"):
                            artist = ""
                            if "byArtist" in track_data:
                                ba = track_data["byArtist"]
                                if isinstance(ba, dict):
                                    artist = ba.get("name", "")
                                elif isinstance(ba, list):
                                    artist = ", ".join(a.get("name", "") for a in ba)
                            tracks.append(TrackQuery(title=track_data["name"], artist=artist))

        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    # Fallback: try og:description for track names
    if not tracks:
        og_desc = soup.find("meta", property="og:description")
        og_title = soup.find("meta", property="og:title")

        if og_desc and og_desc.get("content"):
            desc = og_desc["content"]
            # Yandex descriptions sometimes list tracks
            lines = [l.strip() for l in desc.split(",") if l.strip()]
            for line in lines:
                if len(line) > 2 and not re.match(r"^\d+\s", line):
                    tracks.append(TrackQuery(title=line, artist=""))

        # Last resort: use album/playlist title
        if not tracks and og_title and og_title.get("content"):
            title = re.sub(r"\s*[\-–—]\s*(Слушайте|Listen).*$", "", og_title["content"], flags=re.I)
            tracks.append(TrackQuery(title=title.strip(), artist=""))

    return tracks


async def resolve(url: str) -> list[TrackQuery]:
    """Resolve a Yandex Music URL to track queries (no account needed)."""
    if _TRACK_RE.search(url):
        q = await _scrape_single(url)
        log.info("Yandex track resolved: %s", q.search_query)
        return [q]

    if _ALBUM_RE.search(url) or _PLAYLIST_RE.search(url):
        qs = await _scrape_album_or_playlist(url)
        log.info("Yandex album/playlist resolved: %d tracks", len(qs))
        return qs

    raise ValueError("Unrecognized Yandex Music URL")
