from motor.motor_asyncio import AsyncIOMotorClient
from config import SETTINGS

client = AsyncIOMotorClient(SETTINGS.mongo_uri)
db = client[SETTINGS.db_name]

users = db["users"]
groups = db["groups"]
tx_logs = db["tx_logs"]

async def ensure_indexes():
    # users
    await users.create_index("user_id", unique=True)
    await users.create_index("balance")
    await users.create_index("kills")
    await users.create_index("premium")

    # groups
    await groups.create_index("group_id", unique=True)

    # tx_logs
    await tx_logs.create_index([("timestamp", -1)])
    await tx_logs.create_index([("group_id", 1), ("timestamp", -1)])
    await tx_logs.create_index([("from_user", 1), ("timestamp", -1)])
    await tx_logs.create_index([("to_user", 1), ("timestamp", -1)])
