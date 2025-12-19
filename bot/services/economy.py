from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Optional

import math
import random
from datetime import datetime, timedelta
from typing import Optional

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .. import config
from ..db import get_db
from ..utils import box_card, format_money, format_time, safe_mention, send_dm_safe, utcnow


def _calc_cooldown_remaining(last_time: Optional[datetime], cooldown: int) -> Optional[int]:
    if not last_time:
        return None
    now = utcnow()
    remaining = cooldown - int((now - last_time).total_seconds())
    return remaining if remaining > 0 else None


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict):
    db = get_db()
    reward = 2000 if user.get("premium") else 1000
    cooldown = _calc_cooldown_remaining(user.get("daily_last_claim"), config.CD_DAILY)
    if cooldown:
        await update.effective_message.reply_text(
            box_card("❌ Cooldown", [f"⏳ Try again in {cooldown}s.", "Next: Set a reminder"]),
            parse_mode="Markdown",
        )
        return
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"daily_last_claim": utcnow()}, "$inc": {"balance": reward}},
    )
    await update.effective_message.reply_text(
        box_card("✅ Daily", [f"💰 Daily reward claimed: {format_money(reward)}", "Next: Try /rob"]),
        parse_mode="Markdown",
    )


async def rob(update: Update, context: ContextTypes.DEFAULT_TYPE, robber: dict, victim: dict):
    db = get_db()
    if victim.get("is_dead"):
        await update.effective_message.reply_text(
            box_card("❌ Invalid", ["Target is dead.", "Next: Revive first"]), parse_mode="Markdown"
        )
        return
    protection_until = victim.get("protection_until")
    if protection_until and protection_until > utcnow():
        await update.effective_message.reply_text(
            box_card("🛡️ Protected", [f"Protection until {format_time(protection_until)}", "Next: Pick another target"]),
            parse_mode="Markdown",
        )
        return

    limit = 200 if robber.get("premium") else 100
    if robber.get("rob_limit_used", 0) >= limit:
        await update.effective_message.reply_text(
            box_card("❌ Limit", ["Rob limit reached.", "Next: Wait for future resets"]), parse_mode="Markdown"
        )
        return

    max_amount = 100000 if robber.get("premium") else 10000
    if victim.get("balance", 0) <= 0:
        await update.effective_message.reply_text(
            box_card("😅 Oops", ["Victim has ₹0. Nothing to rob.", "Next: Try someone else"]),
            parse_mode="Markdown",
        )
        return
    steal = min(victim.get("balance", 0), random.randint(1, max_amount))
    result = await db.users.update_one(
        {"user_id": victim["user_id"], "balance": {"$gte": steal}},
        {"$inc": {"balance": -steal}},
    )
    if result.modified_count == 0:
        await update.effective_message.reply_text(
            box_card("⚠️ Retry", ["Victim changed balance. Try again.", "Next: Pick another target"]),
            parse_mode="Markdown",
        )
        return
    await db.users.update_one(
        {"user_id": robber["user_id"]},
        {
            "$inc": {"balance": steal, "robbed_count": 1, "rob_limit_used": 1},
            "$set": {"cooldowns.rob": utcnow()},
        },
    )
    await db.tx_logs.insert_one(
        {
            "type": "rob",
            "from_user": robber["user_id"],
            "to_user": victim["user_id"],
            "amount": steal,
            "timestamp": utcnow(),
            "group_id": update.effective_chat.id,
        }
    )
    robber_name = safe_mention(robber.get("username"), robber["user_id"])
    victim_name = safe_mention(victim.get("username"), victim["user_id"])
    await update.effective_message.reply_text(
        box_card("💸 Rob", [f"{robber_name} robbed {victim_name} for {format_money(steal)}!", "Next: Secure with /protect"]),
        parse_mode="Markdown",
    )
    if victim.get("dm_enabled"):
        ok = await send_dm_safe(
            victim["user_id"],
            context,
            box_card(
                "⚠️ Robbed",
                [
                    f"You were robbed in {update.effective_chat.title}",
                    f"Amount: {format_money(steal)}",
                    f"By: {robber_name}",
                ],
            ),
        )
        if not ok:
            await db.users.update_one({"user_id": victim["user_id"]}, {"$set": {"dm_enabled": False}})
            await update.effective_message.reply_text(
                box_card("ℹ️ DM Off", ["Can't DM victim. Ask them to /start in DM.", "Next: Ping them"]),
                parse_mode="Markdown",
            )


