import asyncio
import uuid
from datetime import timedelta
from typing import List, Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatMemberStatus, ParseMode, ChatType
from telegram.error import BadRequest, Forbidden, RetryAfter
from telegram.ext import ContextTypes

from config import SETTINGS
from db import users, groups, tx_logs, bot_settings, groups_registry, broadcast_jobs
from models import now_utc
from utils import (
    ensure_user,
    ensure_user_from_id,
    ensure_group,
    update_group_registry,
    is_group,
    is_private,
    economy_enabled_or_block,
    require_reply,
    mention_username,
    protection_active,
    check_cooldown,
    set_cooldown,
    dm_or_warn,
    log_tx,
    ceil_fee,
    parse_int_arg,
    fmt_dt,
    rand_between,
    guard_maintenance,
    ensure_bot_settings,
    is_superuser,
    log_event,
    register_user_start,
    cooldown_guard,
    record_added_group,
    record_removed_group,
    safe_dm,
)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_doc = await ensure_user(update)
    settings = await ensure_bot_settings()
    if not await guard_maintenance(update, settings):
        return
    if is_private(update):
        await users.update_one({"user_id": user_doc["user_id"]}, {"$set": {"dm_enabled": True}})
        await register_user_start(update, context)
        await update.effective_message.reply_text(
            "✅ DM enabled!\n\nUse /daily or join a group to play the economy game.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.effective_message.reply_text("👋 DM me and send /start to enable notifications.")


async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    settings = await ensure_bot_settings()
    if not await guard_maintenance(update, settings):
        return

    if await cooldown_guard(update, "daily", SETTINGS.cd_daily) is None:
        return

    last = user.get("daily_last_claim")
    if last and (now_utc() - last) < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now_utc() - last)
        hrs = int(remaining.total_seconds() // 3600)
        mins = int((remaining.total_seconds() % 3600) // 60)
        await update.effective_message.reply_text(
            f"⏳ Daily already claimed. Try again in {hrs}h {mins}m."
        )
        return

    reward = 2000 if user.get("premium", False) else 1000
    await users.update_one(
        {"user_id": user["user_id"]},
        {"$inc": {"balance": reward}, "$set": {"daily_last_claim": now_utc()}},
    )
    await update.effective_message.reply_text(f"💰 Daily reward claimed: ₹{reward}")


async def rob_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    settings = await ensure_bot_settings()
    if not await guard_maintenance(update, settings):
        return
    if not await economy_enabled_or_block(update):
        return
    await ensure_group(update)
    await update_group_registry(update, bot=context.bot)

    if await cooldown_guard(update, "rob", SETTINGS.cd_rob) is None:
        return

    target_user = await require_reply(update)
    if not target_user:
        return
    if target_user.id == user["user_id"]:
        await update.effective_message.reply_text("❌ You can't rob yourself.")
        return

    target = await ensure_user_from_id(target_user)
    if target.get("is_dead", False):
        await update.effective_message.reply_text("❌ Target is dead. They must be revived first.")
        return
    if protection_active(target):
        await update.effective_message.reply_text("🛡️ Target has active protection. Rob blocked.")
        return

    is_premium = user.get("premium", False)
    limit = 200 if is_premium else 100
    if user.get("rob_limit_used", 0) >= limit:
        await update.effective_message.reply_text("⛔ Rob limit reached.")
        return

    max_amt = 100000 if is_premium else 10000
    victim_balance = int(target.get("balance", 0))
    if victim_balance <= 0:
        await update.effective_message.reply_text("😅 Victim has ₹0. Nothing to rob.")
        return

    steal = min(victim_balance, rand_between(1, max_amt))
    res = await users.update_one(
        {"user_id": target_user.id, "balance": {"$gte": steal}}, {"$inc": {"balance": -steal}}
    )
    if res.modified_count == 0:
        await update.effective_message.reply_text("⚠️ Rob failed. Try again.")
        return

    await users.update_one(
        {"user_id": user["user_id"]},
        {"$inc": {"balance": steal, "robbed_count": 1, "rob_limit_used": 1}},
    )

    robber_tag = mention_username(user, user["user_id"])
    victim_tag = mention_username(target, target_user.id)
    await update.effective_message.reply_text(f"💸 {robber_tag} robbed {victim_tag} for ₹{steal}!")
    await log_tx("rob", user["user_id"], target_user.id, steal, update.effective_chat.id)

    dm_text = (
        f"⚠️ You were ROBBED in {update.effective_chat.title}\n"
        f"Amount: ₹{steal}\nBy: {robber_tag}"
    )
    await dm_or_warn(update, context, target, dm_text)


async def kill_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    settings = await ensure_bot_settings()
    if not await guard_maintenance(update, settings):
        return
    if not await economy_enabled_or_block(update):
        return
    await ensure_group(update)
    await update_group_registry(update, bot=context.bot)

    if await cooldown_guard(update, "kill", SETTINGS.cd_kill) is None:
        return

    target_user = await require_reply(update)
    if not target_user:
        return
    if target_user.id == user["user_id"]:
        await update.effective_message.reply_text("❌ You can't kill yourself.")
        return

    target = await ensure_user_from_id(target_user)
    if target.get("is_dead", False):
        await update.effective_message.reply_text("❌ Target is already dead.")
        return

    is_premium = user.get("premium", False)
    limit = 200 if is_premium else 100
    if user.get("kill_limit_used", 0) >= limit:
        await update.effective_message.reply_text("⛔ Kill limit reached.")
        return

    reward = rand_between(200, 400) if is_premium else rand_between(100, 200)
    await users.update_one({"user_id": target_user.id}, {"$set": {"is_dead": True}})
    await users.update_one(
        {"user_id": user["user_id"]},
        {"$inc": {"kills": 1, "kill_limit_used": 1, "balance": reward}},
    )

    killer_tag = mention_username(user, user["user_id"])
    victim_tag = mention_username(target, target_user.id)
    await update.effective_message.reply_text(
        f"☠️ {killer_tag} killed {victim_tag} and earned ₹{reward}!"
    )
    await log_tx("kill", user["user_id"], target_user.id, reward, update.effective_chat.id)

    dm_text = (
        f"☠️ You were killed in {update.effective_chat.title}\n"
        f"By: {killer_tag}\nUse /revive to come back"
    )
    await dm_or_warn(update, context, target, dm_text)


async def revive_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    settings = await ensure_bot_settings()
    if not await guard_maintenance(update, settings):
        return
    if not await economy_enabled_or_block(update):
        return
    await ensure_group(update)
    await update_group_registry(update, bot=context.bot)

    if await cooldown_guard(update, "revive", SETTINGS.cd_revive) is None:
        return

    msg = update.effective_message
    target_user = msg.reply_to_message.from_user if msg.reply_to_message and msg.reply_to_message.from_user else update.effective_user
    target = await ensure_user_from_id(target_user)

    if not target.get("is_dead", False):
        await msg.reply_text("✅ User is already alive.")
        return

    await users.update_one({"user_id": target_user.id}, {"$set": {"is_dead": False}})
    await msg.reply_text("✨ You have been revived in this group.")

    dm_text = f"✨ You have been revived in {update.effective_chat.title}."
    await dm_or_warn(update, context, target, dm_text)


async def protect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    settings = await ensure_bot_settings()
    if not await guard_maintenance(update, settings):
        return
    if not await economy_enabled_or_block(update):
        return
    await ensure_group(update)
    await update_group_registry(update, bot=context.bot)

    if await cooldown_guard(update, "protect", SETTINGS.cd_protect) is None:
        return

    days = 1
    if user.get("premium", False) and context.args:
        d = parse_int_arg(context.args[0])
        if d in (1, 2, 3):
            days = d
    until = now_utc() + timedelta(days=days)
    await users.update_one({"user_id": user["user_id"]}, {"$set": {"protection_until": until}})
    await update.effective_message.reply_text(
        f"🛡️ Protection enabled for {days} day(s). Expires: {fmt_dt(until)}"
    )


async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    settings = await ensure_bot_settings()
    if not await guard_maintenance(update, settings):
        return
    if not await economy_enabled_or_block(update):
        return
    await ensure_group(update)
    await update_group_registry(update, bot=context.bot)

    if await cooldown_guard(update, "give", SETTINGS.cd_give) is None:
        return

    target_user = await require_reply(update)
    if not target_user:
        return
    if target_user.id == user["user_id"]:
        await update.effective_message.reply_text("❌ You can't gift yourself.")
        return

    if not context.args:
        await update.effective_message.reply_text("❌ Usage: /give <amount> (reply to user)")
        return
    amount = parse_int_arg(context.args[0])
    if not amount or amount <= 0:
        await update.effective_message.reply_text("❌ Invalid amount.")
        return

    target = await ensure_user_from_id(target_user)

    rate = 0.05 if user.get("premium", False) else 0.10
    fee = ceil_fee(amount, rate)
    total = amount + fee

    res = await users.update_one(
        {"user_id": user["user_id"], "balance": {"$gte": total}}, {"$inc": {"balance": -total}}
    )
    if res.modified_count == 0:
        await update.effective_message.reply_text(
            f"❌ Not enough balance. Need ₹{total} (includes fee ₹{fee})."
        )
        return
    await users.update_one({"user_id": target_user.id}, {"$inc": {"balance": amount}})

    sender_tag = mention_username(user, user["user_id"])
    receiver_tag = mention_username(target, target_user.id)
    await update.effective_message.reply_text(
        f"🎁 {sender_tag} sent ₹{amount} to {receiver_tag} (fee ₹{fee})."
    )
    await log_tx("give", user["user_id"], target_user.id, amount, update.effective_chat.id)

    dm_text = f"🎁 You received ₹{amount} from {sender_tag}"
    await dm_or_warn(update, context, target, dm_text)


async def toprich_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    settings = await ensure_bot_settings()
    if not await guard_maintenance(update, settings):
        return
    if not await economy_enabled_or_block(update):
        return
    await ensure_group(update)
    await update_group_registry(update, bot=context.bot)

    if await cooldown_guard(update, "toprich", 3) is None:
        return

    top = await users.find().sort("balance", -1).limit(10).to_list(length=10)
    if not top:
        await update.effective_message.reply_text("No users yet.")
        return

    lines = ["🏆 Top Rich Users:"]
    for i, u in enumerate(top, start=1):
        tag = ("💓 " if u.get("premium") else "") + mention_username(u, u["user_id"])
        lines.append(f"{i}. {tag} — ₹{int(u.get('balance', 0))}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def topkill_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    settings = await ensure_bot_settings()
    if not await guard_maintenance(update, settings):
        return
    if not await economy_enabled_or_block(update):
        return
    await ensure_group(update)
    await update_group_registry(update, bot=context.bot)

    if await cooldown_guard(update, "topkill", 3) is None:
        return

    top = await users.find().sort("kills", -1).limit(10).to_list(length=10)
    if not top:
        await update.effective_message.reply_text("No users yet.")
        return

    lines = ["🏆 Top Killers:"]
    for i, u in enumerate(top, start=1):
        tag = mention_username(u, u["user_id"])
        lines.append(f"{i}. {tag} — {int(u.get('kills', 0))} kills")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    settings = await ensure_bot_settings()
    if not await guard_maintenance(update, settings):
        return
    if not await economy_enabled_or_block(update):
        return
    await ensure_group(update)
    await update_group_registry(update, bot=context.bot)

    if await cooldown_guard(update, "check", 3) is None:
        return

    if not user.get("premium", False):
        await update.effective_message.reply_text("❌ This command is only for Premium users.")
        return

    target_user = await require_reply(update)
    if not target_user:
        return

    target = await ensure_user_from_id(target_user)
    until = target.get("protection_until")
    await update.effective_message.reply_text(f"🛡️ Protection until: {fmt_dt(until)}")


async def economy_toggle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    settings = await ensure_bot_settings()
    if not await guard_maintenance(update, settings):
        return
    if not is_group(update):
        await update.effective_message.reply_text("❌ This command works in groups only.")
        return

    if await cooldown_guard(update, "economy", 3) is None:
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
    await update_group_registry(update, bot=context.bot)
    await update.effective_message.reply_text(f"✅ Economy set to: {'ON' if val else 'OFF'}")

    msg = (
        "📌 EVENT: ECONOMY TOGGLE\n"
        f"• Time: {fmt_dt(now_utc())}\n"
        f"• Group: {update.effective_chat.title} ({update.effective_chat.id})\n"
        f"• By: {mention_username({'username': update.effective_user.username}, update.effective_user.id)}\n"
        f"• New State: {'ON' if val else 'OFF'}"
    )
    await log_event(context, msg)


async def broadcast_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    user_doc = await ensure_user(update)
    settings = await ensure_bot_settings()
    if not is_private(update):
        await update.effective_message.reply_text("❌ This command is available in DM only.")
        return
    if not is_superuser(settings, user_doc["user_id"]):
        await update.effective_message.reply_text("❌ Not authorized.")
        return
    if not await guard_maintenance(update, settings):
        return

    if await cooldown_guard(update, "broadcast", SETTINGS.cd_broadcast) is None:
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /broadcast_groups <text>")
        return
    text = " ".join(context.args)

    job_id = str(uuid.uuid4())
    await broadcast_jobs.insert_one(
        {
            "job_id": job_id,
            "by_user": user_doc["user_id"],
            "text": text,
            "mode": mode,
            "started_at": now_utc(),
            "finished_at": None,
            "sent_count": 0,
            "failed_count": 0,
            "status": "running",
        }
    )

    await update.effective_message.reply_text(f"📢 Broadcast queued (job: {job_id}).")

    start_log = (
        "📌 EVENT: BROADCAST START\n"
        f"• Time: {fmt_dt(now_utc())}\n"
        f"• Mode: {mode}\n"
        f"• By: {user_doc['user_id']}\n"
        f"• Job: {job_id}"
    )
    await log_event(context, start_log)

    asyncio.create_task(run_broadcast(context, job_id, mode, text))


async def run_broadcast(context: ContextTypes.DEFAULT_TYPE, job_id: str, mode: str, text: str):
    job = await broadcast_jobs.find_one({"job_id": job_id})
    if not job:
        return
    sent = 0
    failed = 0
    delay = 1.0 / max(1.0, SETTINGS.broadcast_rate_limit)

    async def send_target(chat_id: int, is_user: bool = False):
        nonlocal sent, failed
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
            sent += 1
        except Forbidden:
            failed += 1
            if is_user:
                await users.update_one({"user_id": chat_id}, {"$set": {"dm_enabled": False}})
        except BadRequest:
            failed += 1
        except RetryAfter as e:
            await asyncio.sleep(int(e.retry_after) + 1)
            try:
                await context.bot.send_message(chat_id=chat_id, text=text)
                sent += 1
            except Exception:
                failed += 1
                if is_user:
                    await users.update_one({"user_id": chat_id}, {"$set": {"dm_enabled": False}})
        except asyncio.CancelledError:
            raise
        except Exception:
            failed += 1
        await asyncio.sleep(delay)

    if mode in ("all_groups", "both"):
        cursor = groups_registry.find()
        async for grp in cursor:
            await send_target(grp["group_id"], is_user=False)

    if mode in ("all_users", "both"):
        cursor = users.find({"dm_enabled": True})
        async for usr in cursor:
            await send_target(usr["user_id"], is_user=True)

    await broadcast_jobs.update_one(
        {"job_id": job_id},
        {
            "$set": {
                "finished_at": now_utc(),
                "sent_count": sent,
                "failed_count": failed,
                "status": "done",
            }
        },
    )

    summary = (
        "📌 EVENT: BROADCAST FINISH\n"
        f"• Time: {fmt_dt(now_utc())}\n"
        f"• Mode: {mode}\n"
        f"• Job: {job_id}\n"
        f"• Sent: {sent}\n"
        f"• Failed: {failed}"
    )
    await log_event(context, summary)

    issuer_id = job.get("by_user")
    if issuer_id:
        ok = await safe_dm(context, issuer_id, f"Broadcast complete. Sent: {sent}, Failed: {failed} (job {job_id}).")
        if not ok:
            await users.update_one({"user_id": issuer_id}, {"$set": {"dm_enabled": False}})


async def broadcast_groups_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await broadcast_entry(update, context, "all_groups")


async def broadcast_users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await broadcast_entry(update, context, "all_users")


async def broadcast_all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await broadcast_entry(update, context, "both")


async def panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_doc = await ensure_user(update)
    settings = await ensure_bot_settings()
    if not is_private(update):
        await update.effective_message.reply_text("❌ Panel is available in DM only.")
        return
    if not is_superuser(settings, user_doc["user_id"]):
        await update.effective_message.reply_text("❌ Not authorized.")
        return

    keyboard = [
        [InlineKeyboardButton("Stats", callback_data="panel:stats"), InlineKeyboardButton("Sudo Users", callback_data="panel:sudo")],
        [InlineKeyboardButton("Logs Group", callback_data="panel:logs"), InlineKeyboardButton("Economy Defaults", callback_data="panel:economy")],
        [InlineKeyboardButton("Groups List", callback_data="panel:groups"), InlineKeyboardButton("Maintenance", callback_data="panel:maintenance")],
        [InlineKeyboardButton("Broadcast", callback_data="panel:broadcast"), InlineKeyboardButton("Help", callback_data="panel:help")],
    ]
    await update.effective_message.reply_text(
        "Owner Control Panel",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def panel_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    settings = await ensure_bot_settings()
    if not is_superuser(settings, query.from_user.id):
        await query.edit_message_text("❌ Not authorized.")
        return

    data = query.data or ""
    if data == "panel:stats":
        await render_stats(query)
    elif data == "panel:sudo":
        await render_sudo(query)
    elif data == "panel:logs":
        await render_logs(query)
    elif data == "panel:economy":
        await render_economy_defaults(query)
    elif data == "panel:groups":
        await render_groups_list(query, page=0)
    elif data == "panel:maintenance":
        await render_maintenance(query)
    elif data == "panel:broadcast":
        await query.edit_message_text("Use /broadcast_groups, /broadcast_users, or /broadcast_all in DM to send announcements.")
    elif data == "panel:help":
        await query.edit_message_text(
            "Shortcuts:\n"
            "• /sudo_add <user_id>\n"
            "• /sudo_remove <user_id>\n"
            "• /sudo_list\n"
            "• /set_logs <group_id>\n"
            "• /get_logs\n"
            "• /maintenance on|off\n"
            "• /broadcast_* commands"
        )
    elif data.startswith("groups:page:"):
        page = int(data.split(":")[-1])
        await render_groups_list(query, page)


async def render_stats(query):
    total_users = await users.count_documents({})
    dm_enabled_users = await users.count_documents({"dm_enabled": True})
    total_groups = await groups_registry.count_documents({})
    economy_enabled_groups = await groups.count_documents({"economy_enabled": True})
    total_tx_logs = await tx_logs.count_documents({})
    top_users = await users.find().sort("balance", -1).limit(5).to_list(length=5)

    lines = [
        "📊 Stats",
        f"• Total users: {total_users}",
        f"• DM-enabled users: {dm_enabled_users}",
        f"• Total groups: {total_groups}",
        f"• Economy enabled groups: {economy_enabled_groups}",
        f"• Total transactions: {total_tx_logs}",
        "• Top 5 richest:",
    ]
    for u in top_users:
        lines.append(f"  - {mention_username(u, u['user_id'])}: ₹{u.get('balance', 0)}")

    await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def render_sudo(query):
    settings = await ensure_bot_settings()
    sudo_list = settings.get("sudo_users", [])
    lines = ["👑 Sudo Users:"]
    lines += [f"• {uid}" for uid in sudo_list] or ["(none)"]
    await query.edit_message_text("\n".join(lines))


async def render_logs(query):
    settings = await ensure_bot_settings()
    lg = settings.get("logs_group_id")
    await query.edit_message_text(f"📝 Logs group id: {lg or 'Not set'}")


async def render_economy_defaults(query):
    await query.edit_message_text(
        f"Default economy enabled: {SETTINGS.default_economy_enabled}"
    )


async def render_groups_list(query, page: int = 0, page_size: int = 5):
    skip = page * page_size
    cursor = groups_registry.find().skip(skip).limit(page_size)
    groups_list: List[dict] = [grp async for grp in cursor]
    lines = ["📜 Groups:"]
    for grp in groups_list:
        group_state = await groups.find_one({"group_id": grp["group_id"]})
        econ = group_state.get("economy_enabled") if group_state else None
        econ_text = "ON" if econ else "OFF" if econ is not None else "Unknown"
        lines.append(f"• {grp.get('title')} ({grp['group_id']}) — Economy: {econ_text}")

    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"groups:page:{page-1}"))
    if len(groups_list) == page_size:
        buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"groups:page:{page+1}"))

    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup([buttons]) if buttons else None)


