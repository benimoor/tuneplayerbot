from contextlib import asynccontextmanager
from app.db.session import AsyncSessionLocal
from app.repositories import user_repo


@asynccontextmanager
async def db():
    async with AsyncSessionLocal() as session:
        yield session


async def ensure_user(telegram_id: int, username: str | None):
    async with db() as s:
        return await user_repo.get_or_create(s, telegram_id, username)
