from motor.motor_asyncio import AsyncIOMotorClient

from config import SETTINGS

client = AsyncIOMotorClient(SETTINGS.mongo_uri)
db = client[SETTINGS.db_name]

users = db["users"]
groups = db["groups"]
tx_logs = db["tx_logs"]
bot_settings = db["bot_settings"]
groups_registry = db["groups_registry"]
broadcast_jobs = db["broadcast_jobs"]


async def ensure_indexes():
    # users
    await users.create_index("user_id", unique=True)
    await users.create_index([("balance", -1)])
    await users.create_index([("kills", -1)])
    await users.create_index("premium")

    # groups
    await groups.create_index("group_id", unique=True)

    # tx_logs
    await tx_logs.create_index([("timestamp", -1)])
    await tx_logs.create_index([("group_id", 1), ("timestamp", -1)])
    await tx_logs.create_index([("from_user", 1), ("timestamp", -1)])
    await tx_logs.create_index([("to_user", 1), ("timestamp", -1)])

    # bot_settings
    await bot_settings.create_index("_id", unique=True)

    # groups_registry
    await groups_registry.create_index("group_id", unique=True)

    # broadcast_jobs
    await broadcast_jobs.create_index("job_id", unique=True)
    await broadcast_jobs.create_index("status")
    await broadcast_jobs.create_index("started_at")
