from __future__ import annotations

import asyncio

from bot.main import main as bot_main


def main():
    asyncio.run(bot_main())


if __name__ == "__main__":
    main()
