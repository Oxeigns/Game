from datetime import timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from db import async_session
from models import Group, RelationshipType, RequestStatus, RequestType, User
from repositories import (
    adjust_points,
    create_request,
    ensure_participants,
    remove_relationship,
    resolve_request,
    upsert_relationship,
)
from utils import extract_name, ensure_group_message, italic

router = Router()


async def send_request(message: Message, r_type: RequestType, prompt: str):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(italic("Reply to a user to use this command."))
        return
    target = message.reply_to_message.from_user
    if target.is_bot:
        return
    if target.id == message.from_user.id:
        await message.reply(italic("You cannot target yourself."))
        return
    async with async_session() as session:
        actor, target_user, group, actor_stats, target_stats = await ensure_participants(
            session, message.from_user, message.chat, target
        )
        req = await create_request(session, group, actor, target_user, r_type, ttl_seconds=300)
        await session.commit()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Accept", callback_data=f"rel:{req.id}:1"),
                InlineKeyboardButton(text="Decline", callback_data=f"rel:{req.id}:0"),
            ]
        ]
    )
    await message.reply(italic(prompt), reply_markup=keyboard)


@router.message(Command("lover"))
async def lover_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    prompt = f"{extract_name(message.from_user)} wants to be lovers with {extract_name(message.reply_to_message.from_user)}." if message.reply_to_message else "Reply to someone to send a lover request."
    await send_request(message, RequestType.LOVER, prompt)


@router.message(Command("son"))
async def son_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    prompt = (
        f"{extract_name(message.from_user)} wants a family bond with {extract_name(message.reply_to_message.from_user)}."
        if message.reply_to_message
        else "Reply to someone to send a family request."
    )
    await send_request(message, RequestType.SON, prompt)


@router.callback_query(F.data.startswith("rel:"))
async def rel_callback(call: CallbackQuery):
    if not call.data or not call.from_user:
        return
    _, req_id, accept_flag = call.data.split(":")
    accept = accept_flag == "1"
    async with async_session() as session:
        req = await resolve_request(session, int(req_id), call.from_user.id, accept)
        if not req:
            await call.answer("Request missing", show_alert=True)
            return
        if req.status != RequestStatus.ACCEPTED:
            await session.commit()
            await call.answer("Updated", show_alert=True)
            return
        actor_record = await session.get(User, req.requester_id)
        group_obj = await session.get(Group, req.group_id) if call.message else None
        if not group_obj or not actor_record:
            await call.answer("Group missing", show_alert=True)
            return
        user_record = actor_record
    async with async_session() as session:
        actor_stub = type(
            "Obj",
            (),
            {
                "id": user_record.telegram_id if hasattr(user_record, "telegram_id") else req.requester_id,
                "username": getattr(user_record, "username", None),
                "first_name": getattr(user_record, "first_name", "User"),
                "is_bot": False,
            },
        )()
        target_user = call.from_user
        chat_stub = type("Obj", (), {"id": group_obj.telegram_id if hasattr(group_obj, "telegram_id") else group_obj.id, "title": call.message.chat.title if call.message else None})()
        actor, target, group, actor_stats, target_stats = await ensure_participants(
            session, actor_stub, chat_stub, target_user
        )
        rel_type = RelationshipType.LOVER if req.type == RequestType.LOVER else RelationshipType.SON
        await upsert_relationship(session, group, actor, target, rel_type)
        await upsert_relationship(session, group, target, actor, rel_type)
        await adjust_points(session, actor, group, 5)
        await adjust_points(session, target, group, 5)
        await session.commit()
    await call.message.edit_text(
        italic(
            f"{extract_name(actor_stub)} and {extract_name(target_user)} confirmed {rel_type.value}. +5 points each."
        )
    )
    await call.answer()


@router.message(Command("unlover"))
async def unlover_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        actor, _, group, _, _ = await ensure_participants(session, message.from_user, message.chat)
        removed = await remove_relationship(session, group, actor, RelationshipType.LOVER)
        await session.commit()
    text = "Lover removed." if removed else "No lover found."
    await message.reply(italic(text))


@router.message(Command("unson"))
async def unson_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        actor, _, group, _, _ = await ensure_participants(session, message.from_user, message.chat)
        removed = await remove_relationship(session, group, actor, RelationshipType.SON)
        await session.commit()
    text = "Family bond removed." if removed else "No family bond found."
    await message.reply(italic(text))
