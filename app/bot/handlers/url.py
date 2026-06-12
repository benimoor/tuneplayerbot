import logging
import re

from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from app.bot.utils import db, ensure_user
from app.bot.translations import get_text
from app.services.download_service import process
from app.repositories import chat_log_repo

log = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://\S+", re.I)


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = (msg.text or "").strip()
    user = await ensure_user(update.effective_user.id, update.effective_user.username)
    lang = user.language if user else "en"
    phone = user.phone if user else None

    # Log user message
    async with db() as session:
        await chat_log_repo.add_log(
            session,
            user_id=update.effective_user.id,
            username=update.effective_user.username,
            phone=phone,
            message=text
        )
        # Prune logs older than 7 days on every incoming message
        try:
            await chat_log_repo.prune_logs(session)
        except Exception:
            log.exception("failed to prune chat logs")

    # ── URL download ──────────────────────────────────────────────
    url_match = _URL_RE.search(text)
    if url_match:
        url = url_match.group(0)
        status = await msg.reply_text(get_text(lang, "downloading"))
        count = 0
        async with db() as session:
            try:
                async for track in process(url, session):
                    count += 1
                    await ctx.bot.send_chat_action(msg.chat_id, ChatAction.UPLOAD_AUDIO)
                    
                    msg_sent = None
                    if track.telegram_file_id:
                        try:
                            msg_sent = await ctx.bot.send_audio(
                                chat_id=msg.chat_id,
                                audio=track.telegram_file_id,
                                caption=f"🎧 {track.artist} — {track.title}",
                                reply_markup=None,
                            )
                        except Exception:
                            log.warning("Failed to send track via file_id: %s", track.telegram_file_id)
                            track.telegram_file_id = None
                            await session.commit()
                            pass
                    
                    if not msg_sent:
                        import os
                        # If file is not present locally on disk, perform a fresh download
                        if not track.file_path or not os.path.exists(track.file_path):
                            log.info("File not found on disk, performing fresh download for youtube_id: %s", track.youtube_id)
                            try:
                                from app.services import youtube_service
                                dt = await youtube_service.download_url(f"https://www.youtube.com/watch?v={track.youtube_id}")
                                track.file_path = dt.file_path
                                await session.commit()
                            except Exception:
                                log.exception("Failed to re-download track %s", track.youtube_id)

                        if track.file_path and os.path.exists(track.file_path):
                            with open(track.file_path, "rb") as fh:
                                msg_sent = await ctx.bot.send_audio(
                                    chat_id=msg.chat_id,
                                    audio=InputFile(fh, filename=f"{track.title}.mp3"),
                                    title=track.title,
                                    performer=track.artist,
                                    duration=track.duration or 0,
                                    caption=f"🎧 {track.artist} — {track.title}",
                                    reply_markup=None,
                                )
                            if msg_sent and msg_sent.audio:
                                track.telegram_file_id = msg_sent.audio.file_id
                                await session.commit()
                    
                    import os
                    if track.file_path and os.path.exists(track.file_path):
                        try:
                            os.remove(track.file_path)
                            log.info("Deleted local downloaded file: %s", track.file_path)
                        except Exception as e:
                            log.warning("Failed to delete local file %s: %s", track.file_path, e)
            except ValueError as e:
                await status.edit_text(f"❌ {e}")
                return
            except Exception:
                log.exception("download failed")
                await status.edit_text(get_text(lang, "failed"))
                return

        if count == 0:
            await status.edit_text(get_text(lang, "not_found"))
        else:
            try:
                await status.delete()
            except Exception:
                pass
        return

    # ── Fallback ──────────────────────────────────────────────────
    await msg.reply_text(get_text(lang, "help"), parse_mode="Markdown")
