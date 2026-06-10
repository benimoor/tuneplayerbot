from telegram import Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters,
)

from app.config import settings
from app.bot.handlers.start import start, help_cmd, set_language_callback, handle_contact
from app.bot.handlers.url import handle_text
from app.bot.handlers.admin import admin_panel, broadcast, send_direct, view_logs


async def post_init(application: Application) -> None:
    from telegram import MenuButtonDefault
    import logging
    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonDefault()
        )
        logging.getLogger(__name__).info("Successfully reset Menu Button to default")
    except Exception as e:
        logging.getLogger(__name__).warning("Failed to reset Menu Button: %s", e)


def build_application() -> Application:
    app = Application.builder().token(settings.bot_token).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("send", send_direct))
    app.add_handler(CommandHandler("logs", view_logs))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^lang:"))

    # Contact sharing handler
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))

    # All text messages (URLs + fallback)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app
