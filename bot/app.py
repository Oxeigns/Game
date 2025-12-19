import logging

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from config import SETTINGS
from db import ensure_indexes
from handlers import (
    start_cmd,
    daily_cmd,
    rob_cmd,
    kill_cmd,
    revive_cmd,
    protect_cmd,
    give_cmd,
    toprich_cmd,
    topkill_cmd,
    check_cmd,
    economy_toggle_cmd,
    broadcast_groups_cmd,
    broadcast_users_cmd,
    broadcast_all_cmd,
    panel_cmd,
    panel_router,
    sudo_add_cmd,
    sudo_remove_cmd,
    sudo_list_cmd,
    set_logs_cmd,
    get_logs_cmd,
    maintenance_cmd,
    my_chat_member,
    chat_member,
    handle_message,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)


async def post_init(app: Application):
    await ensure_indexes()


def main():
    if not SETTINGS.bot_token:
        raise SystemExit("BOT_TOKEN is not configured.")

    app = (
        Application.builder()
        .token(SETTINGS.bot_token)
        .post_init(post_init)
        .parse_mode("HTML")
        .build()
    )

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("rob", rob_cmd))
    app.add_handler(CommandHandler("kill", kill_cmd))
    app.add_handler(CommandHandler("revive", revive_cmd))
    app.add_handler(CommandHandler("protect", protect_cmd))
    app.add_handler(CommandHandler("give", give_cmd))
    app.add_handler(CommandHandler("toprich", toprich_cmd))
    app.add_handler(CommandHandler("topkill", topkill_cmd))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("economy", economy_toggle_cmd))

    app.add_handler(CommandHandler("broadcast_groups", broadcast_groups_cmd))
    app.add_handler(CommandHandler("broadcast_users", broadcast_users_cmd))
    app.add_handler(CommandHandler("broadcast_all", broadcast_all_cmd))

    app.add_handler(CommandHandler("panel", panel_cmd))
    app.add_handler(CallbackQueryHandler(panel_router, pattern="^(panel:|groups:page:)"))

    app.add_handler(CommandHandler("sudo_add", sudo_add_cmd))
    app.add_handler(CommandHandler("sudo_remove", sudo_remove_cmd))
    app.add_handler(CommandHandler("sudo_list", sudo_list_cmd))
    app.add_handler(CommandHandler("set_logs", set_logs_cmd))
    app.add_handler(CommandHandler("get_logs", get_logs_cmd))
    app.add_handler(CommandHandler("maintenance", maintenance_cmd))

    app.add_handler(MessageHandler(filters.ALL, handle_message))
    app.add_handler(CommandHandler("groups", panel_cmd))

    app.add_handler(MessageHandler(filters.StatusUpdate.MY_CHAT_MEMBER, my_chat_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.CHAT_MEMBER, chat_member))

    app.run_polling(allowed_updates=["message", "chat_member", "my_chat_member", "callback_query"])


if __name__ == "__main__":
    main()
