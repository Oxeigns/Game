from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import Command

from bot.keys.home import back_home, main_menu
from bot.utils.cards import render_card

router = Router()


def _home_text() -> str:
    return render_card(
        "🎮 Welcome",
        [
            "All-in-one moderation, games, and economy bot.",
            "Use the menu to explore categories.",
            "Need help? Tap ℹ️ Help for usage details.",
        ],
        footer="Stay safe: admin commands are locked to admins only.",
    )


def _help_text() -> str:
    sections = [
        render_card(
            "General",
            [
                "/start — show the welcome menu",
                "/help — full command list",
                "/rules — show group rules (group-only)",
                "/panel — admin panel (DM-only)",
            ],
        ),
        render_card(
            "Economy",
            [
                "/daily — claim daily reward (24h cooldown)",
                "/bal — check your balance",
                "/give <amount> — transfer coins (reply required)",
                "/transactions — recent activity",
                "/toprich — richest players",
            ],
        ),
        render_card(
            "Combat",
            [
                "/rob — steal coins (reply, group-only)",
                "/kill — record a kill (reply, group-only)",
                "/revive — reset status (group-only)",
                "/protect — shield yourself (group-only)",
                "/topkill — top killers",
            ],
        ),
        render_card(
            "Games",
            [
                "/truth /dare — prompts",
                "/puzzle /brain — riddles",
                "/couples — playful matchmaker",
            ],
        ),
        render_card(
            "Social",
            [
                "/kiss /hug /slap /punch /bite — interact (reply)",
            ],
        ),
        render_card(
            "Moderation (admins, group-only)",
            [
                "/warn — warn user (reply, optional reason)",
                "/warns — list warns (reply optional)",
                "/resetwarns — clear warns (reply)",
                "/mute <time> /unmute — mute controls (reply)",
                "/ban /unban <id|@user> — ban controls",
                "/kick — remove user (reply)",
                "/purge — delete from replied message onward",
                "/del — delete a single replied message",
            ],
            footer="Ensure the bot has the required rights to moderate.",
        ),
    ]
    return "\n\n".join(sections)


def _games_text() -> str:
    return render_card(
        "🎲 Games",
        ["/truth, /dare, /puzzle, /brain, /couples"],
        footer="Run in any chat to get a random prompt.",
    )


def _economy_text() -> str:
    return render_card(
        "💰 Economy",
        [
            "/daily — 24h reward",
            "/bal — check balance",
            "/give <amount> — reply to transfer",
            "/transactions — history",
            "/toprich — leaderboard",
        ],
        footer="Group chats recommended for transfers and competitions.",
    )


def _moderation_text() -> str:
    return render_card(
        "🛡 Moderation",
        [
            "Admin-only, group-only commands:",
            "/warn, /warns, /resetwarns (reply)",
            "/mute <time>, /unmute, /ban, /unban",
            "/kick, /purge, /del, /rules",
        ],
        footer="Ensure I have ban/restrict/delete rights.",
    )


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(_home_text(), reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(_help_text())


async def _handle_menu(event: types.Message | types.CallbackQuery, text: str, *, root: bool = False):
    markup = main_menu() if root else back_home()
    if isinstance(event, types.CallbackQuery):
        if event.message:
            await event.message.edit_text(text, reply_markup=markup)
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup)


@router.callback_query(F.data == "menu:home")
async def menu_home(call: types.CallbackQuery):
    await _handle_menu(call, _home_text(), root=True)


@router.callback_query(F.data == "menu:games")
async def menu_games(call: types.CallbackQuery):
    await _handle_menu(call, _games_text())


@router.callback_query(F.data == "menu:economy")
async def menu_economy(call: types.CallbackQuery):
    await _handle_menu(call, _economy_text())


@router.callback_query(F.data == "menu:mod")
async def menu_moderation(call: types.CallbackQuery):
    await _handle_menu(call, _moderation_text())


@router.callback_query(F.data == "menu:help")
async def menu_help(call: types.CallbackQuery):
    await _handle_menu(call, _help_text())
