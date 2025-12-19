from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import get_settings
from models import Base, Gift

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    global _engine, _sessionmaker
    settings = get_settings()
    _engine = create_async_engine(settings.database_url, echo=False, future=True)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_gifts()


async def _seed_gifts() -> None:
    gifts = [
        ("rose", "🌹", 200, 0),
        ("heart", "❤️", 500, 0),
        ("yellow_rose", "💛🌹", 350, 0),
        ("chocolate", "🍫", 800, 0),
        ("teddy", "🧸", 1200, 0),
        ("crown", "👑", 2500, 0),
        ("diamond", "💎", 5000, 5),
        ("fire", "🔥", 1500, 0),
        ("star", "⭐", 1000, 0),
        ("bouquet", "💐", 2000, 0),
    ]
    async with async_session() as session:
        for key, emoji, price, bonus in gifts:
            if await session.get(Gift, key) is None:
                session.add(Gift(key=key, emoji=emoji, price=price, bonus_points=bonus))
        await session.commit()


@asynccontextmanager
def async_session() -> AsyncSession:
    if _sessionmaker is None:
        raise RuntimeError("Database not initialized")
    session = _sessionmaker()
    try:
        yield session
    finally:
        await session.close()


async def shutdown_db() -> None:
    if _engine:
        await _engine.dispose()
