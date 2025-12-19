# Telegram Group Economy Game Bot

Production-grade Telegram economy game bot built with **python-telegram-bot v21**, **Python 3.11+**, and **MongoDB (Motor async)**.

## Features
- Group-only economy actions: rob, kill, revive, protect, give, leaderboards, premium checks.
- Anti-spam cooldowns, lifetime limits, atomic balance updates (no negatives).
- Broadcast system for owner/sudo (groups, users, or both) with rate limiting and persistence.
- Owner control panel, maintenance mode, logs group, and sudo management.
- Group registry tracking and structured audit logs.

## Environment
Copy `.env.example` to `.env` and fill in the values:

```
BOT_TOKEN=your_telegram_bot_token
MONGO_URI=mongodb://localhost:27017
DB_NAME=telegram_economy_bot
OWNER_ID=123456789
SUDO_USERS=987654321,555666777
LOGS_GROUP_ID=0
DEFAULT_ECONOMY_ENABLED=true
MAINTENANCE_MODE=false
BROADCAST_RATE_PER_SEC=20
```

## Setup (local)
1. Install Python 3.11+ and MongoDB.
2. Create and activate a virtual environment.
3. Install dependencies: `pip install -r requirements.txt`.
4. Run the bot: `python app.py`.

## Production deployment (systemd example)
```
[Unit]
Description=Telegram Economy Bot
After=network.target

[Service]
WorkingDirectory=/opt/economy-bot
EnvironmentFile=/opt/economy-bot/.env
ExecStart=/opt/economy-bot/.venv/bin/python app.py
Restart=on-failure
User=botuser
Group=botuser

[Install]
WantedBy=multi-user.target
```

Reload systemd, enable and start:
```
sudo systemctl daemon-reload
sudo systemctl enable economy-bot
sudo systemctl start economy-bot
```

## MongoDB indexes
Indexes are created automatically on startup as required by the specification.

## BotFather commands
```
start - Enable DM and register yourself
panel - Open owner control panel
broadcast_groups - Broadcast to all groups
broadcast_users - Broadcast to DM-enabled users
broadcast_all - Broadcast to groups and users
daily - Claim daily reward
rob - Rob a replied user (group only)
kill - Kill a replied user (group only)
revive - Revive yourself or replied user (group only)
protect - Enable protection (group only)
give - Send coins to a replied user (group only)
toprich - Show richest users (group only)
topkill - Show top killers (group only)
check - Check protection (premium, group only)
economy - Toggle economy on/off (admins)
sudo_add - Add sudo user (owner)
sudo_remove - Remove sudo user (owner)
sudo_list - List sudo users
set_logs - Set logs group (owner)
get_logs - Get logs group
maintenance - Toggle maintenance mode
```

## Notes
- Economy commands are restricted to groups and require the economy to be enabled per group.
- DM failures automatically disable further DMs to the user to avoid spam.
- Maintenance mode locks the bot for regular users while keeping owner/sudo operations available.
