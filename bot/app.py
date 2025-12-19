from __future__ import annotations

import asyncio
import logging
import signal

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
)

from . import config
from .db import close_db, create_indexes, ensure_settings, init_db
from .handlers.callbacks import CALLBACKS
from .handlers.commands import COMMANDS
from .services.logging import log_event
from .services.registry import handle_join_leave
from .utils import box_card

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Exception while handling update", exc_info=context.error)
    try:
        if config.LOGS_GROUP_ID:
            await context.bot.send_message(
                config.LOGS_GROUP_ID,
                box_card("Error", ["An error occurred", str(context.error)]),
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception:
        pass
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                box_card("⚠️", ["Something went wrong. Try again.", "Next: Retry shortly"]),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass


async def my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_join_leave(update, context)
    status = update.my_chat_member.new_chat_member.status
    chat = update.effective_chat
    if status in ("member", "administrator"):
        await log_event(context, "Bot Added", update, chat.id, "Bot added to group")
    elif status in ("left", "kicked"):
        await log_event(context, "Bot Removed", update, chat.id, "Bot removed from group")


async def main():
    if not config.BOT_TOKEN or not config.MONGO_URI:
        raise RuntimeError("BOT_TOKEN and MONGO_URI required")
    init_db()
    await ensure_settings(config.OWNER_ID, config.SUDO_USERS, config.MAINTENANCE_MODE, config.LOGS_GROUP_ID)
    await create_indexes()

    application = ApplicationBuilder().token(config.BOT_TOKEN).concurrent_updates(True).build()

    for handler in COMMANDS:
        application.add_handler(handler)
    for cb in CALLBACKS:
        application.add_handler(cb)
    application.add_handler(ChatMemberHandler(my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    application.add_error_handler(error_handler)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    await stop_event.wait()

    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
