# UI/UX Spec & Templates

## Global Style
- Boxed monospace cards with icons: success ✅, error ❌, warning ⚠️, protection 🛡️, money 💰, gift 🎁, kill ☠️, stats 📊, admin 👑, broadcast 📣, logs 🧾.
- Format:
  ```
  ┏━━━━━━━━━━━━━━━━━━━━━━
  ┃ Title
  ┣━━━━━━━━━━━━━━━━━━━━━━
  ┃ line 1
  ┃ line 2
  ┗━━━━━━━━━━━━━━━━━━━━━━
  ```
- Include one next-step line (CTA) per message. Keep group replies under 8 lines.
- Mentions: use @username else `ID: <id>`.
- Timestamps UTC formatted as `YYYY-MM-DD HH:MM:SS UTC`.

## Inline Keyboards
- Group quick actions: Top Rich, Top Kill, Protect, Help callbacks `ui:toprich`, `ui:topkill`, `ui:protect`, `ui:help`.
- DM panel: rows = [Stats | Admin], [Broadcast | Logs], [Groups | Maintenance], [Commands | Help].
- Broadcast menu: [Groups | Users], [All | Cancel].
- Admin menu: [Sudo List | Add Sudo], [Remove Sudo | Set Logs], [Back].
- DM warning button: URL to `t.me/<bot>?start=enable`.

## Templates (boxed)
- Success samples: Daily `💰 Daily reward claimed: ₹X`, Rob `💸 A robbed B for ₹Y`, Kill `☠️ Killer killed Victim and earned ₹Z`, Give `🎁 Sender sent ₹A to Receiver (fee ₹F)`, Protect `🛡️ Protection enabled for N day(s)`, Revive `✨ User has been revived`, Economy `✅ Economy set to: ON/OFF`, Broadcast `📣 Broadcast done...`.
- Errors: group-only, reply required, self-target, target dead/alive, target protected, insufficient balance, limit reached, cooldown `⏳ Slow down. Try again in Xs`, premium-only, admin-only, maintenance, DM disabled warning.
- DM alerts: Robbed, Killed, Gift Received, Revived (include group title and actor).
- Logs: Bot added/removed, /start DM, broadcast start/finish, economy toggle, maintenance toggle with UTC time and IDs.

## Helpers (PTB v20+ snippets)
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter, BadRequest, Forbidden, NetworkError
from telegram.ext import ContextTypes
from datetime import datetime
import asyncio

def box_card(title: str, lines: list[str]) -> str:
    lines = [ln.replace('`','"')[:48] for ln in lines]
    body = "\n".join(["┃ " + ln for ln in lines])
    return f"```\n┏━━━━━━━━━━━━━━━━━━━━━━\n┃ {title}\n┣━━━━━━━━━━━━━━━━━━━━━━\n{body}\n┗━━━━━━━━━━━━━━━━━━━━━━\n```"

def format_time_utc(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

def format_money(amount: int) -> str:
    return f"₹{amount:,}"

async def safe_reply(update, context: ContextTypes.DEFAULT_TYPE, text: str, keyboard=None, edit=False):
    try:
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
    except RetryAfter as e:
        await asyncio.sleep(min(e.retry_after, 5))
        try:
            if edit and update.callback_query:
                await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
            else:
                await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
        except Exception:
            pass
    except (BadRequest, Forbidden, NetworkError):
        pass

async def dm_warning(update, context, bot_username: str):
    btn = InlineKeyboardMarkup([[InlineKeyboardButton('✅ Enable DM', url=f'https://t.me/{bot_username}?start=enable')]])
    await safe_reply(update, context, box_card('DM Needed', ["ℹ️ Can't DM user. Ask them to /start in DM.", 'Next: Tap Enable DM']), btn)
```

## Hardening Checklist
- Add global `Application.add_error_handler` to log and respond with friendly warning.
- Catch `RetryAfter` with capped sleep; continue on `Forbidden/BadRequest/NetworkError`.
- Enforce cooldown per user per command; validate reply/amount/admin/premium/group/maintenance before action.
- Atomic Mongo updates with `$inc` + conditional guards for balances; never allow negative balances.
- For DMs, skip when `dm_enabled` is false; if DM fails, set `dm_enabled=false`.
- Always `answer_callback_query` and validate callback payload version; ignore unknown payloads.
- Limit broadcast text length (<3500 chars) and throttle (>=0.05s) with RetryAfter handling.
- Escape user-provided text in boxes; avoid Markdown injection by replacing backticks.
- Keep group messages concise (≤8 lines) and include clear next action/button.
