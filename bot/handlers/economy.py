from __future__ import annotations

from aiogram import Router, types
from aiogram.filters import Command

from bot.services.economy_service import EconomyService
from bot.utils.cards import render_card
from bot.utils.errors import BotError

router = Router()

economy_service = EconomyService(rate_limiter=None)


@router.message(Command("bal"))
async def cmd_bal(message: types.Message, session):
    balance = await economy_service.balance(session, message.from_user)
    await message.reply(render_card("💰 Balance", [f"{balance} coins"]))


@router.message(Command("daily"))
async def cmd_daily(message: types.Message, session, rate_limiter):
    economy_service.rate_limiter = rate_limiter
    reward = await economy_service.daily(session, message.from_user, rate_limiter)
    await message.reply(render_card("🎁 Daily claimed", [f"+{reward} coins"]))


@router.message(Command("give"))
async def cmd_give(message: types.Message, session):
    if not message.reply_to_message:
        raise BotError("Reply to a user to transfer.")
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        raise BotError("Provide amount, e.g. /give 100")
    amount = int(parts[1])
    await economy_service.transfer(session, message.from_user, message.reply_to_message.from_user, amount)
    await message.reply(render_card("💸 Transfer", [f"Sent {amount} to {message.reply_to_message.from_user.full_name}"]))


@router.message(Command("toprich"))
async def cmd_toprich(message: types.Message, session):
    users = await economy_service.top(session, limit=10)
    lines = [f"{idx+1}. {u.first_name or u.user_id}: {u.balance}" for idx, u in enumerate(users)]
    await message.reply(render_card("🏆 Top Rich", lines or ["No data"]))


@router.message(Command("transactions"))
async def cmd_transactions(message: types.Message, session):
    txs = await economy_service.transactions(session, message.from_user)
    lines = [f"{tx.type}: {tx.amount}" for tx in txs] or ["No transactions"]
    await message.reply(render_card("📜 Transactions", lines))
