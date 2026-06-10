"""Spotify metadata scraper — NO account required.

Extracts track name and artist from Spotify URLs by:
1. Using yt-dlp to extract metadata (it supports Spotify URLs for metadata).
2. Falling back to scraping the page's OpenGraph / meta tags via httpx + BeautifulSoup.

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

_TRACK_RE = re.compile(r"open\.spotify\.com/(?:intl-[a-z]+/)?track/([A-Za-z0-9]+)")
_PLAYLIST_RE = re.compile(r"open\.spotify\.com/(?:intl-[a-z]+/)?playlist/([A-Za-z0-9]+)")
_ALBUM_RE = re.compile(r"open\.spotify\.com/(?:intl-[a-z]+/)?album/([A-Za-z0-9]+)")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_title_artist(og_title: str) -> TrackQuery:
    """Parse an OpenGraph title like 'Song Name - song and target by Artist Name | Spotify'
    or 'Song Name · Artist Name' into a TrackQuery."""
    # Remove trailing " | Spotify" or " - Spotify" etc.
    cleaned = re.sub(r"\s*[\|–—-]\s*Spotify\s*$", "", og_title, flags=re.I).strip()

    # Try "Artist - Title" or "Title · Artist" patterns
    for sep in [" · ", " - song and lyrics by ", " - Song by ", " - song by "]:
        if sep in cleaned:
            parts = cleaned.split(sep, 1)
            if sep == " · ":
                return TrackQuery(title=parts[0].strip(), artist=parts[1].strip())
            else:
                return TrackQuery(title=parts[0].strip(), artist=parts[1].strip())

    # Try "Title - Artist"
    if " - " in cleaned:
        parts = cleaned.split(" - ", 1)
        return TrackQuery(title=parts[0].strip(), artist=parts[1].strip())

    return TrackQuery(title=cleaned, artist="")


async def _scrape_single(url: str) -> TrackQuery:
    """Scrape a single Spotify track URL for title + artist metadata."""
    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Try og:title meta tag first (most reliable)
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")

    title = ""
    artist = ""

    if og_title and og_title.get("content"):
        title = og_title["content"].strip()

    if og_desc and og_desc.get("content"):
        desc = og_desc["content"].strip()
        # Description is usually like "Song · Artist · Album · 2024"
        # or "Listen to Title on Spotify. Artist · Album · 2024"
        desc_clean = re.sub(r"^Listen to .+ on Spotify\.\s*", "", desc)
        parts = [p.strip() for p in desc_clean.split("·")]
        if parts:
            artist = parts[0]

    # Fallback: try the <title> tag
    if not title and soup.title:
        return _parse_title_artist(soup.title.string or "")

    if title and artist:
        return TrackQuery(title=title, artist=artist)

    if title:
        return _parse_title_artist(title)

    raise ValueError(f"Could not extract metadata from Spotify URL: {url}")


async def _scrape_playlist_or_album(url: str) -> list[TrackQuery]:
    """Scrape a Spotify playlist/album page.

    Spotify embeds track listing in JSON-LD and meta tags. We also try
    the Spotify embed endpoint which returns JSON with track info.
    """
    # Try the embed API (works for playlists and albums without auth)
    embed_url = url.replace("open.spotify.com/", "open.spotify.com/embed/")

    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=20) as client:
        resp = await client.get(embed_url)

    tracks: list[TrackQuery] = []

    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for JSON data in script tags
        for script in soup.find_all("script"):
            text = script.string or ""
            if "track" in text.lower() and ("name" in text or "title" in text):
                try:
                    # Try to parse any JSON blobs with track data
                    for match in re.finditer(r'\{[^{}]*"name"\s*:\s*"[^"]+?"[^{}]*\}', text):
                        try:
                            data = json.loads(match.group())
                            if "name" in data:
                                t = TrackQuery(
                                    title=data.get("name", ""),
                                    artist=data.get("artist", data.get("artists", "")),
                                )
                                if t.title:
                                    tracks.append(t)
                        except (json.JSONDecodeError, KeyError):
                            continue
                except Exception:
                    continue

    # Fallback: scrape the regular page for og:title to get at least the playlist name
    if not tracks:
        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Try to find track listing from meta tags or structured data
        og_title = soup.find("meta", property="og:title")
        og_desc = soup.find("meta", property="og:description")

        if og_desc and og_desc.get("content"):
            desc = og_desc["content"]
            # Playlist descriptions often list tracks like:
            # "Playlist · User · 2024 · 50 songs" or list track names
            # Try extracting track-like patterns
            # Sometimes the description lists artist/song names
            lines = [l.strip() for l in desc.replace("·", "\n").split("\n") if l.strip()]
            for line in lines:
                if line and not re.match(r"^\d+\s*(songs?|tracks?)", line, re.I) and len(line) > 2:
                    # Could be "Artist - Title" or just a name
                    if " - " in line:
                        parts = line.split(" - ", 1)
                        tracks.append(TrackQuery(title=parts[1].strip(), artist=parts[0].strip()))
                    elif not re.match(r"^\d{4}$", line):  # Skip year entries
                        tracks.append(TrackQuery(title=line, artist=""))

        # If we still have nothing, use the playlist title as a search query
        if not tracks and og_title and og_title.get("content"):
            tracks.append(TrackQuery(title=og_title["content"], artist="playlist"))

    return tracks


async def resolve(url: str) -> list[TrackQuery]:
    """Resolve a Spotify URL to track queries (no account needed)."""
    if _TRACK_RE.search(url):
        q = await _scrape_single(url)
        log.info("Spotify track resolved: %s", q.search_query)
        return [q]

    if _PLAYLIST_RE.search(url) or _ALBUM_RE.search(url):
        qs = await _scrape_playlist_or_album(url)
        log.info("Spotify playlist/album resolved: %d tracks", len(qs))
        return qs

    raise ValueError("Unrecognized Spotify URL")
