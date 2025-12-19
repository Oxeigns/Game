from __future__ import annotations

import math
from datetime import datetime

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from .. import config
from ..db import get_db
from ..models import default_user
from ..services import economy
from ..services.admin_panel import PANEL_BUTTONS, panel_main_card
from ..services.broadcast import broadcast
from ..services.logging import log_event
from ..services.registry import set_group_defaults
from ..utils import box_card, format_time, safe_mention
from .common import (
    check_cooldown,
    ensure_group,
    ensure_user,
    is_superuser,
    maintenance_guard,
    require_admin,
    require_group,
    require_premium,
    require_reply,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    db = get_db()
    if update.effective_chat.type == "private":
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"dm_enabled": True}})
        await update.effective_message.reply_text(
            box_card("✅ DM Enabled", ["You'll now receive alerts.", "Next: Join a group and play!"]),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=PANEL_BUTTONS,
        )
        await log_event(context, "DM Start", update, None, "User enabled DM")
    else:
        await ensure_group(update)
        await update.effective_message.reply_text(
            box_card("👋 Hi", ["Use /daily or /rob to play.", "Next: DM /start for alerts"]), parse_mode=ParseMode.MARKDOWN
        )


@maintenance_guard
@check_cooldown("daily")
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE, user_doc: dict):
    await economy.daily(update, context, user_doc)


@maintenance_guard
@require_group
@require_reply
@check_cooldown("rob")
async def rob(update: Update, context: ContextTypes.DEFAULT_TYPE, user_doc: dict):
    robber = user_doc
    victim_user = update.effective_message.reply_to_message.from_user
    db = get_db()
    victim_doc = await db.users.find_one({"user_id": victim_user.id})
    if not victim_doc:
        victim_doc = default_user(victim_user.id, victim_user.username)
        await db.users.insert_one(victim_doc)
    await economy.rob(update, context, robber, victim_doc)


@maintenance_guard
@require_group
@require_reply
@check_cooldown("kill")
async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE, user_doc: dict):
    killer = user_doc
    target_user = update.effective_message.reply_to_message.from_user
    db = get_db()
    target_doc = await db.users.find_one({"user_id": target_user.id})
    if not target_doc:
        target_doc = default_user(target_user.id, target_user.username)
        await db.users.insert_one(target_doc)
    await economy.kill(update, context, killer, target_doc)


@maintenance_guard
@require_group
@check_cooldown("revive")
async def revive(update: Update, context: ContextTypes.DEFAULT_TYPE, user_doc: dict):
    db = get_db()
    target_user = update.effective_message.reply_to_message.from_user if update.effective_message.reply_to_message else update.effective_user
    target_doc = await db.users.find_one({"user_id": target_user.id})
    if not target_doc:
        target_doc = default_user(target_user.id, target_user.username)
        await db.users.insert_one(target_doc)
    await economy.revive(update, context, target_doc)


@maintenance_guard
@require_group
@check_cooldown("protect")
async def protect(update: Update, context: ContextTypes.DEFAULT_TYPE, user_doc: dict):
    args = context.args
    days = 1
    if args:
        try:
            days = int(args[0])
        except ValueError:
            days = 1
    await economy.protect(update, context, user_doc, days)


@maintenance_guard
@require_group
@require_reply
@check_cooldown("give")
async def give(update: Update, context: ContextTypes.DEFAULT_TYPE, user_doc: dict):
    db = get_db()
    receiver_user = update.effective_message.reply_to_message.from_user
    if receiver_user.id == user_doc["user_id"]:
        await update.effective_message.reply_text(
            box_card("❌ Invalid", ["Cannot give to yourself.", "Next: Pick someone else"]), parse_mode="Markdown"
        )
        return
    try:
        amount = int(context.args[0]) if context.args else 0
    except ValueError:
        amount = 0
    receiver_doc = await db.users.find_one({"user_id": receiver_user.id})
    if not receiver_doc:
        receiver_doc = default_user(receiver_user.id, receiver_user.username)
        await db.users.insert_one(receiver_doc)
    await economy.give(update, context, user_doc, receiver_doc, amount)


