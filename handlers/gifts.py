from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db import async_session
from repositories import adjust_points, ensure_participants, gift_history, get_gift, record_gift, get_or_create_user
from utils import ensure_group_message, italic

router = Router()


@router.message(Command("gifts"))
async def gifts_cmd(message: Message):
    async with async_session() as session:
        result = await session.execute("select key, emoji, price from gifts")
        rows = result.all()
    lines = ["Gifts:"]
    for key, emoji, price in rows:
        lines.append(f"{key} {emoji} - {price}p")
    await message.reply(italic("\n".join(lines)))


@router.message(Command("gift"))
async def gift_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(italic("Specify a gift key."))
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(italic("Reply to a user to use this command."))
        return
    target = message.reply_to_message.from_user
    if target.is_bot or target.id == message.from_user.id:
        await message.reply(italic("Invalid target."))
        return
    key = parts[1].strip()
    async with async_session() as session:
        actor, target_user, group = await ensure_participants(session, message.from_user, message.chat, target)
        gift = await get_gift(session, key)
        if not gift:
            await message.reply(italic("Unknown gift."))
            return
        if actor.points < gift.price:
            await message.reply(italic("Not enough points."))
            return
        await adjust_points(session, actor, -gift.price)
        await adjust_points(session, target_user, gift.bonus_points)
        await record_gift(session, actor, target_user, gift, group)
        await session.commit()
    bonus_text = f" Receiver +{gift.bonus_points}p" if gift.bonus_points else ""
    await message.reply(italic(f"Gift sent: {gift.key} {gift.emoji}.{bonus_text}"))


@router.message(Command("gifthistory"))
async def gifthistory_cmd(message: Message):
    if not message.from_user:
        return
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        history = await gift_history(session, user)
    lines = ["Recent gifts:"]
    for entry in history:
        lines.append(f"{entry.gift_key} from {entry.sender_id} to {entry.receiver_id}")
    await message.reply(italic("\n".join(lines)))
