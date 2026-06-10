"""Single entry-point: `python -m app.main {bot|api}`."""
import asyncio
import sys

from app.logging_config import configure_logging


async def init_db() -> None:
    """Create all tables if they don't exist yet."""
    from app.db.base import Base
    from app.db import models  # noqa: ensure models are registered
    from app.db.session import engine
    from sqlalchemy import text

    async with engine.begin() as conn:
        # Run auto-migration for newly added columns if table exists
        try:
            await conn.execute(text("ALTER TABLE tracks ADD COLUMN IF NOT EXISTS telegram_message_id INTEGER"))
            await conn.execute(text("ALTER TABLE tracks ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(5) DEFAULT 'en'"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(32)"))
            
            # Drop obsolete tables
            await conn.execute(text("DROP TABLE IF EXISTS playlist_tracks CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS share_tokens CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS likes CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS playlists CASCADE"))
        except Exception:
            pass
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()


def run_bot() -> None:
    asyncio.get_event_loop().run_until_complete(init_db())
    from app.bot.app import build_application
    app = build_application()
    app.run_polling()


def main() -> None:
    configure_logging()
    mode = sys.argv[1] if len(sys.argv) > 1 else "bot"
    if mode == "bot":
        run_bot()
    else:
        raise SystemExit(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
