from __future__ import annotations

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import FSInputFile

from bot.keys.home import main_menu
from bot.utils.cards import render_card

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    caption = render_card(
        "🎮 Premium Control",
        [
            "✨ All-in-one moderator + games",
            "🛡 Powered by antiflood + filters",
            "💰 Economy, combat and leaderboards",
        ],
        footer="Use the menu below to explore.",
    )
    photo = FSInputFile("assets/start.jpg")
    await message.answer_photo(photo=photo, caption=caption, reply_markup=main_menu(), parse_mode="Markdown")


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    text = render_card(
        "ℹ️ Help",
        [
            "🛡 Moderation: /warn /mute /ban /resetwarns",
            "💰 Economy: /bal /daily /give /toprich",
            "🎲 Games: /truth /dare /puzzle /couples",
            "⚔️ Combat: /rob /kill /revive /protect",
        ],
        footer="Admins: /panel to configure",
    )
    await message.answer(text)
