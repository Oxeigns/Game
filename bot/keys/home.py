from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🎮 Games", callback_data="menu:games"), InlineKeyboardButton(text="💰 Economy", callback_data="menu:economy")],
        [InlineKeyboardButton(text="🛡 Moderation", callback_data="menu:mod"), InlineKeyboardButton(text="ℹ️ Help", callback_data="menu:help")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Home", callback_data="menu:home")]])
