from dataclasses import dataclass


@dataclass(slots=True)
class TrackQuery:
    """Source-agnostic 'what to download'."""
    title: str
    artist: str

    @property
    def search_query(self) -> str:
        return f"{self.artist} - {self.title}"


@dataclass(slots=True)
class DownloadedTrack:
    title: str
    artist: str
    duration: int
    youtube_id: str
    file_path: str
