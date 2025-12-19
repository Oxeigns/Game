from __future__ import annotations

from typing import Iterable, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def box_card(title: str, lines: Iterable[str], footer_line: str | None = "") -> str:
    clean_lines: List[str] = []
    for ln in lines:
        safe = ln.replace("`", "'")
        clean_lines.append(safe)
    if footer_line:
        clean_lines.append(footer_line)
    body = "\n".join([f"┃ {ln}" for ln in clean_lines])
    return (
        "```text\n"
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"┃ {title}\n"
        "┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{body}\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "```"
    )


def action_keyboard(buttons: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(buttons)


def quick_actions(*buttons: InlineKeyboardButton) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[btn for btn in buttons if btn]])
