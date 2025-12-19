from __future__ import annotations

from aiogram import Router, types
from aiogram.filters import Command

from bot.services import game_service
from bot.utils.cards import render_card

router = Router()


@router.message(Command("truth"))
async def cmd_truth(message: types.Message):
    prompt = game_service.random_entry("truth")
    await message.reply(render_card("🎯 Truth", [prompt]))


@router.message(Command("dare"))
async def cmd_dare(message: types.Message):
    prompt = game_service.random_entry("dare")
    await message.reply(render_card("🔥 Dare", [prompt]))


@router.message(Command("puzzle"))
async def cmd_puzzle(message: types.Message):
    puzzle = game_service.random_entry("puzzles")
    await message.reply(render_card("🧩 Puzzle", [puzzle]))


@router.message(Command("brain", "mind"))
async def cmd_brain(message: types.Message):
    riddle = game_service.random_entry("riddles")
    await message.reply(render_card("🧠 Riddle", [riddle]))


@router.message(Command("couples"))
async def cmd_couples(message: types.Message):
    if not message.chat or not message.chat.get_members_count:
        await message.reply("Invite more friends to use this game.")
        return
    await message.reply(render_card("💞 Couples", ["The stars will pair you soon."]))
