from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TimedOut
from telegram.ext import ContextTypes

from . import config


def format_money(amount: int) -> str:
    return f"₹{amount:,}"


def format_time(dt: datetime) -> str:
    return dt.strftime(config.TIME_FORMAT)


def safe_mention(username: Optional[str], user_id: int) -> str:
    return f"@{username}" if username else f"ID: {user_id}"


def box_card(title: str, lines: list[str]) -> str:
    sanitized = []
    for ln in lines:
        ln = ln.replace("`", "'")
        if len(ln) > 48:
            ln = ln[:45] + "…"
        sanitized.append(ln)
    body = "\n".join(["┃ " + ln for ln in sanitized])
    card = f"```
┏━━━━━━━━━━━━━━━━━━━━━━
┃ {title}
┣━━━━━━━━━━━━━━━━━━━━━━
{body}
┗━━━━━━━━━━━━━━━━━━━━━━
```"
    return card


def action_keyboard(buttons: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(buttons)


async def safe_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, keyboard: InlineKeyboardMarkup | None = None, edit: bool = False):
    try:
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    except RetryAfter as e:
        await asyncio.sleep(min(e.retry_after, config.MAX_RETRY_AFTER))
        try:
            if edit and update.callback_query:
                await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            else:
                await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            return
    except (Forbidden, BadRequest, TimedOut, NetworkError):
        return


async def send_dm_safe(user_id: int, context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        await context.bot.send_message(user_id, text, parse_mode=ParseMode.MARKDOWN)
        return True
    except RetryAfter as e:
        await asyncio.sleep(min(e.retry_after, config.MAX_RETRY_AFTER))
        try:
            await context.bot.send_message(user_id, text, parse_mode=ParseMode.MARKDOWN)
            return True
        except Exception:
            return False
    except (Forbidden, BadRequest):
        return False
    except (TimedOut, NetworkError):
        return False


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


async def ensure_dm(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    button = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Enable DM", url=url)]]
    )
    await safe_reply(update, context, box_card("DM Needed", ["ℹ️ Can't DM user. Ask them to /start me in DM.", "Next: Tap Enable DM"]), keyboard=button)
