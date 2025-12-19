from datetime import timedelta

from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

from db import users, groups
from models import now_utc
from config import SETTINGS
from utils import (
    ensure_user, ensure_group, is_group, is_private,
    economy_enabled_or_block, require_reply, mention_username,
    protection_active, check_cooldown, set_cooldown,
    dm_or_warn, log_tx, ceil_fee, parse_int_arg, fmt_dt, rand_between
)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    if not is_private(update):
        await update.effective_message.reply_text("👋 DM me and send /start to enable notifications.")
        return
    uid = update.effective_user.id
    await users.update_one({"user_id": uid}, {"$set": {"dm_enabled": True}})
    await update.effective_message.reply_text(
        "✅ DM enabled!\n\nAdd me to your group and start using economy commands there."
    )

async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)

    ok, wait = await check_cooldown(user["user_id"], "daily", SETTINGS.cd_daily)
    if not ok:
        await update.effective_message.reply_text(f"⏳ Slow down. Try again in {wait}s.")
        return
    await set_cooldown(user["user_id"], "daily")

    # 24h cooldown
    last = user.get("daily_last_claim")
    if last and (now_utc() - last) < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now_utc() - last)
        hrs = int(remaining.total_seconds() // 3600)
        mins = int((remaining.total_seconds() % 3600) // 60)
        await update.effective_message.reply_text(f"⏳ Daily already claimed. Try again in {hrs}h {mins}m.")
        return

    reward = 2000 if user.get("premium", False) else 1000
    await users.update_one(
        {"user_id": user["user_id"]},
        {"$inc": {"balance": reward}, "$set": {"daily_last_claim": now_utc()}}
    )
    await update.effective_message.reply_text(f"💰 Daily reward claimed: ₹{reward}")

async def rob_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not await economy_enabled_or_block(update, context):
        return

    ok, wait = await check_cooldown(user["user_id"], "rob", SETTINGS.cd_rob)
    if not ok:
        await update.effective_message.reply_text(f"⏳ Slow down. Try again in {wait}s.")
        return
    await set_cooldown(user["user_id"], "rob")

    target_id = await require_reply(update)
    if not target_id:
        return
    if target_id == user["user_id"]:
        await update.effective_message.reply_text("❌ You can't rob yourself.")
        return

    target = await users.find_one({"user_id": target_id}) or await ensure_user_from_id(target_id)
    if target.get("is_dead", False):
        await update.effective_message.reply_text("❌ Target is dead. They must be revived first.")
        return
    if protection_active(target):
        await update.effective_message.reply_text("🛡️ Target has active protection. Rob blocked.")
        return

    # limits
    is_premium = user.get("premium", False)
    limit = 200 if is_premium else 100
    used = user.get("rob_limit_used", 0)
    if used >= limit:
        await update.effective_message.reply_text("⛔ Rob limit reached.")
        return

    max_amt = 100000 if is_premium else 10000
    victim_balance = int(target.get("balance", 0))
    if victim_balance <= 0:
        await update.effective_message.reply_text("😅 Victim has ₹0. Nothing to rob.")
        return

    import random
    steal = min(victim_balance, random.randint(1, max_amt))
    # atomic update: ensure no negative
    res = await users.update_one(
        {"user_id": target_id, "balance": {"$gte": steal}},
        {"$inc": {"balance": -steal}}
    )
    if res.modified_count == 0:
        # balance changed concurrently
        await update.effective_message.reply_text("⚠️ Rob failed. Try again.")
        return

    await users.update_one(
        {"user_id": user["user_id"]},
        {"$inc": {"balance": steal, "robbed_count": 1, "rob_limit_used": 1}}
    )

    group_name = update.effective_chat.title if update.effective_chat else "this group"
    robber_tag = mention_username(user, user["user_id"])
    victim_tag = mention_username(target, target_id)

    await update.effective_message.reply_text(f"💸 {robber_tag} robbed {victim_tag} for ₹{steal}!")

    await log_tx("rob", user["user_id"], target_id, steal, update.effective_chat.id)

    # DM victim
    dm_text = f"⚠️ You were ROBBED in {group_name}\nAmount: ₹{steal}\nBy: {robber_tag}"
    await dm_or_warn(update, context, target, dm_text)

async def kill_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not await economy_enabled_or_block(update, context):
        return

    ok, wait = await check_cooldown(user["user_id"], "kill", SETTINGS.cd_kill)
    if not ok:
        await update.effective_message.reply_text(f"⏳ Slow down. Try again in {wait}s.")
        return
    await set_cooldown(user["user_id"], "kill")

    target_id = await require_reply(update)
    if not target_id:
        return
    if target_id == user["user_id"]:
        await update.effective_message.reply_text("❌ You can't kill yourself.")
        return

    target = await users.find_one({"user_id": target_id}) or await ensure_user_from_id(target_id)
    if target.get("is_dead", False):
        await update.effective_message.reply_text("❌ Target is already dead.")
        return

    is_premium = user.get("premium", False)
    limit = 200 if is_premium else 100
    used = user.get("kill_limit_used", 0)
    if used >= limit:
        await update.effective_message.reply_text("⛔ Kill limit reached.")
        return

    reward = rand_between(200, 400) if is_premium else rand_between(100, 200)

    # mark dead
    await users.update_one({"user_id": target_id}, {"$set": {"is_dead": True}})
    await users.update_one(
        {"user_id": user["user_id"]},
        {"$inc": {"kills": 1, "kill_limit_used": 1, "balance": reward}}
    )

    group_name = update.effective_chat.title if update.effective_chat else "this group"
    killer_tag = mention_username(user, user["user_id"])
    victim_tag = mention_username(target, target_id)

    await update.effective_message.reply_text(f"☠️ {killer_tag} killed {victim_tag} and earned ₹{reward}!")
    await log_tx("kill", user["user_id"], target_id, reward, update.effective_chat.id)

    dm_text = f"☠️ You were killed in {group_name}\nBy: {killer_tag}\nUse /revive to come back"
    await dm_or_warn(update, context, target, dm_text)

async def revive_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not await economy_enabled_or_block(update, context):
        return

    ok, wait = await check_cooldown(user["user_id"], "revive", SETTINGS.cd_revive)
    if not ok:
        await update.effective_message.reply_text(f"⏳ Slow down. Try again in {wait}s.")
        return
    await set_cooldown(user["user_id"], "revive")

    msg = update.effective_message
    target_id = user["user_id"]
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target_id = msg.reply_to_message.from_user.id

    target = await users.find_one({"user_id": target_id}) or await ensure_user_from_id(target_id)
    if not target.get("is_dead", False):
        await msg.reply_text("✅ User is already alive.")
        return

    await users.update_one({"user_id": target_id}, {"$set": {"is_dead": False}})
    await msg.reply_text("✨ Revived successfully!")

    dm_text = f"✨ You have been revived in {update.effective_chat.title}."
    await dm_or_warn(update, context, target, dm_text)

async def protect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not await economy_enabled_or_block(update, context):
        return

    ok, wait = await check_cooldown(user["user_id"], "protect", SETTINGS.cd_protect)
    if not ok:
        await update.effective_message.reply_text(f"⏳ Slow down. Try again in {wait}s.")
        return
    await set_cooldown(user["user_id"], "protect")

    days = 1
    if user.get("premium", False):
        if context.args:
            d = parse_int_arg(context.args[0])
            if d in (1, 2, 3):
                days = d
    # normal users fixed 1 day

    until = now_utc() + timedelta(days=days)
    await users.update_one({"user_id": user["user_id"]}, {"$set": {"protection_until": until}})
    await update.effective_message.reply_text(f"🛡️ Protection enabled for {days} day(s). Expires: {fmt_dt(until)}")

async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not await economy_enabled_or_block(update, context):
        return

    ok, wait = await check_cooldown(user["user_id"], "give", SETTINGS.cd_give)
    if not ok:
        await update.effective_message.reply_text(f"⏳ Slow down. Try again in {wait}s.")
        return
    await set_cooldown(user["user_id"], "give")

    target_id = await require_reply(update)
    if not target_id:
        return
    if target_id == user["user_id"]:
        await update.effective_message.reply_text("❌ You can't gift yourself.")
        return

    if not context.args:
        await update.effective_message.reply_text("❌ Usage: /give <amount> (reply to user)")
        return
    amount = parse_int_arg(context.args[0])
    if not amount or amount <= 0:
        await update.effective_message.reply_text("❌ Invalid amount.")
        return

    target = await users.find_one({"user_id": target_id}) or await ensure_user_from_id(target_id)

    rate = 0.05 if user.get("premium", False) else 0.10
    fee = ceil_fee(amount, rate)
    total = amount + fee

    sender_balance = int(user.get("balance", 0))
    if sender_balance < total:
        await update.effective_message.reply_text(f"❌ Not enough balance. Need ₹{total} (includes fee ₹{fee}).")
        return

    # atomic: deduct from sender, then add to receiver
    res = await users.update_one({"user_id": user["user_id"], "balance": {"$gte": total}}, {"$inc": {"balance": -total}})
    if res.modified_count == 0:
        await update.effective_message.reply_text("⚠️ Payment failed. Try again.")
        return
    await users.update_one({"user_id": target_id}, {"$inc": {"balance": amount}})

    sender_tag = mention_username(user, user["user_id"])
    receiver_tag = mention_username(target, target_id)

    await update.effective_message.reply_text(f"🎁 {sender_tag} sent ₹{amount} to {receiver_tag} (fee ₹{fee}).")
    await log_tx("give", user["user_id"], target_id, amount, update.effective_chat.id)

    dm_text = f"🎁 You received ₹{amount} from {sender_tag}"
    await dm_or_warn(update, context, target, dm_text)

async def toprich_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    if not await economy_enabled_or_block(update, context):
        return

    top = await users.find().sort("balance", -1).limit(10).to_list(length=10)
    if not top:
        await update.effective_message.reply_text("No users yet.")
        return

    lines = ["🏆 Top Rich Users:"]
    for i, u in enumerate(top, start=1):
        tag = ("💓 " if u.get("premium") else "") + mention_username(u, u["user_id"])
        lines.append(f"{i}. {tag} — ₹{int(u.get('balance', 0))}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")

async def topkill_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    if not await economy_enabled_or_block(update, context):
        return

    top = await users.find().sort("kills", -1).limit(10).to_list(length=10)
    if not top:
        await update.effective_message.reply_text("No users yet.")
        return

    lines = ["🏆 Top Killers:"]
    for i, u in enumerate(top, start=1):
        tag = mention_username(u, u["user_id"])
        lines.append(f"{i}. {tag} — {int(u.get('kills', 0))} kills")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")

async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not await economy_enabled_or_block(update, context):
        return
    if not user.get("premium", False):
        await update.effective_message.reply_text("❌ This command is only for Premium users.")
        return

    target_id = await require_reply(update)
    if not target_id:
        return

    target = await users.find_one({"user_id": target_id}) or await ensure_user_from_id(target_id)
    until = target.get("protection_until")
    await update.effective_message.reply_text(f"🛡️ Protection until: {fmt_dt(until)}")

async def economy_toggle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    if not is_group(update):
        await update.effective_message.reply_text("❌ Group only.")
        return

    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        await update.effective_message.reply_text("❌ Admins only.")
        return

    if not context.args or context.args[0].lower() not in ("on", "off"):
        await update.effective_message.reply_text("Usage: /economy on|off")
        return

    val = context.args[0].lower() == "on"
    await ensure_group(update)
    await groups.update_one({"group_id": update.effective_chat.id}, {"$set": {"economy_enabled": val}})
    await update.effective_message.reply_text(f"✅ Economy set to: {'ON' if val else 'OFF'}")

# helper to auto-register targets that never used bot
async def ensure_user_from_id(user_id: int) -> dict:
    doc = await users.find_one({"user_id": user_id})
    if not doc:
        doc = {
            "user_id": user_id,
            "username": "",
            "balance": 0,
            "kills": 0,
            "robbed_count": 0,
            "is_dead": False,
            "protection_until": None,
            "premium": False,
            "daily_last_claim": None,
            "rob_limit_used": 0,
            "kill_limit_used": 0,
            "dm_enabled": False,
            "cooldowns": {"daily": None, "rob": None, "kill": None, "give": None, "protect": None, "revive": None}
        }
        await users.insert_one(doc)
    return doc
