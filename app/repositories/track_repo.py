from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Track


async def get_by_youtube_id(session: AsyncSession, youtube_id: str) -> Track | None:
    res = await session.execute(select(Track).where(Track.youtube_id == youtube_id))
    return res.scalar_one_or_none()


async def upsert(session: AsyncSession, *, title: str, artist: str, duration: int,
                 youtube_id: str, file_path: str) -> Track:
    track = await get_by_youtube_id(session, youtube_id)
    if track:
        track.file_path = file_path
        track.title = title
        track.artist = artist
        track.duration = duration
    else:
        track = Track(title=title, artist=artist, duration=duration,
                      youtube_id=youtube_id, file_path=file_path)
        session.add(track)
    await session.commit()
    return track
