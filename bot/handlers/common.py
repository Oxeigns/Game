from __future__ import annotations

import functools
from datetime import datetime
from typing import Callable, Awaitable

from telegram import Update
import functools
from datetime import datetime
from typing import Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

from .. import config
from ..db import get_db
from ..models import default_group, default_user
from ..services.logging import update_group_registry
from ..utils import box_card


async def is_superuser(user_id: int) -> bool:
    db = get_db()
    settings = await db.bot_settings.find_one({"_id": "settings"})
    owner_id = settings.get("owner_id", config.OWNER_ID) if settings else config.OWNER_ID
    sudo_users = settings.get("sudo_users", []) if settings else config.SUDO_USERS
    return user_id == owner_id or user_id in sudo_users


async def ensure_user(update: Update) -> dict:
    db = get_db()
    user = update.effective_user
    doc = await db.users.find_one({"user_id": user.id})
    if not doc:
        doc = default_user(user.id, user.username)
        await db.users.insert_one(doc)
    else:
        if user.username and user.username != doc.get("username"):
            await db.users.update_one({"user_id": user.id}, {"$set": {"username": user.username}})
            doc["username"] = user.username
    return doc


async def ensure_group(update: Update) -> dict | None:
    if not update.effective_chat or update.effective_chat.type == "private":
        return None
    db = get_db()
    doc = await db.groups.find_one({"group_id": update.effective_chat.id})
    if not doc:
        doc = default_group(update.effective_chat.id)
        await db.groups.insert_one(doc)
    await update_group_registry(doc, update)
    return doc


def require_group(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable]):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat.type == "private":
            await update.effective_message.reply_text(
                box_card("❌ Group Only", ["This command works in groups only.", "Next: Try in group"]),
                parse_mode="Markdown",
            )
            return
        return await func(update, context, *args, **kwargs)

    return wrapper


def require_reply(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable]):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_message.reply_to_message:
            await update.effective_message.reply_text(
                box_card("❌ Reply", ["Reply to a user to use this.", "Next: Reply then retry"]), parse_mode="Markdown"
            )
            return
        return await func(update, context, *args, **kwargs)

    return wrapper


def require_admin(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable]):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        member = await update.effective_chat.get_member(update.effective_user.id)
        if not member.status in ("creator", "administrator"):
            await update.effective_message.reply_text(
                box_card("❌ Admin", ["Admins only.", "Next: Ask an admin"]), parse_mode="Markdown"
            )
            return
        return await func(update, context, *args, **kwargs)

    return wrapper


def require_premium(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable]):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = await ensure_user(update)
        if not user.get("premium"):
            await update.effective_message.reply_text(
                box_card("❌ Premium", ["This command is only for Premium users.", "Next: Upgrade"]), parse_mode="Markdown"
            )
            return
        return await func(update, context, *args, **kwargs, user=user)

    return wrapper


def check_cooldown(command: str):
    def decorator(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable]):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = await ensure_user(update)
            cooldowns = user.get("cooldowns", {})
            last = cooldowns.get(command)
            if last:
                diff = (datetime.utcnow() - last).total_seconds()
                if diff < config.COOLDOWNS.get(command, 0):
                    remaining = int(config.COOLDOWNS[command] - diff)
                    await update.effective_message.reply_text(
                        box_card("⏳ Cooldown", [f"Slow down. Try again in {remaining}s." , "Next: Wait a bit"]),
                        parse_mode="Markdown",
                    )
                    return
            kwargs["user_doc"] = user
            return await func(update, context, *args, **kwargs)

        return wrapper

    return decorator


def maintenance_guard(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable]):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        db = get_db()
        settings = await db.bot_settings.find_one({"_id": "settings"})
        maintenance = settings.get("maintenance_mode", False) if settings else config.MAINTENANCE_MODE
        user_id = update.effective_user.id if update.effective_user else 0
        sudo_users = settings.get("sudo_users", []) if settings else config.SUDO_USERS
        owner_id = settings.get("owner_id", config.OWNER_ID) if settings else config.OWNER_ID
        is_super = user_id == owner_id or user_id in sudo_users
        if maintenance and not is_super:
            await update.effective_message.reply_text(
                box_card("🛠️ Maintenance", ["Bot is under maintenance. Try again later.", "Next: Wait"]),
                parse_mode="Markdown",
            )
            return
        return await func(update, context, *args, **kwargs)

    return wrapper