@maintenance_guard
@require_group
async def toprich(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await economy.toprich(update, context)


@maintenance_guard
@require_group
async def topkill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await economy.topkill(update, context)


@maintenance_guard
@require_group
@require_reply
@require_premium
async def check(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict):
    db = get_db()
    target_user = update.effective_message.reply_to_message.from_user
    target_doc = await db.users.find_one({"user_id": target_user.id})
    if not target_doc:
        target_doc = default_user(target_user.id, target_user.username)
        await db.users.insert_one(target_doc)
    await economy.check_protection(update, context, target_doc)


@maintenance_guard
@require_group
@require_admin
async def economy_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or args[0].lower() not in ["on", "off"]:
        await update.effective_message.reply_text(
            box_card("Usage", ["/economy on|off", "Next: Toggle economy"]), parse_mode="Markdown"
        )
        return
    enabled = args[0].lower() == "on"
    await economy.toggle_economy(update, context, enabled)
    await log_event(context, "Economy", update, update.effective_chat.id, f"Set to {enabled}")


@check_cooldown("broadcast")
async def broadcast_groups(update: Update, context: ContextTypes.DEFAULT_TYPE, user_doc: dict | None = None):
    user_id = update.effective_user.id
    if update.effective_chat.type != "private" or not await is_superuser(user_id):
        await update.effective_message.reply_text(box_card("❌", ["Superusers only in DM.", "Next: DM owner"]), parse_mode="Markdown")
        return
    text = " ".join(context.args)
    if not text:
        await update.effective_message.reply_text(box_card("Usage", ["/broadcast_groups <text>", "Next: Provide text"]), parse_mode="Markdown")
        return
    await broadcast(update, context, "groups", text)


@check_cooldown("broadcast")
async def broadcast_users(update: Update, context: ContextTypes.DEFAULT_TYPE, user_doc: dict | None = None):
    user_id = update.effective_user.id
    if update.effective_chat.type != "private" or not await is_superuser(user_id):
        await update.effective_message.reply_text(box_card("❌", ["Superusers only in DM.", "Next: DM owner"]), parse_mode="Markdown")
        return
    text = " ".join(context.args)
    if not text:
        await update.effective_message.reply_text(box_card("Usage", ["/broadcast_users <text>", "Next: Provide text"]), parse_mode="Markdown")
        return
    await broadcast(update, context, "users", text)


@check_cooldown("broadcast")
async def broadcast_all(update: Update, context: ContextTypes.DEFAULT_TYPE, user_doc: dict | None = None):
    user_id = update.effective_user.id
    if update.effective_chat.type != "private" or not await is_superuser(user_id):
        await update.effective_message.reply_text(box_card("❌", ["Superusers only in DM.", "Next: DM owner"]), parse_mode="Markdown")
        return
    text = " ".join(context.args)
    if not text:
        await update.effective_message.reply_text(box_card("Usage", ["/broadcast_all <text>", "Next: Provide text"]), parse_mode="Markdown")
        return
    await broadcast(update, context, "both", text)


async def sudo_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or update.effective_user.id != config.OWNER_ID:
        await update.effective_message.reply_text(box_card("❌", ["Owner only in DM.", "Next: Ask owner"]), parse_mode="Markdown")
        return
    if not context.args:
        await update.effective_message.reply_text(box_card("Usage", ["/sudo_add <user_id>", "Next: Provide ID"]), parse_mode="Markdown")
        return
    try:
        target = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text(box_card("❌", ["Invalid ID", "Next: Retry"]), parse_mode="Markdown")
        return
    db = get_db()
    await db.bot_settings.update_one({"_id": "settings"}, {"$addToSet": {"sudo_users": target}}, upsert=True)
    await update.effective_message.reply_text(box_card("✅", [f"Sudo added: {target}", "Next: /sudo_list"]), parse_mode="Markdown")


async def sudo_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or update.effective_user.id != config.OWNER_ID:
        await update.effective_message.reply_text(box_card("❌", ["Owner only in DM.", "Next: Ask owner"]), parse_mode="Markdown")
        return
    if not context.args:
        await update.effective_message.reply_text(box_card("Usage", ["/sudo_remove <user_id>", "Next: Provide ID"]), parse_mode="Markdown")
        return
    try:
        target = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text(box_card("❌", ["Invalid ID", "Next: Retry"]), parse_mode="Markdown")
        return
    db = get_db()
    await db.bot_settings.update_one({"_id": "settings"}, {"$pull": {"sudo_users": target}}, upsert=True)
    await update.effective_message.reply_text(box_card("✅", [f"Sudo removed: {target}", "Next: /sudo_list"]), parse_mode="Markdown")


async def sudo_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or update.effective_user.id != config.OWNER_ID:
        await update.effective_message.reply_text(box_card("❌", ["Owner only in DM.", "Next: Ask owner"]), parse_mode="Markdown")
        return
    db = get_db()
    settings = await db.bot_settings.find_one({"_id": "settings"})
    sudo_users = settings.get("sudo_users", []) if settings else []
    lines = ["Sudo Users:", *[str(x) for x in sudo_users], "Next: /sudo_add"]
    await update.effective_message.reply_text(box_card("👑 Sudo", lines), parse_mode="Markdown")


async def set_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or update.effective_user.id != config.OWNER_ID:
        await update.effective_message.reply_text(box_card("❌", ["Owner only in DM.", "Next: Ask owner"]), parse_mode="Markdown")
        return
    if not context.args:
        await update.effective_message.reply_text(box_card("Usage", ["/set_logs <group_id>", "Next: Provide ID"]), parse_mode="Markdown")
        return
    try:
        gid = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text(box_card("❌", ["Invalid ID", "Next: Retry"]), parse_mode="Markdown")
        return
    db = get_db()
    await db.bot_settings.update_one({"_id": "settings"}, {"$set": {"logs_group_id": gid}}, upsert=True)
    await update.effective_message.reply_text(box_card("✅", [f"Logs group set: {gid}", "Next: Add bot to group"]), parse_mode="Markdown")


async def get_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or update.effective_user.id != config.OWNER_ID:
        await update.effective_message.reply_text(box_card("❌", ["Owner only in DM.", "Next: Ask owner"]), parse_mode="Markdown")
        return
    db = get_db()
    settings = await db.bot_settings.find_one({"_id": "settings"})
    gid = settings.get("logs_group_id") if settings else None
    await update.effective_message.reply_text(box_card("🧾 Logs", [f"Logs group: {gid}", "Next: /set_logs <id>"] ), parse_mode="Markdown")


async def maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or update.effective_user.id != config.OWNER_ID:
        await update.effective_message.reply_text(box_card("❌", ["Owner only in DM.", "Next: Ask owner"]), parse_mode="Markdown")
        return
    if not context.args or context.args[0].lower() not in ["on", "off"]:
        await update.effective_message.reply_text(box_card("Usage", ["/maintenance on|off", "Next: Toggle"]), parse_mode="Markdown")
        return
    enabled = context.args[0].lower() == "on"
    db = get_db()
    await db.bot_settings.update_one({"_id": "settings"}, {"$set": {"maintenance_mode": enabled}}, upsert=True)
    await update.effective_message.reply_text(box_card("🛠️", [f"Maintenance: {'ON' if enabled else 'OFF'}", "Next: Inform users"]), parse_mode="Markdown")
    await log_event(context, "Maintenance", update, None, f"State: {enabled}")


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db()
    settings = await db.bot_settings.find_one({"_id": "settings"})
    sudo_users = settings.get("sudo_users", []) if settings else []
    owner_id = settings.get("owner_id", config.OWNER_ID) if settings else config.OWNER_ID
    user_id = update.effective_user.id
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text(box_card("❌ DM", ["Use in DM.", "Next: DM me"]), parse_mode="Markdown")
        return
    if user_id != owner_id and user_id not in sudo_users:
        await update.effective_message.reply_text(box_card("❌", ["Not allowed.", "Next: Ask owner"]), parse_mode="Markdown")
        return
    await update.effective_message.reply_text(panel_main_card(), parse_mode="Markdown", reply_markup=PANEL_BUTTONS)


COMMANDS = [
    CommandHandler("start", start),
    CommandHandler("daily", daily),
    CommandHandler("rob", rob),
    CommandHandler("kill", kill),
    CommandHandler("revive", revive),
    CommandHandler("protect", protect),
    CommandHandler("give", give),
    CommandHandler("toprich", toprich),
    CommandHandler("topkill", topkill),
    CommandHandler("check", check),
    CommandHandler("economy", economy_toggle),
    CommandHandler("broadcast_groups", broadcast_groups),
    CommandHandler("broadcast_users", broadcast_users),
    CommandHandler("broadcast_all", broadcast_all),
    CommandHandler("sudo_add", sudo_add),
    CommandHandler("sudo_remove", sudo_remove),
    CommandHandler("sudo_list", sudo_list),
    CommandHandler("set_logs", set_logs),
    CommandHandler("get_logs", get_logs),
    CommandHandler("maintenance", maintenance),
    CommandHandler("panel", panel),
]