async def render_maintenance(query):
    settings = await ensure_bot_settings()
    await query.edit_message_text(
        f"Maintenance mode: {'ON' if settings.get('maintenance_mode') else 'OFF'}\nUse /maintenance on|off"
    )


async def sudo_add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    settings = await ensure_bot_settings()
    if not is_private(update):
        await update.effective_message.reply_text("❌ DM only.")
        return
    if update.effective_user.id != settings.get("owner_id"):
        await update.effective_message.reply_text("❌ Owner only.")
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /sudo_add <user_id>")
        return
    uid = parse_int_arg(context.args[0])
    if uid is None:
        await update.effective_message.reply_text("Invalid id.")
        return
    await bot_settings.update_one({"_id": "settings"}, {"$addToSet": {"sudo_users": uid}})
    await update.effective_message.reply_text("✅ Sudo user added.")


async def sudo_remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    settings = await ensure_bot_settings()
    if not is_private(update):
        await update.effective_message.reply_text("❌ DM only.")
        return
    if update.effective_user.id != settings.get("owner_id"):
        await update.effective_message.reply_text("❌ Owner only.")
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /sudo_remove <user_id>")
        return
    uid = parse_int_arg(context.args[0])
    if uid is None:
        await update.effective_message.reply_text("Invalid id.")
        return
    await bot_settings.update_one({"_id": "settings"}, {"$pull": {"sudo_users": uid}})
    await update.effective_message.reply_text("✅ Sudo user removed.")


