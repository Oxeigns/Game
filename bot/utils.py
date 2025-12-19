import asyncio
import math
import random
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, List

from telegram import Update, User
from telegram.constants import ChatType
from telegram.error import Forbidden, BadRequest, RetryAfter, TimedOut, NetworkError
from telegram.ext import ContextTypes

from config import SETTINGS
from db import (
    users,
    groups,
    tx_logs,
    bot_settings,
    groups_registry,
)
from models import new_user_doc, new_group_doc, new_settings_doc, now_utc


def is_group(update: Update) -> bool:
    return update.effective_chat is not None and update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


def is_private(update: Update) -> bool:
    return update.effective_chat is not None and update.effective_chat.type == ChatType.PRIVATE


async def ensure_bot_settings() -> Dict[str, Any]:
    settings = await bot_settings.find_one({"_id": "settings"})
    if not settings:
        settings = new_settings_doc(SETTINGS.owner_id, SETTINGS.sudo_users, SETTINGS.logs_group_id, SETTINGS.maintenance_mode)
        await bot_settings.insert_one(settings)
    return settings


def is_superuser(settings: Dict[str, Any], user_id: int) -> bool:
    if not user_id:
        return False
    return user_id == settings.get("owner_id") or user_id in (settings.get("sudo_users") or [])


async def ensure_user(update: Update) -> Optional[Dict[str, Any]]:
    tg_user = update.effective_user
    if not tg_user:
        return None
    doc = await users.find_one({"user_id": tg_user.id})
    username = tg_user.username or ""
    if not doc:
        doc = new_user_doc(tg_user.id, username)
        await users.insert_one(doc)
    else:
        if username and doc.get("username") != username:
            await users.update_one({"user_id": tg_user.id}, {"$set": {"username": username}})
            doc["username"] = username
    return doc


async def ensure_user_from_id(user: User) -> Dict[str, Any]:
    doc = await users.find_one({"user_id": user.id})
    username = user.username or ""
    if not doc:
        doc = new_user_doc(user.id, username)
        await users.insert_one(doc)
    else:
        if username and doc.get("username") != username:
            await users.update_one({"user_id": user.id}, {"$set": {"username": username}})
            doc["username"] = username
    return doc


async def ensure_group(update: Update) -> Optional[Dict[str, Any]]:
    chat = update.effective_chat
    if not chat or not is_group(update):
        return None
    doc = await groups.find_one({"group_id": chat.id})
    if not doc:
        doc = new_group_doc(chat.id, SETTINGS.default_economy_enabled)
        await groups.insert_one(doc)
    return doc


async def update_group_registry(
    update: Update, added_by: Optional[int] = None, added_at: Optional[datetime] = None, bot=None
):
    chat = update.effective_chat
    if not chat or not is_group(update):
        return
    fields: Dict[str, Any] = {
        "title": chat.title,
        "username": getattr(chat, "username", None),
        "last_seen_at": now_utc(),
    }
    if added_by is not None:
        fields["added_by"] = added_by
    if added_at is not None:
        fields["added_at"] = added_at
    if bot:
        try:
            count = await bot.get_chat_member_count(chat.id)
            fields["member_count"] = count
        except Exception:
            pass
    await groups_registry.update_one(
        {"group_id": chat.id},
        {"$set": fields, "$setOnInsert": {"group_id": chat.id, "created_at": now_utc()}},
        upsert=True,
    )


async def economy_enabled_or_block(update: Update) -> bool:
    if not is_group(update):
        await update.effective_message.reply_text("❌ This command works in groups only.")
        return False
    g = await ensure_group(update)
    if not g.get("economy_enabled", True):
        await update.effective_message.reply_text("⛔ Economy is disabled in this group.")
        return False
    return True


async def require_reply(update: Update) -> Optional[User]:
    msg = update.effective_message
    if not msg or not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("❌ Reply to a user to use this command.")
        return None
    return msg.reply_to_message.from_user


def mention_username(user_doc: Dict[str, Any], fallback_id: int) -> str:
    username = user_doc.get("username") or ""
    if username:
        return f"@{username}"
    return f"`{fallback_id}`"


def protection_active(user_doc: Dict[str, Any]) -> bool:
    pu = user_doc.get("protection_until")
    if not pu:
        return False
    if isinstance(pu, datetime):
        return pu > now_utc()
    return False


async def check_cooldown(user_id: int, cmd: str, cd_seconds: int) -> Tuple[bool, int]:
    doc = await users.find_one({"user_id": user_id}, {"cooldowns": 1})
    last = (doc or {}).get("cooldowns", {}).get(cmd)
    if last and isinstance(last, datetime):
        delta = (now_utc() - last).total_seconds()
        if delta < cd_seconds:
            return False, int(cd_seconds - delta)
    return True, 0


