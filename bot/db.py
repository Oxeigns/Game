import asyncio
from datetime import datetime
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from . import config

client: Optional[AsyncIOMotorClient] = None
db = None


def init_db() -> None:
    global client, db
    if client:
        return
    client = AsyncIOMotorClient(config.MONGO_URI, uuidRepresentation="standard")
    db_name = config.DB_NAME
    db = client[db_name]


def get_db():
    if db is None:
        init_db()
    return db


async def create_indexes():
    database = get_db()
    await asyncio.gather(
        database.users.create_index("user_id", unique=True),
        database.users.create_index("balance", name="balance_desc", sort=[("balance", -1)]),
        database.users.create_index("kills", name="kills_desc", sort=[("kills", -1)]),
        database.users.create_index("premium"),
        database.groups.create_index("group_id", unique=True),
        database.tx_logs.create_index("timestamp", name="ts_desc", sort=[("timestamp", -1)]),
        database.tx_logs.create_index(
            [
                ("group_id", 1),
                ("timestamp", -1),
            ]
        ),
        database.tx_logs.create_index(
            [
                ("from_user", 1),
                ("timestamp", -1),
            ]
        ),
        database.tx_logs.create_index(
            [
                ("to_user", 1),
                ("timestamp", -1),
            ]
        ),
        database.bot_settings.create_index("_id", unique=True),
        database.groups_registry.create_index("group_id", unique=True),
        database.broadcast_jobs.create_index("job_id", unique=True),
        database.broadcast_jobs.create_index("status"),
        database.broadcast_jobs.create_index("started_at", name="started_desc", sort=[("started_at", -1)]),
    )


async def ensure_settings(owner_id: int, sudo_users: list[int], maintenance: bool, logs_group_id: Optional[int]):
    database = get_db()
    await database.bot_settings.update_one(
        {"_id": "settings"},
        {
            "$setOnInsert": {
                "owner_id": owner_id,
                "sudo_users": sudo_users,
                "logs_group_id": logs_group_id,
                "maintenance_mode": maintenance,
                "created_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )


async def close_db():
    if client:
        client.close()
