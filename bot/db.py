import asyncio
from datetime import datetime
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure

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
    async def create_index_safe(collection, keys, **kwargs):
        try:
            return await collection.create_index(keys, **kwargs)
        except OperationFailure as exc:
            if exc.code in {68, 85, 86} or "already exists" in str(exc):
                return None
            raise

    await asyncio.gather(
        # Users
        create_index_safe(database.users, [("user_id", 1)], unique=True),
        create_index_safe(database.users, [("balance", -1)], name="balance_desc"),
        create_index_safe(database.users, [("kills", -1)], name="kills_desc"),
        create_index_safe(database.users, [("premium", 1)]),
        # Groups
        create_index_safe(database.groups, [("group_id", 1)], unique=True),
        # Transaction logs
        create_index_safe(database.tx_logs, [("timestamp", -1)], name="ts_desc"),
        create_index_safe(
            database.tx_logs,
            [
                ("group_id", 1),
                ("timestamp", -1),
            ],
        ),
        create_index_safe(
            database.tx_logs,
            [
                ("from_user", 1),
                ("timestamp", -1),
            ],
        ),
        create_index_safe(
            database.tx_logs,
            [
                ("to_user", 1),
                ("timestamp", -1),
            ],
        ),
        # Settings (uses MongoDB's built-in _id index; no manual index needed)
        create_index_safe(database.groups_registry, [("group_id", 1)], unique=True),
        # Broadcast jobs
        create_index_safe(database.broadcast_jobs, [("job_id", 1)], unique=True),
        create_index_safe(database.broadcast_jobs, [("status", 1)]),
        create_index_safe(database.broadcast_jobs, [("started_at", -1)], name="started_desc"),
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
