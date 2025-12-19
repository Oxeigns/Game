from __future__ import annotations

from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from .. import config
from ..db import get_db
from ..utils import box_card, format_time, safe_mention


async def send_log(context: ContextTypes.DEFAULT_TYPE, title: str, lines: list[str]):
    logs_chat = config.LOGS_GROUP_ID
    if not logs_chat:
        return
    text = box_card(title, lines)
    await context.bot.send_message(logs_chat, text, disable_web_page_preview=True, parse_mode="Markdown")


async def log_event(context: ContextTypes.DEFAULT_TYPE, event_type: str, update: Optional[Update], group_id: Optional[int], details: str):
    user = update.effective_user if update else None
    group_title = update.effective_chat.title if update and update.effective_chat else ""
    await send_log(
        context,
        "EVENT",
        [
            f"📌 {event_type}",
            f"• Time: {format_time(datetime.utcnow())}",
            f"• User: {safe_mention(user.username if user else None, user.id if user else 0)}" if user else "• User: Unknown",
            f"• Group: {group_title} ({group_id})" if group_id else "• Group: N/A",
            f"• Details: {details}",
        ],
    )


async def update_group_registry(group, update: Update):
    if not group:
        return
    db = get_db()
    info = update.effective_chat
    now = datetime.utcnow()
    await db.groups_registry.update_one(
        {"group_id": info.id},
        {
            "$set": {
                "title": info.title,
                "username": info.username,
                "last_seen_at": now,
                "last_event": "seen",
            },
            "$setOnInsert": {
                "added_at": None,
                "removed_at": None,
                "added_by": update.effective_user.id if update.effective_user else None,
            },
        },
        upsert=True,
    )
