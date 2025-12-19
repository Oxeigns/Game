from __future__ import annotations

from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .. import config
from ..db import get_db
from ..utils import box_card, format_money, format_time, safe_mention


PANEL_BUTTONS = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("📊 Stats", callback_data="panel:stats"), InlineKeyboardButton("👑 Admin", callback_data="panel:admin")],
        [InlineKeyboardButton("📣 Broadcast", callback_data="panel:broadcast"), InlineKeyboardButton("🧾 Logs", callback_data="panel:logs")],
        [InlineKeyboardButton("🏘️ Groups", callback_data="panel:groups"), InlineKeyboardButton("🛠️ Maintenance", callback_data="panel:maintenance")],
        [InlineKeyboardButton("🎮 Commands", callback_data="panel:help"), InlineKeyboardButton("❓ Help", callback_data="panel:help")],
    ]
)


def panel_main_card() -> str:
    return box_card(
        "Control Panel",
        [
            "Tap a button to manage.",
            "DM only."
        ],
    )


async def panel_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db()
    total_users = await db.users.estimated_document_count()
    dm_enabled = await db.users.count_documents({"dm_enabled": True})
    total_groups = await db.groups_registry.estimated_document_count()
    economy_enabled_groups = await db.groups.count_documents({"economy_enabled": True})
    tx_logs = await db.tx_logs.estimated_document_count()
    richest = db.users.find().sort("balance", -1).limit(5)
    rich_lines = []
    async for user in richest:
        rich_lines.append(f"- {safe_mention(user.get('username'), user['user_id'])}: {format_money(user.get('balance',0))}")
    card = box_card(
        "📊 Stats",
        [
            f"Users: {total_users} (DM {dm_enabled})",
            f"Groups: {total_groups}",
            f"Economy ON: {economy_enabled_groups}",
            f"Tx Logs: {tx_logs}",
            "Top Rich:",
            *rich_lines,
            "Next: Broadcast?",
        ],
    )
    await update.callback_query.edit_message_text(card, parse_mode="Markdown", reply_markup=PANEL_BUTTONS)


async def panel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👑 Sudo List", callback_data="panel:sudo_list"), InlineKeyboardButton("➕ Add Sudo", callback_data="panel:sudo_add")],
            [InlineKeyboardButton("➖ Remove Sudo", callback_data="panel:sudo_remove"), InlineKeyboardButton("🧾 Set Logs", callback_data="panel:set_logs")],
            [InlineKeyboardButton("🔙 Back", callback_data="panel:home")],
        ]
    )
    await update.callback_query.edit_message_text(
        box_card("👑 Admin", ["Manage sudo/logs.", "Next: Choose action"]), parse_mode="Markdown", reply_markup=buttons
    )


async def panel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📣 Groups", callback_data="panel:bc_groups"), InlineKeyboardButton("👤 Users", callback_data="panel:bc_users")],
            [InlineKeyboardButton("🌐 All", callback_data="panel:bc_all"), InlineKeyboardButton("⛔ Cancel", callback_data="panel:home")],
        ]
    )
    card = box_card(
        "📣 Broadcast",
        [
            "Use commands:",
            "/broadcast_groups text",
            "/broadcast_users text",
            "/broadcast_all text",
            "Next: Type command",
        ],
    )
    await update.callback_query.edit_message_text(card, parse_mode="Markdown", reply_markup=buttons)


async def panel_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db()
    settings = await db.bot_settings.find_one({"_id": "settings"})
    logs_id = settings.get("logs_group_id") if settings else None
    await update.callback_query.edit_message_text(
        box_card("🧾 Logs", [f"Logs group: {logs_id}", "Use /set_logs <id>", "Next: Add logs group"]),
        parse_mode="Markdown",
        reply_markup=PANEL_BUTTONS,
    )


async def panel_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db()
    total = await db.groups_registry.estimated_document_count()
    enabled = await db.groups.count_documents({"economy_enabled": True})
    await update.callback_query.edit_message_text(
        box_card("🏘️ Groups", [f"Tracked: {total}", f"Economy ON: {enabled}", "Next: Run /broadcast_groups"]),
        parse_mode="Markdown",
        reply_markup=PANEL_BUTTONS,
    )


async def panel_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db()
    settings = await db.bot_settings.find_one({"_id": "settings"})
    state = settings.get("maintenance_mode", False) if settings else False
    await update.callback_query.edit_message_text(
        box_card("🛠️ Maintenance", [f"Current: {'ON' if state else 'OFF'}", "Use /maintenance on|off", "Next: Toggle if needed"]),
        parse_mode="Markdown",
        reply_markup=PANEL_BUTTONS,
    )


async def panel_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text(
        box_card(
            "Help",
            [
                "Commands:",
                "/daily /rob /kill /revive /protect",
                "/give /toprich /topkill /check",
                "Admin: /economy on|off",
                "Next: /panel",
            ],
        ),
        parse_mode="Markdown",
        reply_markup=PANEL_BUTTONS,
    )
