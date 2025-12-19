from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from db import async_session
from models import RequestStatus, RequestType, User
from repositories import adjust_points, create_pending_request, ensure_participants, resolve_request
from utils import extract_name, ensure_group_message, italic

router = Router()


def _display_user(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return user.first_name or "User"


async def handle_social(message: Message, action: str, actor_delta: int, target_delta: int):
    if not ensure_group_message(message):
        return
    if not message.from_user or message.from_user.is_bot:
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(italic("Reply to a user to use this command."))
        return
    target = message.reply_to_message.from_user
    if target.is_bot or target.id == message.from_user.id:
        await message.reply(italic("You cannot target yourself."))
        return
    async with async_session() as session:
        actor, target_user, group = await ensure_participants(session, message.from_user, message.chat, target)
        await adjust_points(session, actor, actor_delta)
        await adjust_points(session, target_user, target_delta)
        await session.commit()
    await message.reply(
        italic(
            f"{extract_name(message.from_user)} {action} {extract_name(target)} ({actor_delta:+}p | target {target_delta:+}p)"
        )
    )


@router.message(Command("hug"))
async def hug_cmd(message: Message):
    await handle_social(message, "hug", actor_delta=1, target_delta=0)


@router.message(Command("punch"))
async def punch_cmd(message: Message):
    await handle_social(message, "punch", actor_delta=-2, target_delta=-1)


@router.message(Command("bite"))
async def bite_cmd(message: Message):
    await handle_social(message, "bite", actor_delta=-1, target_delta=-1)


@router.message(Command("dare"))
async def dare_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    dare_text = "Complete a creative challenge today!"
    if message.reply_to_message and message.reply_to_message.from_user and not message.reply_to_message.from_user.is_bot:
        await message.reply(
            italic(f"{extract_name(message.from_user)} dares {extract_name(message.reply_to_message.from_user)}: {dare_text}")
        )
    else:
        await message.reply(italic(f"Dare: {dare_text}"))


@router.message(Command("kiss"))
async def kiss_cmd(message: Message):
    if not ensure_group_message(message):
        return
    if not message.from_user or message.from_user.is_bot:
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(italic("Reply to a user to use this command."))
        return
    target = message.reply_to_message.from_user
    if target.is_bot or target.id == message.from_user.id:
        await message.reply(italic("You cannot target yourself."))
        return
    async with async_session() as session:
        actor, target_user, group = await ensure_participants(session, message.from_user, message.chat, target)
        req = await create_pending_request(session, actor, target_user, group, RequestType.KISS, ttl_seconds=120)
        await session.commit()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Accept", callback_data=f"kiss:{req.id}:1"),
                InlineKeyboardButton(text="Decline", callback_data=f"kiss:{req.id}:0"),
            ]
        ]
    )
    await message.reply(
        italic(f"{extract_name(message.from_user)} wants to kiss {extract_name(target)}. Accept?"),
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("kiss:"))
async def kiss_callback(call: CallbackQuery):
    if not call.data or not call.from_user:
        return
    _, req_id, accept_flag = call.data.split(":")
    accept = accept_flag == "1"
    async with async_session() as session:
        req = await resolve_request(session, int(req_id), call.from_user.id, accept)
        if not req:
            await call.answer("Expired", show_alert=True)
            return
        if req.status != RequestStatus.ACCEPTED:
            await session.commit()
            await call.answer("Updated", show_alert=True)
            return
        requester = await session.get(User, req.requester_id)
        target = await session.get(User, req.target_id)
        if not requester or not target:
            await call.answer("Missing user", show_alert=True)
            return
        await adjust_points(session, requester, 3)
        await adjust_points(session, target, 1)
        await session.commit()
    await call.message.edit_text(
        italic(f"Kiss accepted! {_display_user(requester)} +3p, {_display_user(target)} +1p."),
    )
    await call.answer()