async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE, killer: dict, target: dict):
    db = get_db()
    if target.get("is_dead"):
        await update.effective_message.reply_text(
            box_card("☠️", ["User already dead.", "Next: Use /revive"]), parse_mode="Markdown"
        )
        return
    limit = 200 if killer.get("premium") else 100
    if killer.get("kill_limit_used", 0) >= limit:
        await update.effective_message.reply_text(
            box_card("❌ Limit", ["Kill limit reached.", "Next: Wait for reset"]), parse_mode="Markdown"
        )
        return
    reward = random.randint(200, 400) if killer.get("premium") else random.randint(100, 200)
    await db.users.update_one({"user_id": target["user_id"]}, {"$set": {"is_dead": True}})
    await db.users.update_one(
        {"user_id": killer["user_id"]},
        {
            "$inc": {"kills": 1, "balance": reward, "kill_limit_used": 1},
            "$set": {"cooldowns.kill": utcnow()},
        },
    )
    await db.tx_logs.insert_one(
        {
            "type": "kill",
            "from_user": killer["user_id"],
            "to_user": target["user_id"],
            "amount": reward,
            "timestamp": utcnow(),
            "group_id": update.effective_chat.id,
        }
    )
    killer_name = safe_mention(killer.get("username"), killer["user_id"])
    target_name = safe_mention(target.get("username"), target["user_id"])
    await update.effective_message.reply_text(
        box_card("☠️ Kill", [f"{killer_name} killed {target_name} and earned {format_money(reward)}!", "Next: /protect yourself"]),
        parse_mode="Markdown",
    )
    if target.get("dm_enabled"):
        ok = await send_dm_safe(
            target["user_id"],
            context,
            box_card(
                "☠️ You were killed",
                [
                    f"You were killed in {update.effective_chat.title}",
                    f"By: {killer_name}",
                    "Use /revive to come back",
                ],
            ),
        )
        if not ok:
            await db.users.update_one({"user_id": target["user_id"]}, {"$set": {"dm_enabled": False}})
            await update.effective_message.reply_text(
                box_card("ℹ️ DM Off", ["Can't DM target. Ask them to /start in DM.", "Next: Ping them"]),
                parse_mode="Markdown",
            )


async def revive(update: Update, context: ContextTypes.DEFAULT_TYPE, target: dict):
    db = get_db()
    if not target.get("is_dead"):
        await update.effective_message.reply_text(
            box_card("✅ Alive", ["User is already alive.", "Next: Play fair"]), parse_mode="Markdown"
        )
        return
    await db.users.update_one({"user_id": target["user_id"]}, {"$set": {"is_dead": False}})
    await update.effective_message.reply_text(
        box_card("✨ Revived", ["User has been revived.", "Next: Stay safe"]), parse_mode="Markdown",
    )
    if target.get("dm_enabled"):
        await send_dm_safe(
            target["user_id"],
            context,
            box_card("✨ Revived", [f"You have been revived in {update.effective_chat.title}.", "Welcome back!"] ),
        )


async def protect(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict, days: int):
    db = get_db()
    if days < 1:
        days = 1
    if not user.get("premium"):
        days = 1
    days = min(days, 3)
    expires = utcnow() + timedelta(days=days)
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"protection_until": expires, "cooldowns.protect": utcnow()}},
    )
    await update.effective_message.reply_text(
        box_card(
            "🛡️ Protected",
            [f"Protection enabled for {days} day(s).", f"Expires: {format_time(expires)}", "Next: Relax"],
        ),
        parse_mode="Markdown",
    )


