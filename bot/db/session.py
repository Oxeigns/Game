"""Database session management for async SQLAlchemy."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from bot.config import settings


class Base(DeclarativeBase):
    pass


def create_engine():
    url = make_url(settings.resolved_database_url)
    if url.drivername.startswith("sqlite") and url.database not in (None, ":memory:"):
        db_path = Path(url.database)
        # Ensure SQLite directory exists to avoid OperationalError on startup.
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(url.render_as_string(hide_password=False), echo=False, future=True)


engine = create_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
