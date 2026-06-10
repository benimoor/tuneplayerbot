from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import ContextTypes
from app.bot.utils import ensure_user, db
from app.bot.translations import get_text


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await ensure_user(u.id, u.username)

    # Prompt language selection
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇦🇲 հայերեն", callback_data="lang:hy"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
        ]
    ])
    
    welcome_text = (
        "Welcome to Tunebot! 🎵\n"
        "Բարի գալուստ Tunebot: 🎵\n"
        "Добро пожаловать в Tunebot! 🎵\n\n"
        "Please select your language / Խնդրում ենք ընտրել լեզուն / Пожалуйста, выберите язык:"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=keyboard)


async def set_language_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    data = q.data or ""
    lang = data.split(":")[1]
    u = update.effective_user
    
    async with db() as s:
        from sqlalchemy import update as sql_update
        from app.db.models import User
        await s.execute(
            sql_update(User)
            .where(User.telegram_id == u.id)
            .values(language=lang)
        )
        await s.commit()

    # Inform language choice and welcome the user
    welcome_text = get_text(lang, "welcome")
    await q.edit_message_text(welcome_text, parse_mode="Markdown")


async def handle_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if not contact:
        return
    
    u = update.effective_user
    phone = contact.phone_number
    
    async with db() as s:
        from sqlalchemy import update as sql_update
        from app.db.models import User
        from sqlalchemy import select
        res = await s.execute(select(User).where(User.telegram_id == u.id))
        user = res.scalar_one_or_none()
        lang = user.language if user else "en"
        
        await s.execute(
            sql_update(User)
            .where(User.telegram_id == u.id)
            .values(phone=phone)
        )
        await s.commit()
        
    thanks_text = get_text(lang, "phone_saved")
    await update.message.reply_text(thanks_text, reply_markup=ReplyKeyboardRemove())


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    async with db() as s:
        from sqlalchemy import select
        from app.db.models import User
        res = await s.execute(select(User).where(User.telegram_id == u.id))
        user = res.scalar_one_or_none()
        lang = user.language if user else "en"
        
    await update.message.reply_text(get_text(lang, "help"), parse_mode="Markdown")
