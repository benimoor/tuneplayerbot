import logging
import html
import os
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from app.config import settings
from app.bot.utils import db
from app.repositories import chat_log_repo

log = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in settings.admins


async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u.id):
        return  # Silently ignore non-admins
    
    async with db() as s:
        from sqlalchemy import select, func
        from app.db.models import User, ChatLog
        total_users = (await s.execute(select(func.count(User.id)))).scalar_one()
        total_logs = (await s.execute(select(func.count(ChatLog.id)))).scalar_one()
        
    text = (
        "🛠 <b>Admin Control Panel</b> 🛠\n\n"
        "📊 <b>Statistics:</b>\n"
        f"👥 Total Registered Users: <code>{total_users}</code>\n"
        f"📝 Active Chat Logs (last 7 days): <code>{total_logs}</code>\n\n"
        "📜 <b>Available Commands & Examples:</b>\n\n"
        "📢 <b>Broadcast to all users:</b>\n"
        "• <code>/broadcast &lt;message&gt;</code>\n"
        "  <i>Example:</i> <code>/broadcast 📣 Downloader updated! Enjoy music! 🎵</code>\n\n"
        "👤 <b>Send direct message to user:</b>\n"
        "• <code>/send &lt;user_id&gt; &lt;message&gt;</code>\n"
        "  <i>Example:</i> <code>/send 567390667 Hello from support! 👋 How can we help?</code>\n\n"
        "📋 <b>View audit logs & download log file:</b>\n"
        "• <code>/logs</code>\n"
    )
    await update.message.reply_html(text)


async def broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u.id):
        return
    
    # Extract message
    if not ctx.args:
        await update.message.reply_html("❌ Usage: <code>/broadcast &lt;text&gt;</code>")
        return
        
    broadcast_msg = " ".join(ctx.args)
    
    async with db() as s:
        from sqlalchemy import select
        from app.db.models import User
        res = await s.execute(select(User))
        users = list(res.scalars())
        
    status_msg = await update.message.reply_text(f"📢 Starting broadcast to {len(users)} users...")
    
    success = 0
    fail = 0
    for user in users:
        try:
            await ctx.bot.send_message(chat_id=user.telegram_id, text=broadcast_msg)
            success += 1
        except Exception as e:
            log.warning(f"Failed to send broadcast to {user.telegram_id}: {e}")
            fail += 1
            
    await status_msg.edit_text(
        f"📢 <b>Broadcast Complete</b>\n\n"
        f"• Successfully sent: <code>{success}</code>\n"
        f"• Failed/Blocked: <code>{fail}</code>",
        parse_mode="HTML"
    )


async def send_direct(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u.id):
        return
        
    if len(ctx.args) < 2:
        await update.message.reply_html("❌ Usage: <code>/send &lt;user_id&gt; &lt;text&gt;</code>")
        return
        
    user_id_str = ctx.args[0]
    direct_msg = " ".join(ctx.args[1:])
    
    try:
        target_user_id = int(user_id_str)
    except ValueError:
        await update.message.reply_html("❌ Invalid user ID. Must be an integer.")
        return
        
    try:
        await ctx.bot.send_message(chat_id=target_user_id, text=direct_msg)
        await update.message.reply_html(f"✅ Message successfully sent to <code>{target_user_id}</code>!")
    except Exception as e:
        await update.message.reply_html(f"❌ Failed to send message to <code>{target_user_id}</code>: {html.escape(str(e))}")


async def view_logs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u.id):
        return
        
    async with db() as s:
        logs = await chat_log_repo.get_recent_logs(s, limit=30)
        
    if not logs:
        await update.message.reply_text("📋 No chat logs found in the last 7 days.")
    else:
        lines = ["📋 <b>Recent Chat Logs (Last 7 Days)</b>\n"]
        for log_entry in logs:
            ts = log_entry.created_at.strftime("%Y-%m-%d %H:%M")
            username = f"@{html.escape(log_entry.username)}" if log_entry.username else "no_nickname"
            phone = html.escape(log_entry.phone) if log_entry.phone else "no_phone"
            escaped_msg = html.escape(log_entry.message)
            
            line = (
                f"👤 <b>{log_entry.user_id}</b> ({username}) | {phone}\n"
                f"💬 <code>{escaped_msg}</code>\n"
                f"🕒 {ts}\n"
                f"───────────────────"
            )
            lines.append(line)
            
        message_text = ""
        for line in lines:
            if len(message_text) + len(line) + 2 > 4000:
                await update.message.reply_html(message_text)
                message_text = ""
            message_text += line + "\n"
            
        if message_text:
            await update.message.reply_html(message_text)

    # Also send the request.log file if it exists
    log_path = "storage/request.log"
    if os.path.exists(log_path):
        try:
            with open(log_path, "rb") as f:
                await ctx.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=InputFile(f, filename="request.log"),
                    caption="📂 Complete local request.log file"
                )
        except Exception as e:
            log.warning("Failed to send request.log file: %s", e)
