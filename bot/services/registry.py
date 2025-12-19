from __future__ import annotations

from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from ..db import get_db
from ..utils import box_card


async def handle_join_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db()
    chat = update.effective_chat
    status = update.my_chat_member.new_chat_member.status
    now = datetime.utcnow()
    if status in ("member", "administrator"):
        await db.groups_registry.update_one(
            {"group_id": chat.id},
            {
                "$set": {
                    "title": chat.title,
                    "username": chat.username,
                    "last_event": "added",
                    "added_at": now,
                    "removed_at": None,
                    "last_seen_at": now,
                },
            },
            upsert=True,
        )
    elif status in ("left", "kicked"):
        await db.groups_registry.update_one(
            {"group_id": chat.id},
            {"$set": {"removed_at": now, "last_event": "removed", "last_seen_at": now}},
            upsert=True,
        )


async def set_group_defaults(group_id: int):
    db = get_db()
    await db.groups.update_one({"group_id": group_id}, {"$setOnInsert": {"economy_enabled": True}}, upsert=True)
