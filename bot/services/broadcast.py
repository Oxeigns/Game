from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Iterable

from telegram import Update
from telegram.error import RetryAfter, Forbidden, BadRequest, NetworkError
from telegram.ext import ContextTypes

from .. import config
from ..db import get_db
from ..models import default_broadcast_job
from ..utils import box_card


async def _send_safe(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str):
    try:
        await context.bot.send_message(chat_id, text, parse_mode="Markdown")
        return True
    except RetryAfter as e:
        await asyncio.sleep(min(e.retry_after, config.MAX_RETRY_AFTER))
        try:
            await context.bot.send_message(chat_id, text, parse_mode="Markdown")
            return True
        except Exception:
            return False
    except (Forbidden, BadRequest):
        return False
    except NetworkError:
        return False


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str, text: str):
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text(box_card("❌ DM Only", ["Use this in DM.", "Next: DM me"]), parse_mode="Markdown")
        return
    db = get_db()
    job_id = str(uuid.uuid4())
    job_doc = default_broadcast_job(job_id, update.effective_user.id, text, mode)
    await db.broadcast_jobs.insert_one(job_doc)

    await update.effective_message.reply_text(
        box_card("📣 Broadcast", [f"Job started: {job_id}", "Next: Wait for summary"]), parse_mode="Markdown"
    )
    sent = 0
    failed = 0

    targets: list[int] = []
    if mode in ("groups", "both"):
        async for g in db.groups_registry.find({"removed_at": None}):
            targets.append(g["group_id"])
    if mode in ("users", "both"):
        async for u in db.users.find({"dm_enabled": True}):
            targets.append(u["user_id"])

    for chat_id in targets:
        ok = await _send_safe(context, chat_id, text)
        if ok:
            sent += 1
        else:
            failed += 1
            if mode in ("users", "both"):
                await db.users.update_one({"user_id": chat_id}, {"$set": {"dm_enabled": False}})
        await asyncio.sleep(config.BROADCAST_DELAY)

    await db.broadcast_jobs.update_one(
        {"job_id": job_id},
        {
            "$set": {
                "status": "done",
                "finished_at": datetime.utcnow(),
                "sent_count": sent,
                "failed_count": failed,
            }
        },
    )
    await update.effective_message.reply_text(
        box_card(
            "📣 Broadcast done",
            [f"Mode: {mode}", f"Sent: {sent}", f"Failed: {failed}", f"Job: {job_id}"],
        ),
        parse_mode="Markdown",
    )
