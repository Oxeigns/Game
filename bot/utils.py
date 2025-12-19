import math
import random
from datetime import datetime, timedelta
from typing import Optional, Tuple

from telegram import Update
from telegram.constants import ChatType
from telegram.error import Forbidden, BadRequest, RetryAfter, TimedOut, NetworkError
from telegram.ext import ContextTypes

from db import users, groups, tx_logs
from models import new_user_doc, new_group_doc, now_utc
from config import SETTINGS

ECONOMY_GROUP_ONLY_CMDS = {"rob", "kill", "revive", "protect", "give", "toprich", "topkill", "check", "economy"}

def is_group(update: Update) -> bool:
    return update.effective_chat and update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)

def is_private(update: Update) -> bool:
    return update.effective_chat and update.effective_chat.type == ChatType.PRIVATE

async def ensure_user(update: Update):
    u = update.effective_user
    if not u:
        return None
    doc = await users.find_one({"user_id": u.id})
    username = u.username or ""
    if not doc:
        doc = new_user_doc(u.id, username)
        await users.insert_one(doc)
    else:
        # keep username fresh (no breaking if missing)
        if username and doc.get("username") != username:
            await users.update_one({"user_id": u.id}, {"$set": {"username": username}})
            doc["username"] = username
    return doc

async def ensure_group(update: Update):
    chat = update.effective_chat
    if not chat or not is_group(update):
        return None
    doc = await groups.find_one({"group_id": chat.id})
    if not doc:
        doc = new_group_doc(chat.id, SETTINGS.default_economy_enabled)
        await groups.insert_one(doc)
    return doc

async def economy_enabled_or_block(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    # Only relevant in groups
    if not is_group(update):
        await update.effective_message.reply_text("❌ This command works in groups only.")
        return False
    g = await ensure_group(update)
    if not g.get("economy_enabled", True):
        await update.effective_message.reply_text("⛔ Economy is disabled in this group.")
        return False
    return True

async def require_reply(update: Update) -> Optional[int]:
    msg = update.effective_message
    if not msg or not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("❌ Reply to a user to use this command.")
        return None
    return msg.reply_to_message.from_user.id

def mention_username(user_doc: dict, fallback_id: int) -> str:
    un = (user_doc or {}).get("username") or ""
    return f"@{un}" if un else f"`{fallback_id}`"

def protection_active(user_doc: dict) -> bool:
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

async def safe_dm(context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str) -> bool:
    try:
        await context.bot.send_message(chat_id=user_id, text=text)
        return True
    except (Forbidden, BadRequest):
        return False
    except (RetryAfter, TimedOut, NetworkError):
        # transient errors: treat as failure to avoid DM spam loops
        return False

async def dm_or_warn(update: Update, context: ContextTypes.DEFAULT_TYPE, target_doc: dict, text: str):
    # dm_enabled gate
    if not target_doc.get("dm_enabled", False):
        await update.effective_message.reply_text("ℹ️ User hasn't enabled DM. Ask them to /start me in DM.")
        return

    ok = await safe_dm(context, target_doc["user_id"], text)
    if not ok:
        # Disable DM to avoid repeated failures
        await users.update_one({"user_id": target_doc["user_id"]}, {"$set": {"dm_enabled": False}})
        await update.effective_message.reply_text("ℹ️ Couldn't DM user. Ask them to /start me in DM.")
        return

async def log_tx(tx_type: str, from_user: int, to_user: int, amount: int, group_id: int):
    await tx_logs.insert_one({
        "type": tx_type,
        "from_user": from_user,
        "to_user": to_user,
        "amount": amount,
        "timestamp": now_utc(),
        "group_id": group_id
    })

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
