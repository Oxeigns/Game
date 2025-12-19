# Telegram Group Economy Game Bot

Production-ready economy game bot for Telegram groups and DMs using **python-telegram-bot v20+**, **Motor/MongoDB**, and Python 3.11.

## Features
- Group economy gameplay: /daily, /rob, /kill, /revive, /protect, /give, /toprich, /topkill, /check, /economy.
- DM admin panel and broadcasts for owner/sudo.
- Safe DM handling, cooldowns, maintenance mode, and structured logging to a logs group.
- Deployable on Heroku (worker dyno) or VPS (systemd).

## Requirements
- Python 3.11+
- MongoDB (Atlas recommended)
- Environment variables configured (see `.env.example`).

## Setup (Local)
1. Clone the repo and create env file:
   ```bash
   cp .env.example .env
   # edit .env with BOT_TOKEN, MONGO_URI, DB_NAME, OWNER_ID, LOGS_GROUP_ID
   ```
2. Create virtual env & install:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run bot:
   ```bash
   python bot/app.py
   ```

## Heroku Deployment (Polling)
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)
1. Install Heroku CLI and login.
2. Create app and set config vars:
   ```bash
   heroku create
   heroku config:set BOT_TOKEN=<token>
   heroku config:set MONGO_URI=<mongo_uri>
   heroku config:set DB_NAME=<db_name>
   heroku config:set OWNER_ID=<owner_id>
   heroku config:set LOGS_GROUP_ID=<optional logs chat id>
   ```
3. Deploy:
   ```bash
   git add .
   git commit -m "Deploy bot"
   git push heroku work:main
   ```
4. Scale worker dyno:
   ```bash
   heroku ps:scale worker=1
   ```

## VPS Deployment (systemd + polling)
1. Install Python 3.11 and create a user `bot`.
2. Clone repo to `/opt/gamebot` and create `.env` (see example).
3. Create venv & install:
   ```bash
   cd /opt/gamebot
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. Create systemd unit `/etc/systemd/system/gamebot.service` from `systemd.service.example`, adjust paths/user.
5. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable gamebot.service
   sudo systemctl start gamebot.service
   sudo systemctl status gamebot.service
   ```
6. Logs: `journalctl -u gamebot.service -f`.

## Database Indexes
Indexes are created automatically at startup in `db.create_indexes()`:
- users: user_id (unique), balance desc, kills desc, premium
- groups: group_id (unique)
- tx_logs: timestamp desc, (group_id,timestamp), (from_user,timestamp), (to_user,timestamp)
- bot_settings: _id unique
- groups_registry: group_id unique
- broadcast_jobs: job_id unique, status, started_at desc

## Safety Notes
- Cooldowns enforced per user per command.
- DM attempts are skipped if `dm_enabled` is false; on DM failure flag is disabled.
- Broadcasts throttle at 20 msg/sec and handle RetryAfter with capped wait.
- Maintenance mode blocks all non-superuser commands.

## BotFather Commands
```
start - Enable DM notifications
daily - Claim daily reward
rob - Rob a replied user (group only)
kill - Kill a replied user (group only)
revive - Revive self or replied user
protect - Enable protection
give - Give money to replied user
toprich - Top richest users
topkill - Top killers
check - Check protection (premium only)
economy - Toggle economy on/off (admins)
panel - Owner/Sudo control panel (DM)
broadcast_groups - Broadcast to all groups (owner/sudo, DM)
broadcast_users - Broadcast to DM users (owner/sudo, DM)
broadcast_all - Broadcast to groups + users (owner/sudo, DM)
sudo_add - Add sudo user (owner, DM)
sudo_remove - Remove sudo user (owner, DM)
sudo_list - List sudo users (owner, DM)
set_logs - Set logs group id (owner, DM)
get_logs - Get logs group id (owner, DM)
maintenance - Toggle maintenance mode (owner, DM)
```

## Notes on Broadcasting & DMs
- Broadcast jobs stored in `broadcast_jobs`; failures counted and DM users auto-disabled on Forbidden.
- DM notifications only sent when `dm_enabled=true`; set via /start in DM.

## Running
`python bot/app.py`
