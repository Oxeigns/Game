import logging
from telegram.ext import Application, CommandHandler

from config import SETTINGS
from db import ensure_indexes
from handlers import (
    start_cmd, daily_cmd, rob_cmd, kill_cmd, revive_cmd, protect_cmd, give_cmd,
    toprich_cmd, topkill_cmd, check_cmd, economy_toggle_cmd
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO
)

async def post_init(app: Application):
    await ensure_indexes()

def main():
    app = Application.builder().token(SETTINGS.bot_token).post_init(post_init).build()

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

    app.run_polling(allowed_updates=["message", "chat_member"])

if __name__ == "__main__":
    main()
