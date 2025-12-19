from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from config import get_settings

Base = declarative_base()

_settings = get_settings()
engine: AsyncEngine = create_async_engine(_settings.database_url, echo=False, future=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


aSYNC_TEST_QUERY = text("SELECT 1")


async def check_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(aSYNC_TEST_QUERY)
        return True
    except Exception:
        return False
