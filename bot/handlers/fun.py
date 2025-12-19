from __future__ import annotations

import random

from aiogram import Router, types
from aiogram.filters import Command

from bot.utils.cards import render_card

router = Router()

ACTIONS = {
    "kiss": "😘 {actor} kissed {target}!",
    "hug": "🤗 {actor} hugged {target}!",
    "slap": "👋 {actor} slapped {target}!",
    "punch": "🥊 {actor} punched {target}!",
    "bite": "🦈 {actor} bit {target}!",
}


async def _action(message: types.Message, verb: str):
    if not message.reply_to_message:
        await message.reply("Reply to someone to interact")
        return
    actor = message.from_user.full_name
    target = message.reply_to_message.from_user.full_name
    text = ACTIONS[verb].format(actor=actor, target=target)
    await message.reply(render_card("🎭 Action", [text]))


for verb in ACTIONS.keys():
    router.message(Command(verb))(lambda message, verb=verb: _action(message, verb))
