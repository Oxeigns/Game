from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from db import async_session
from models import RelationshipType, RequestStatus, RequestType, User
from repositories import (
    create_pending_request,
    ensure_participants,
    remove_relationship,
    resolve_request,
    set_relationship,
)
from utils import ensure_group_message, extract_name, italic

router = Router()


async def _relationship_request(message: Message, req_type: RequestType):
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
        req = await create_pending_request(session, actor, target_user, group, req_type, ttl_seconds=300)
        await session.commit()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Accept", callback_data=f"rel:{req.id}:1"),
                InlineKeyboardButton(text="Decline", callback_data=f"rel:{req.id}:0"),
            ]
        ]
    )
    label = "love" if req_type == RequestType.LOVER else "family"
    await message.reply(italic(f"{extract_name(message.from_user)} wants to be your {label}. Accept?"), reply_markup=keyboard)


@router.message(Command("lover"))
async def lover_cmd(message: Message):
    await _relationship_request(message, RequestType.LOVER)


@router.message(Command("son"))
async def son_cmd(message: Message):
    await _relationship_request(message, RequestType.SON)


@router.message(Command("unlover"))
async def unlover_cmd(message: Message):
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
        actor, target_user, _ = await ensure_participants(session, message.from_user, message.chat, target)
        await remove_relationship(session, actor, target_user, RelationshipType.LOVER)
        await session.commit()
    await message.reply(italic("Relationship cleared."))


@router.message(Command("unson"))
async def unson_cmd(message: Message):
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
        actor, target_user, _ = await ensure_participants(session, message.from_user, message.chat, target)
        await remove_relationship(session, actor, target_user, RelationshipType.PARENT)
        await session.commit()
    await message.reply(italic("Family link cleared."))


@router.callback_query(F.data.startswith("rel:"))
async def rel_callback(call: CallbackQuery):
    if not call.data or not call.from_user:
        return
    _, req_id, flag = call.data.split(":")
    accept = flag == "1"
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
            await call.answer("Missing", show_alert=True)
            return
        rel_type = RelationshipType.LOVER if req.type == RequestType.LOVER else RelationshipType.PARENT
        await set_relationship(session, requester, target, rel_type)
        await session.commit()
    await call.message.edit_text(italic("Request accepted."))
    await call.answer()