async def sudo_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    settings = await ensure_bot_settings()
    if not is_private(update):
        await update.effective_message.reply_text("❌ DM only.")
        return
    if not is_superuser(settings, update.effective_user.id):
        await update.effective_message.reply_text("❌ Not authorized.")
        return
    sudo_list = settings.get("sudo_users", [])
    lines = ["👑 Sudo Users:"] + [str(uid) for uid in sudo_list]
    await update.effective_message.reply_text("\n".join(lines))


async def set_logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    settings = await ensure_bot_settings()
    if not is_private(update):
        await update.effective_message.reply_text("❌ DM only.")
        return
    if update.effective_user.id != settings.get("owner_id"):
        await update.effective_message.reply_text("❌ Owner only.")
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /set_logs <group_id>")
        return
    gid = parse_int_arg(context.args[0])
    if gid is None:
        await update.effective_message.reply_text("Invalid group id.")
        return
    await bot_settings.update_one({"_id": "settings"}, {"$set": {"logs_group_id": gid}})
    await update.effective_message.reply_text("✅ Logs group updated.")


async def get_logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    settings = await ensure_bot_settings()
    if not is_private(update):
        await update.effective_message.reply_text("❌ DM only.")
        return
    if not is_superuser(settings, update.effective_user.id):
        await update.effective_message.reply_text("❌ Not authorized.")
        return
    await update.effective_message.reply_text(f"Logs group: {settings.get('logs_group_id')}")


