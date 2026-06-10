"""All inline keyboard layouts for the bot."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from app.config import settings


# ── Main menu ──────────────────────────────────────────────────────────
def main_menu() -> InlineKeyboardMarkup:
    web_app_url = settings.api_public_url or "http://localhost:8000"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Open Player", web_app=WebAppInfo(url=web_app_url))
        ],
        [
            InlineKeyboardButton("🎵 My Playlists", callback_data="m:pl"),
            InlineKeyboardButton("❤️ Liked Songs", callback_data="m:lk"),
        ],
        [
            InlineKeyboardButton("🎲 Random Track", callback_data="rc"),
            InlineKeyboardButton("ℹ️ Help", callback_data="m:help"),
        ],
    ])


# ── Player controls (shown under each sent audio) ─────────────────────
def player(track_id: int, liked: bool, playlist_id: int | None = None, index: int = 0) -> InlineKeyboardMarkup:
    """Player with prev/next/random + like/playlist/share."""
    nav_row = []
    if playlist_id is not None:
        nav_row = [
            InlineKeyboardButton("⏮ Prev", callback_data=f"pn:{playlist_id}:{index}:p"),
            InlineKeyboardButton("🔀 Random", callback_data=f"pn:{playlist_id}:0:r"),
            InlineKeyboardButton("⏭ Next", callback_data=f"pn:{playlist_id}:{index}:n"),
        ]
    else:
        nav_row = [
            InlineKeyboardButton("🔀 Random", callback_data="rc"),
        ]

    action_row = [
        InlineKeyboardButton("❤️ Liked" if liked else "🖤 Like", callback_data=f"lk:{track_id}:{playlist_id or ''}"),
        InlineKeyboardButton("➕ Playlist", callback_data=f"ap:{track_id}"),
        InlineKeyboardButton("🔗 Share", callback_data=f"sh:{track_id}"),
    ]

    return InlineKeyboardMarkup([nav_row, action_row])


# ── Track info card (shown when clicking a song in playlist) ──────────
def track_info(track, liked: bool, playlist_id: int, index: int, bot_username: str, is_liked_playlist: bool = False, current_chat_id: int | None = None) -> InlineKeyboardMarkup:
    """Track info view with direct jump-link to the original message instead of a Send Audio button."""
    from app.config import settings
    chat_id = track.telegram_chat_id
    msg_id = track.telegram_message_id
    
    rows = []
    
    if chat_id and msg_id and (current_chat_id is None or chat_id == current_chat_id):
        chat_id_str = str(chat_id)
        if chat_id_str.startswith("-100"):
            stripped = chat_id_str.removeprefix("-100")
            jump_url = f"https://t.me/c/{stripped}/{msg_id}"
            rows.append([
                InlineKeyboardButton("🎧 Go to track", url=jump_url),
            ])
        elif chat_id_str.startswith("-"):
            stripped = chat_id_str.removeprefix("-")
            jump_url = f"https://t.me/c/{stripped}/{msg_id}"
            rows.append([
                InlineKeyboardButton("🎧 Go to track", url=jump_url),
            ])
        else:
            bot_id = settings.bot_token.split(":")[0]
            jump_url = f"tg://openmessage?user_id={bot_id}&message_id={msg_id}"
            rows.append([
                InlineKeyboardButton("🎧 Go to track", url=jump_url),
                InlineKeyboardButton("▶️ Send Audio", callback_data=f"sa:{playlist_id}:{index}"),
            ])
    else:
        # Untracked/Legacy track: let them explicitly request it
        rows.append([
            InlineKeyboardButton("📤 Send to Chat", callback_data=f"sa:{playlist_id}:{index}"),
        ])

    rows.extend([
        [
            InlineKeyboardButton("⏮ Prev", callback_data=f"ti:{playlist_id}:{index}:p"),
            InlineKeyboardButton("🔀 Random", callback_data=f"ti:{playlist_id}:{index}:r"),
            InlineKeyboardButton("⏭ Next", callback_data=f"ti:{playlist_id}:{index}:n"),
        ],
        [
            InlineKeyboardButton("❤️ Liked" if liked else "🖤 Like", callback_data=f"lk:{track.id}:{playlist_id}"),
            InlineKeyboardButton("➕ Playlist", callback_data=f"ap:{track.id}"),
        ],
        [
            InlineKeyboardButton("❌ Remove from Playlist", callback_data=f"pr:{playlist_id}:{track.id}"),
        ]
    ])

    rows.append([
        InlineKeyboardButton("◀️ Back to playlist", callback_data=f"po:{playlist_id}:0"),
        InlineKeyboardButton("🏠 Menu", callback_data="m:home"),
    ])

    return InlineKeyboardMarkup(rows)


# ── Playlist list ──────────────────────────────────────────────────────
def playlist_list(playlists, page: int = 0, page_size: int = 5) -> InlineKeyboardMarkup:
    """List of playlists as buttons + create/back controls."""
    start = page * page_size
    end = start + page_size
    page_items = playlists[start:end]

    rows = []
    for p in page_items:
        label = f"{'❤️ ' if p.is_liked else '📁 '}{p.name}"
        rows.append([
            InlineKeyboardButton(label, callback_data=f"po:{p.id}:0"),
            InlineKeyboardButton("🗑", callback_data=f"pd:{p.id}"),
        ])

    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"pp:{page - 1}"))
    if end < len(playlists):
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"pp:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton("➕ Create Playlist", callback_data="pc"),
        InlineKeyboardButton("🏠 Menu", callback_data="m:home"),
    ])

    return InlineKeyboardMarkup(rows)


# ── Playlist detail (tracks as buttons) ───────────────────────────────
def playlist_detail(playlist, tracks_with_pos, page: int = 0, page_size: int = 8) -> InlineKeyboardMarkup:
    """Show tracks in a playlist as clickable buttons."""
    start = page * page_size
    end = start + page_size
    page_items = tracks_with_pos[start:end]

    rows = []
    for idx, item in page_items:
        track = item.track
        label = f"🎵 {track.artist} — {track.title}"
        if len(label) > 45:
            label = label[:42] + "…"
        # ps: shows track info card (no re-send)
        rows.append([
            InlineKeyboardButton(label, callback_data=f"ps:{playlist.id}:{idx}"),
        ])

    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"pt:{playlist.id}:{page - 1}"))
    if end < len(tracks_with_pos):
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"pt:{playlist.id}:{page + 1}"))
    if nav:
        rows.append(nav)

    # Actions
    rows.append([
        InlineKeyboardButton("🔀 Random", callback_data=f"ti:{playlist.id}:0:r"),
        InlineKeyboardButton("🔗 Share", callback_data=f"sp:{playlist.id}"),
    ])
    rows.append([
        InlineKeyboardButton("◀️ Back", callback_data="m:pl"),
        InlineKeyboardButton("🏠 Menu", callback_data="m:home"),
    ])

    return InlineKeyboardMarkup(rows)


# ── Playlist picker (add track to playlist) ───────────────────────────
def playlist_picker(track_id: int, playlists) -> InlineKeyboardMarkup:
    rows = []
    for p in playlists:
        label = f"❤️ {p.name}" if p.is_liked else f"📁 {p.name}"
        rows.append([InlineKeyboardButton(label, callback_data=f"pa:{track_id}:{p.id}")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


# ── Delete confirmation ───────────────────────────────────────────────
def confirm_delete(playlist_id: int, name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🗑 Yes, delete '{name}'", callback_data=f"pdy:{playlist_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="m:pl"),
        ],
    ])
