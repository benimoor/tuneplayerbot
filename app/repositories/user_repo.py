from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User


async def get_or_create(session: AsyncSession, telegram_id: int, username: str | None) -> User:
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = res.scalar_one_or_none()
    if user:
        if user.username != username:
            user.username = username
            await session.commit()
        return user
    user = User(telegram_id=telegram_id, username=username)
    session.add(user)
    await session.commit()
    return user