async def maintenance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    settings = await ensure_bot_settings()
    if not is_private(update):
        await update.effective_message.reply_text("❌ DM only.")
        return
    if update.effective_user.id != settings.get("owner_id"):
        await update.effective_message.reply_text("❌ Owner only.")
        return
    if not context.args or context.args[0].lower() not in ("on", "off"):
        await update.effective_message.reply_text("Usage: /maintenance on|off")
        return
    val = context.args[0].lower() == "on"
    await bot_settings.update_one({"_id": "settings"}, {"$set": {"maintenance_mode": val}})
    await update.effective_message.reply_text(f"✅ Maintenance set to {'ON' if val else 'OFF'}")


async def my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_member = update.my_chat_member
    if not chat_member:
        return
    new_status = chat_member.new_chat_member.status
    old_status = chat_member.old_chat_member.status
    chat = chat_member.chat

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await ensure_group(update)
        await update_group_registry(update, added_by=chat_member.from_user.id, bot=context.bot)
        if new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER) and old_status in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.KICKED,
        ):
            await record_added_group(update, context, chat_member.from_user.id)
        elif new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
            await record_removed_group(update, context, chat_member.from_user.id)


async def chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await my_chat_member(update, context)


async def groups_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # For owner/sudo via DM
    await panel_cmd(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # placeholder to auto-register users on any message
    await ensure_user(update)
    if is_group(update):
        await ensure_group(update)
        await update_group_registry(update, bot=context.bot)

