# Premium Telegram Game + Economy + Moderation Bot

High-end aiogram v3 bot featuring moderation, antiflood, economy, combat, and mini-games with premium Unicode card UI.

## Features
- 🛡 Advanced moderation: warns, mutes, bans, purges, rule cards
- 🚫 Antiflood + filters backed by Redis fallback
- 💰 Economy with daily rewards, transfers, leaderboards, and transactions
- ⚔️ Combat mini-system: rob, kill, revive, protect, top killers
- 🎮 Mini games: truth/dare, puzzles, riddles, couples
- 🎭 Fun actions with premium cards
- 🧰 Admin panel preview card and command setup for groups/private
- JSON structured logging

## Tech Stack
- Python 3.11+, aiogram v3
- SQLAlchemy async + PostgreSQL (dev SQLite fallback)
- Redis for cooldowns/antiflood (memory fallback)
- Alembic ready models

## Quickstart
1. Copy `.env.example` to `.env` and set `BOT_TOKEN`.
2. Install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Initialize database (SQLite dev default):
   ```bash
   python -m bot.main
   ```
4. For production with Postgres/Redis, update `DATABASE_URL` and `REDIS_URL` in `.env`.

## Docker Compose
`docker-compose.yml` provisions Postgres + Redis.

## Systemd
See `systemd.service.example` for a service template.

## Data
Sample data for truth/dare/puzzles/riddles/badwords live in `bot/data/`.
