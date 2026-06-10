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

    # 1. First make sure all latest tables are created if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Run alter columns in individual transactions so a failure in one doesn't abort others
    alter_statements = [
        "ALTER TABLE tracks ADD COLUMN IF NOT EXISTS telegram_message_id INTEGER",
        "ALTER TABLE tracks ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(5) DEFAULT 'en'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(32)",
        "DROP TABLE IF EXISTS playlist_tracks CASCADE",
        "DROP TABLE IF EXISTS share_tokens CASCADE",
        "DROP TABLE IF EXISTS likes CASCADE",
        "DROP TABLE IF EXISTS playlists CASCADE",
    ]

    for stmt in alter_statements:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Migration statement failed: %s. Error: %s", stmt, e)
    
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
