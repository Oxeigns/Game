from __future__ import annotations

import random
from datetime import timedelta

from aiogram import Router, types
from aiogram.filters import Command

from bot.db import crud
from bot.services.economy_service import EconomyService
from bot.utils.cards import render_card
from bot.utils.rate_limit import RateLimiter

router = Router()

cooldowns = RateLimiter()
economy_service = EconomyService(rate_limiter=cooldowns)


async def _cooldown(key: str, seconds: int):
    if not await cooldowns.hit(key, seconds):
        rem = await cooldowns.remaining(key)
        raise ValueError(f"Cooldown active ({rem:.0f}s)")


@router.message(Command("rob"))
async def cmd_rob(message: types.Message, session):
    if not message.reply_to_message:
        await message.reply("Reply to someone to rob them")
        return
    await _cooldown(f"rob:{message.from_user.id}", 120)
    victim = await economy_service.ensure_user(session, message.reply_to_message.from_user)
    thief = await economy_service.ensure_user(session, message.from_user)
    stolen = min(50, victim.balance)
    victim.balance -= stolen
    thief.balance += stolen
    await crud.add_transaction(session, from_id=victim.user_id, to_id=thief.user_id, amount=stolen, tx_type=crud.TransactionType.penalty, meta={})
    await session.commit()
    await message.reply(render_card("🕵️ Robbery", [f"Stole {stolen} coins from {victim.first_name or victim.user_id}"]))


@router.message(Command("kill"))
async def cmd_kill(message: types.Message, session):
    if not message.reply_to_message:
        await message.reply("Reply to someone to engage")
        return
    await _cooldown(f"kill:{message.from_user.id}", 180)
    await crud.increment_kill(session, message.from_user.id, message.reply_to_message.from_user.id)
    await session.commit()
    await message.reply(render_card("⚔️ Duel", [f"{message.from_user.full_name} eliminated {message.reply_to_message.from_user.full_name}"]))


@router.message(Command("revive"))
async def cmd_revive(message: types.Message, session):
    await message.reply(render_card("❤️ Revive", ["You feel refreshed."]))


@router.message(Command("protect"))
async def cmd_protect(message: types.Message):
    await _cooldown(f"protect:{message.from_user.id}", 300)
    await message.reply(render_card("🛡 Protection", ["Shield enabled for next hit!"]))


@router.message(Command("topkill"))
async def cmd_topkill(message: types.Message, session):
    top = await crud.top_killers(session, limit=10)
    lines = [f"{idx+1}. {u.first_name or u.user_id}: {u.kills}" for idx, u in enumerate(top)]
    await message.reply(render_card("🏴 Top Killers", lines or ["No data"]))
