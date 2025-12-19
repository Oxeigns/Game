from __future__ import annotations

from datetime import timedelta

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import ChatPermissions

from bot.db import crud
from bot.services import moderation_service
from bot.utils.cards import render_card
from bot.utils.errors import BotError
from bot.utils.permissions import ensure_admin, ensure_group_chat, ensure_target_actionable
from bot.utils.timeparse import parse_time, TimeParseError

router = Router()


async def _ensure_reply(message: types.Message) -> types.Message:
    if not message.reply_to_message or not message.reply_to_message.from_user:
        raise BotError("Reply to a user to use this command.")
    return message.reply_to_message


async def _safe_telegram(call, error_text: str):
    try:
        return await call
    except TelegramForbiddenError:
        raise BotError("I need the proper admin rights to perform this action.")
    except TelegramBadRequest:
        raise BotError(error_text)


@router.message(Command("warn"))
async def cmd_warn(message: types.Message, session):
    await ensure_group_chat(message)
    await ensure_admin(message)
    replied = await _ensure_reply(message)
    await ensure_target_actionable(message.bot, message.chat.id, replied.from_user.id)
    reason = message.text.partition(" ")[2].strip() or "No reason"
    count, action = await moderation_service.warn_user(session, message.chat, message.from_user, replied.from_user, reason)
    card = render_card(
        "🛡 Warning Issued",
        [f"👤 Target: {replied.from_user.full_name}", f"⚠ Count: {count}", f"📝 Reason: {reason}"],
        footer=f"Action on max: {action.value.upper()}",
    )
    await message.reply(card)
    if count >= (await moderation_service.get_group_settings(session, message.chat))["max_warns"]:
        if action.value == "mute":
            until = message.date + timedelta(seconds=3600)
            await _safe_telegram(
                message.bot.restrict_chat_member(
                    message.chat.id, replied.from_user.id, ChatPermissions(can_send_messages=False), until_date=until
                ),
                "Auto-mute failed. Please check my admin rights.",
            )
        else:
            await _safe_telegram(
                message.bot.ban_chat_member(message.chat.id, replied.from_user.id),
                "Auto-ban failed. Please check my admin rights.",
            )


@router.message(Command("warns"))
async def cmd_warns(message: types.Message, session):
    await ensure_group_chat(message)
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    warns = await crud.get_warns(session, message.chat.id, target.id)
    if not warns:
        await message.reply("No warnings.")
        return
    lines = [f"{w.created_at:%Y-%m-%d}: {w.reason}" for w in warns[:5]]
    await message.reply(render_card("⚠ Warns", lines, footer=f"Total: {len(warns)}"))


@router.message(Command("resetwarns"))
async def cmd_resetwarns(message: types.Message, session):
    await ensure_group_chat(message)
    await ensure_admin(message)
    replied = await _ensure_reply(message)
    count = await moderation_service.reset_warns(session, message.chat, replied.from_user.id)
    await message.reply(render_card("✅ Warns reset", [f"Removed: {count}"]))


@router.message(Command("mute"))
async def cmd_mute(message: types.Message):
    await ensure_group_chat(message)
    await ensure_admin(message)
    replied = await _ensure_reply(message)
    parts = message.text.split()
    if len(parts) < 2:
        raise BotError("Provide duration e.g. 10m")
    try:
        delta = parse_time(parts[1])
    except TimeParseError as e:
        raise BotError(str(e))
    await ensure_target_actionable(message.bot, message.chat.id, replied.from_user.id)
    until = message.date + delta
    await _safe_telegram(
        message.bot.restrict_chat_member(
            message.chat.id, replied.from_user.id, ChatPermissions(can_send_messages=False), until_date=until
        ),
        "I could not mute this user.",
    )
    await message.reply(render_card("🔇 Muted", [f"Duration: {parts[1]}"]))


@router.message(Command("unmute"))
async def cmd_unmute(message: types.Message):
    await ensure_group_chat(message)
    await ensure_admin(message)
    replied = await _ensure_reply(message)
    await _safe_telegram(
        message.bot.restrict_chat_member(message.chat.id, replied.from_user.id, ChatPermissions(can_send_messages=True)),
        "I could not unmute this user.",
    )
    await message.reply(render_card("🔊 Unmuted", [replied.from_user.full_name]))


@router.message(Command("ban"))
async def cmd_ban(message: types.Message):
    await ensure_group_chat(message)
    await ensure_admin(message)
    replied = await _ensure_reply(message)
    await ensure_target_actionable(message.bot, message.chat.id, replied.from_user.id)
    await _safe_telegram(message.bot.ban_chat_member(message.chat.id, replied.from_user.id), "Unable to ban this user.")
    await message.reply(render_card("🚫 Banned", [replied.from_user.full_name]))


@router.message(Command("unban"))
async def cmd_unban(message: types.Message):
    await ensure_group_chat(message)
    await ensure_admin(message)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        raise BotError("Provide user id or username")
    target = parts[1].lstrip("@")
    target_id = int(target) if target.isdigit() else target
    await _safe_telegram(message.bot.unban_chat_member(message.chat.id, target_id), "Unable to unban that user.")
    await message.reply(render_card("✅ Unbanned", [str(target_id)]))


@router.message(Command("kick"))
async def cmd_kick(message: types.Message):
    await ensure_group_chat(message)
    await ensure_admin(message)
    replied = await _ensure_reply(message)
    await ensure_target_actionable(message.bot, message.chat.id, replied.from_user.id)
    await _safe_telegram(message.bot.ban_chat_member(message.chat.id, replied.from_user.id), "Unable to kick this user.")
    await _safe_telegram(message.bot.unban_chat_member(message.chat.id, replied.from_user.id), "Unable to finalize kick.")
    await message.reply(render_card("👢 Kicked", [replied.from_user.full_name]))


@router.message(Command("del"))
async def cmd_del(message: types.Message):
    await ensure_group_chat(message)
    await ensure_admin(message)
    if not message.reply_to_message:
        raise BotError("Reply to a message to delete it")
    await _safe_telegram(
        message.bot.delete_message(message.chat.id, message.reply_to_message.message_id),
        "I could not delete that message.",
    )
    try:
        await message.delete()
    except Exception:
        pass


@router.message(Command("purge"))
async def cmd_purge(message: types.Message):
    await ensure_group_chat(message)
    await ensure_admin(message)
    if not message.reply_to_message:
        raise BotError("Reply to a start message to purge")
    start_id = message.reply_to_message.message_id
    end_id = message.message_id
    for msg_id in range(start_id, end_id + 1):
        try:
            await message.bot.delete_message(message.chat.id, msg_id)
        except Exception:
            continue


@router.message(Command("rules"))
async def cmd_rules(message: types.Message, session):
    await ensure_group_chat(message)
    group = await moderation_service.get_group_settings(session, message.chat)
    rules_text = group.get("rules_text") or "No rules set."
    await message.reply(render_card("📜 Rules", [rules_text]))