async def set_cooldown(user_id: int, cmd: str):
    await users.update_one({"user_id": user_id}, {"$set": {f"cooldowns.{cmd}": now_utc()}})


async def safe_send(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str):
    try:
        await context.bot.send_message(chat_id=chat_id, text=text)
    except RetryAfter as e:
        await asyncio.sleep(int(e.retry_after) + 1)
        await safe_send(context, chat_id, text)
    except (Forbidden, BadRequest, TimedOut, NetworkError):
        return


async def safe_dm(context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str) -> bool:
    try:
        await context.bot.send_message(chat_id=user_id, text=text)
        return True
    except RetryAfter as e:
        await asyncio.sleep(int(e.retry_after) + 1)
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
            return True
        except Exception:
            return False
    except (Forbidden, BadRequest, TimedOut, NetworkError):
        return False


async def dm_or_warn(update: Update, context: ContextTypes.DEFAULT_TYPE, target_doc: Dict[str, Any], text: str):
    if not target_doc.get("dm_enabled", False):
        await update.effective_message.reply_text("ℹ️ Can't DM user. Ask them to /start me in DM.")
        return
    ok = await safe_dm(context, target_doc["user_id"], text)
    if not ok:
        await users.update_one({"user_id": target_doc["user_id"]}, {"$set": {"dm_enabled": False}})
        await update.effective_message.reply_text("ℹ️ Couldn't DM user. Ask them to /start me in DM.")


async def log_tx(tx_type: str, from_user: int, to_user: int, amount: int, group_id: int):
    await tx_logs.insert_one(
        {
            "type": tx_type,
            "from_user": from_user,
            "to_user": to_user,
            "amount": amount,
            "timestamp": now_utc(),
            "group_id": group_id,
        }
    )


def ceil_fee(amount: int, rate: float) -> int:
    return int(math.ceil(amount * rate))


def parse_int_arg(text: str) -> Optional[int]:
    try:
        return int(text.strip())
    except Exception:
        return None


def fmt_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return "None"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def rand_between(a: int, b: int) -> int:
    return random.randint(a, b)


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


async def guard_maintenance(update: Update, settings: Dict[str, Any]) -> bool:
    if not settings.get("maintenance_mode"):
        return True
    user_id = update.effective_user.id if update.effective_user else 0
    if is_superuser(settings, user_id):
        return True
    await update.effective_message.reply_text("🛠️ Bot is under maintenance. Try again later.")
    return False


async def log_event(context: ContextTypes.DEFAULT_TYPE, message: str):
    settings = await ensure_bot_settings()
    logs_group_id = settings.get("logs_group_id")
    if not logs_group_id:
        return
    try:
        await context.bot.send_message(chat_id=logs_group_id, text=message)
    except Exception:
        return


async def cooldown_guard(update: Update, cmd: str, seconds: int) -> Optional[int]:
    user_id = update.effective_user.id if update.effective_user else 0
    ok, wait = await check_cooldown(user_id, cmd, seconds)
    if not ok:
        await update.effective_message.reply_text(f"⏳ Slow down. Try again in {wait}s.")
        return None
    await set_cooldown(user_id, cmd)
    return wait


async def record_added_group(update: Update, context: ContextTypes.DEFAULT_TYPE, added_by: Optional[int]):
    chat = update.effective_chat
    if not chat:
        return
    await update_group_registry(update, added_by=added_by, added_at=now_utc())
    msg = (
        "📌 EVENT: BOT ADDED\n"
        f"• Time: {fmt_dt(now_utc())}\n"
        f"• Group: {chat.title} ({chat.id})\n"
        f"• By: {added_by if added_by else 'Unknown'}"
    )
    await log_event(context, msg)


async def record_removed_group(update: Update, context: ContextTypes.DEFAULT_TYPE, removed_by: Optional[int]):
    chat = update.effective_chat
    if not chat:
        return
    await update_group_registry(update)
    msg = (
        "📌 EVENT: BOT REMOVED\n"
        f"• Time: {fmt_dt(now_utc())}\n"
        f"• Group: {chat.title} ({chat.id})\n"
        f"• By: {removed_by if removed_by else 'Unknown'}"
    )
    await log_event(context, msg)


async def register_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    msg = (
        "📌 EVENT: USER START\n"
        f"• Time: {fmt_dt(now_utc())}\n"
        f"• User: {user.mention_html()} ({user.id})"
    )
    await log_event(context, msg)


def mention_plain(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return str(user.id)


async def ensure_target_doc(user_id: int) -> Dict[str, Any]:
    doc = await users.find_one({"user_id": user_id})
    if not doc:
        doc = new_user_doc(user_id, "")
        await users.insert_one(doc)
    return doc
