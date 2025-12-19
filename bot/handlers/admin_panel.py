from __future__ import annotations

from aiogram import Router, types
from aiogram.filters import Command

from bot.utils.cards import render_card
from bot.utils.permissions import ensure_private_chat

router = Router()


@router.message(Command("panel"))
async def cmd_panel(message: types.Message, session):
    await ensure_private_chat(message)
    lines = [
        "Use me as an admin in your groups to unlock moderation controls.",
        "Admin-only commands: /warn /resetwarns /mute /unmute /ban /unban /kick /purge /del.",
        "Group-only tools: /rules to show your configured rules.",
        "Tip: give me delete, ban, and restrict rights so actions never fail.",
    ]
    await message.reply(render_card("🛠 Admin Panel", lines, footer="Run moderation commands directly in your group."))