async def give(update: Update, context: ContextTypes.DEFAULT_TYPE, sender: dict, receiver: dict, amount: int):
    db = get_db()
    if amount <= 0:
        await update.effective_message.reply_text(
            box_card("❌ Amount", ["Amount must be positive.", "Next: Try again"]), parse_mode="Markdown"
        )
        return
    fee_rate = 0.05 if sender.get("premium") else 0.10
    fee = math.ceil(amount * fee_rate)
    total = amount + fee
    result = await db.users.update_one(
        {"user_id": sender["user_id"], "balance": {"$gte": total}},
        {"$inc": {"balance": -total}, "$set": {"cooldowns.give": utcnow()}},
    )
    if result.modified_count == 0:
        await update.effective_message.reply_text(
            box_card("❌ Balance", ["Not enough balance.", "Next: Earn more"]), parse_mode="Markdown"
        )
        return
    await db.users.update_one({"user_id": receiver["user_id"]}, {"$inc": {"balance": amount}})
    await db.tx_logs.insert_one(
        {
            "type": "give",
            "from_user": sender["user_id"],
            "to_user": receiver["user_id"],
            "amount": amount,
            "timestamp": utcnow(),
            "group_id": update.effective_chat.id,
        }
    )
    sender_name = safe_mention(sender.get("username"), sender["user_id"])
    receiver_name = safe_mention(receiver.get("username"), receiver["user_id"])
    await update.effective_message.reply_text(
        box_card("🎁 Gift", [f"{sender_name} sent {format_money(amount)} to {receiver_name} (fee {format_money(fee)}).", "Next: Say thanks"]),
        parse_mode="Markdown",
    )
    if receiver.get("dm_enabled"):
        ok = await send_dm_safe(
            receiver["user_id"], context, box_card("🎁 Gift", [f"You received {format_money(amount)} from {sender_name}", "Enjoy!"])
        )
        if not ok:
            await db.users.update_one({"user_id": receiver["user_id"]}, {"$set": {"dm_enabled": False}})
            await update.effective_message.reply_text(
                box_card("ℹ️ DM Off", ["Can't DM receiver. Ask them to /start in DM.", "Next: Ping them"]),
                parse_mode="Markdown",
            )


async def toprich(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db()
    top = db.users.find().sort("balance", -1).limit(10)
    lines = ["🏆 Top Rich Users:"]
    idx = 1
    async for user in top:
        prefix = "💓 " if user.get("premium") else ""
        lines.append(f"{idx}. {prefix}{safe_mention(user.get('username'), user['user_id'])} — {format_money(user.get('balance',0))}")
        idx += 1
    await update.effective_message.reply_text(box_card("Top Rich", lines), parse_mode="Markdown")


async def topkill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db()
    top = db.users.find().sort("kills", -1).limit(10)
    lines = ["🏆 Top Killers:"]
    idx = 1
    async for user in top:
        lines.append(f"{idx}. {safe_mention(user.get('username'), user['user_id'])} — {user.get('kills',0)} kills")
        idx += 1
    await update.effective_message.reply_text(box_card("Top Kill", lines), parse_mode="Markdown")


async def check_protection(update: Update, context: ContextTypes.DEFAULT_TYPE, target: dict):
    protection_until = target.get("protection_until")
    if protection_until:
        text = format_time(protection_until)
    else:
        text = "No protection"
    await update.effective_message.reply_text(
        box_card("🛡️ Protection", [f"Protection until: {text}", "Next: /protect"]), parse_mode="Markdown"
    )


async def toggle_economy(update: Update, context: ContextTypes.DEFAULT_TYPE, enabled: bool):
    db = get_db()
    await db.groups.update_one({"group_id": update.effective_chat.id}, {"$set": {"economy_enabled": enabled}}, upsert=True)
    await update.effective_message.reply_text(
        box_card("Economy", [f"✅ Economy set to: {'ON' if enabled else 'OFF'}", "Next: /toprich"]),
        parse_mode="Markdown",
    )
