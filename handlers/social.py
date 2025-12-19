from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from db import async_session
from models import Clan, Group, RequestStatus, RequestType, User
from repositories import (
    adjust_points,
    apply_clan_bonus,
    clan_bonus_due,
    create_request,
    ensure_participants,
    get_membership,
    increment_action,
    log_social_action,
    resolve_request,
)
from utils import extract_name, ensure_group_message, italic, random_dare

router = Router()


async def clan_bonus_check(session, actor_stats, group, actor, action_name: str) -> bool:
    membership = await get_membership(session, actor_stats)
    if not membership:
        return False
    clan = await session.get(Clan, membership.clan_id) if membership.clan_id else None
    if clan is None:
        return False
    await log_social_action(session, clan, group, actor, action_name)
    if await clan_bonus_due(session, clan):
        await apply_clan_bonus(session, clan)
        return True
    return False


async def handle_social(message: Message, action: str, actor_delta: int, target_delta: int = 0, actor_field: str | None = None, target_field: str | None = None):
    if not ensure_group_message(message):
        return
    if not message.from_user or message.from_user.is_bot:
        return
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
        response_parts = []
        if actor_delta:
            await adjust_points(session, actor, group, actor_delta)
            response_parts.append(f"{extract_name(message.from_user)} {action} {extract_name(target)}")
        if target_delta:
            await adjust_points(session, target_user, group, target_delta)
        if actor_field:
            await increment_action(session, actor_stats, actor_field)
        if target_field and target_stats:
            await increment_action(session, target_stats, target_field)
        bonus = await clan_bonus_check(session, actor_stats, group, actor, action)
        await session.commit()
        base_response = " ".join(response_parts) if response_parts else f"{extract_name(message.from_user)} {action} {extract_name(target)}"
        if actor_delta > 0:
            base_response += f" (+{actor_delta}p)"
        if actor_delta < 0:
            base_response += f" ({actor_delta}p)"
        if target_delta:
            base_response += f" | Target {target_delta:+}p"
        if bonus:
            base_response += " | Clan bonus +2"
        await message.reply(italic(base_response))


@router.message(Command("hug"))
async def hug_cmd(message: Message):
    await handle_social(message, "hug", actor_delta=1, target_delta=0, actor_field="hugs")


@router.message(Command("punch"))
async def punch_cmd(message: Message):
    await handle_social(message, "punch", actor_delta=-2, target_delta=-1, actor_field="punches", target_field="punches")


@router.message(Command("bite"))
async def bite_cmd(message: Message):
    await handle_social(message, "bite", actor_delta=-1, target_delta=-1, actor_field="bites", target_field="bites")


@router.message(Command("dare"))
async def dare_cmd(message: Message):
    if not ensure_group_message(message):
        return
    if not message.from_user or message.from_user.is_bot:
        return
    dare_text = random_dare()
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        if target.is_bot:
            return
        async with async_session() as session:
            actor, target_user, group, actor_stats, target_stats = await ensure_participants(
                session, message.from_user, message.chat, target
            )
            await increment_action(session, actor_stats, "dares")
            bonus = await clan_bonus_check(session, actor_stats, group, actor, "dare")
            await session.commit()
        await message.reply(italic(f"{extract_name(message.from_user)} dares {extract_name(target)}: {dare_text}{' | Clan bonus +2' if bonus else ''}"))
    else:
        async with async_session() as session:
            actor, _, group, actor_stats, _ = await ensure_participants(session, message.from_user, message.chat)
            await increment_action(session, actor_stats, "dares")
            bonus = await clan_bonus_check(session, actor_stats, group, actor, "dare")
            await session.commit()
        await message.reply(italic(f"Dare for you: {dare_text}{' | Clan bonus +2' if bonus else ''}"))


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
    if target.is_bot:
        return
    if target.id == message.from_user.id:
        await message.reply(italic("You cannot target yourself."))
        return
    async with async_session() as session:
        actor, target_user, group, actor_stats, target_stats = await ensure_participants(
            session, message.from_user, message.chat, target
        )
        req = await create_request(session, group, actor, target_user, RequestType.KISS, ttl_seconds=120)
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
            await call.answer("Request missing", show_alert=True)
            return
        if req.status != RequestStatus.ACCEPTED:
            await session.commit()
            await call.answer("Updated", show_alert=True)
            return
        actor_db = await session.get(User, req.requester_id)
        group_db = await session.get(Group, req.group_id)
        if not actor_db or not group_db:
            await call.answer("Request invalid", show_alert=True)
            return
        target_user = call.from_user
    async with async_session() as session:
        actor_stub = type("Obj", (), {
            "id": actor_db.telegram_id,
            "username": actor_db.username,
            "first_name": actor_db.first_name,
            "is_bot": False,
        })()
        chat_stub = type("Obj", (), {"id": group_db.telegram_id, "title": group_db.title})()
        actor, target, group, actor_stats, target_stats = await ensure_participants(
            session, actor_stub, chat_stub, target_user
        )
        await adjust_points(session, actor, group, 3)
        await adjust_points(session, target, group, 1)
        await increment_action(session, actor_stats, "kisses")
        await increment_action(session, target_stats, "kisses")
        bonus = await clan_bonus_check(session, actor_stats, group, actor, "kiss")
        await session.commit()
    await call.message.edit_text(
        italic(
            f"Kiss accepted! {extract_name(actor_stub)} and {extract_name(target_user)} gain points"
            f"{' | Clan bonus +2' if bonus else ''}."
        )
    )
    await call.answer()
