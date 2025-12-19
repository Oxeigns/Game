from __future__ import annotations

from datetime import timedelta

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import ChatPermissions

from bot.services import moderation_service
from bot.db import crud
from bot.utils.cards import render_card
from bot.utils.timeparse import parse_time, TimeParseError

router = Router()


async def _ensure_reply(message: types.Message) -> types.Message:
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("Reply to a user to use this command.")
        raise RuntimeError
    return message.reply_to_message


@router.message(Command("warn"))
async def cmd_warn(message: types.Message, session):
    replied = await _ensure_reply(message)
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
            await message.bot.restrict_chat_member(
                message.chat.id, replied.from_user.id, ChatPermissions(can_send_messages=False), until_date=until
            )
        else:
            await message.bot.ban_chat_member(message.chat.id, replied.from_user.id)


@router.message(Command("warns"))
async def cmd_warns(message: types.Message, session):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    warns = await crud.get_warns(session, message.chat.id, target.id)
    if not warns:
        await message.reply("No warnings.")
        return
    lines = [f"{w.created_at:%Y-%m-%d}: {w.reason}" for w in warns[:5]]
    await message.reply(render_card("⚠ Warns", lines, footer=f"Total: {len(warns)}"))


@router.message(Command("resetwarns"))
async def cmd_resetwarns(message: types.Message, session):
    replied = await _ensure_reply(message)
    count = await moderation_service.reset_warns(session, message.chat, replied.from_user.id)
    await message.reply(render_card("✅ Warns reset", [f"Removed: {count}"]))


@router.message(Command("mute"))
async def cmd_mute(message: types.Message):
    replied = await _ensure_reply(message)
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Provide duration e.g. 10m")
        return
    try:
        delta = parse_time(parts[1])
    except TimeParseError as e:
        await message.reply(str(e))
        return
    until = message.date + delta
    await message.bot.restrict_chat_member(
        message.chat.id, replied.from_user.id, ChatPermissions(can_send_messages=False), until_date=until
    )
    await message.reply(render_card("🔇 Muted", [f"Duration: {parts[1]}"]))


@router.message(Command("unmute"))
async def cmd_unmute(message: types.Message):
    replied = await _ensure_reply(message)
    await message.bot.restrict_chat_member(message.chat.id, replied.from_user.id, ChatPermissions(can_send_messages=True))
    await message.reply(render_card("🔊 Unmuted", [replied.from_user.full_name]))


@router.message(Command("ban"))
async def cmd_ban(message: types.Message):
    replied = await _ensure_reply(message)
    await message.bot.ban_chat_member(message.chat.id, replied.from_user.id)
    await message.reply(render_card("🚫 Banned", [replied.from_user.full_name]))


@router.message(Command("unban"))
async def cmd_unban(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Provide user id or username")
        return
    target = parts[1]
    await message.bot.unban_chat_member(message.chat.id, target)
    await message.reply(render_card("✅ Unbanned", [target]))


@router.message(Command("kick"))
async def cmd_kick(message: types.Message):
    replied = await _ensure_reply(message)
    await message.bot.ban_chat_member(message.chat.id, replied.from_user.id)
    await message.bot.unban_chat_member(message.chat.id, replied.from_user.id)
    await message.reply(render_card("👢 Kicked", [replied.from_user.full_name]))


@router.message(Command("del"))
async def cmd_del(message: types.Message):
    if not message.reply_to_message:
        await message.reply("Reply to a message to delete it")
        return
    await message.bot.delete_message(message.chat.id, message.reply_to_message.message_id)
    try:
        await message.delete()
    except Exception:
        pass


@router.message(Command("purge"))
async def cmd_purge(message: types.Message):
    if not message.reply_to_message:
        await message.reply("Reply to a start message to purge")
        return
    start_id = message.reply_to_message.message_id
    end_id = message.message_id
    for msg_id in range(start_id, end_id + 1):
        try:
            await message.bot.delete_message(message.chat.id, msg_id)
        except Exception:
            continue


@router.message(Command("rules"))
async def cmd_rules(message: types.Message, session):
    group = await moderation_service.get_group_settings(session, message.chat)
    rules_text = group.get("rules_text") or "No rules set."
    await message.reply(render_card("📜 Rules", [rules_text]))
