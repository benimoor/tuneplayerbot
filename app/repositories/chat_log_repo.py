from datetime import datetime, timedelta
import os
import logging
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ChatLog

logger = logging.getLogger(__name__)


def _write_to_local_file(user_id: int, username: str | None, phone: str | None, message: str):
    try:
        os.makedirs("storage", exist_ok=True)
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        username_str = f"@{username}" if username else "no_nickname"
        phone_str = phone if phone else "no_phone"
        # Escape newlines in message to keep log lines 1-to-1
        escaped_message = message.replace("\n", " [NL] ")
        line = f"[{ts}] ID: {user_id} | {username_str} | Phone: {phone_str} | Msg: {escaped_message}\n"
        with open("storage/request.log", "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        logger.warning("Failed to write to request.log: %s", e)


async def add_log(
    session: AsyncSession,
    user_id: int,
    username: str | None,
    phone: str | None,
    message: str,
) -> ChatLog:
    log = ChatLog(
        user_id=user_id,
        username=username,
        phone=phone,
        message=message,
    )
    session.add(log)
    await session.commit()

    # Write to local log file as well
    _write_to_local_file(user_id, username, phone, message)

    return log


async def prune_logs(session: AsyncSession) -> int:
    """Delete logs older than 7 days."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    res = await session.execute(
        delete(ChatLog).where(ChatLog.created_at < cutoff)
    )
    await session.commit()
    return res.rowcount


async def get_recent_logs(session: AsyncSession, limit: int = 100) -> list[ChatLog]:
    """Retrieve recent chat logs, ordered by created_at desc."""
    res = await session.execute(
        select(ChatLog).order_by(ChatLog.created_at.desc()).limit(limit)
    )
    return list(res.scalars())
