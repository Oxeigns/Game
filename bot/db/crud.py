"""Database helper CRUD operations."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, Group, Warn, Transaction, TransactionType, WarnAction


async def get_or_create_user(session: AsyncSession, user_id: int, username: Optional[str], first_name: Optional[str]) -> User:
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(user_id=user_id, username=username, first_name=first_name, balance=0)
        session.add(user)
        await session.flush()
    else:
        user.username = username
        user.first_name = first_name
    return user


async def get_or_create_group(session: AsyncSession, group_id: int, title: str) -> Group:
    result = await session.execute(select(Group).where(Group.group_id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        group = Group(
            group_id=group_id,
            title=title,
        )
        session.add(group)
        await session.flush()
    else:
        group.title = title
    return group


async def add_warn(session: AsyncSession, group_id: int, user_id: int, admin_id: int, reason: str) -> Warn:
    warn = Warn(group_id=group_id, user_id=user_id, admin_id=admin_id, reason=reason)
    session.add(warn)
    await session.flush()
    return warn


async def get_warns(session: AsyncSession, group_id: int, user_id: int) -> list[Warn]:
    result = await session.execute(
        select(Warn).where(Warn.group_id == group_id, Warn.user_id == user_id).order_by(Warn.created_at.desc())
    )
    return list(result.scalars())


async def reset_warns(session: AsyncSession, group_id: int, user_id: int) -> int:
    result = await session.execute(delete(Warn).where(Warn.group_id == group_id, Warn.user_id == user_id))
    return result.rowcount or 0


async def update_balance(session: AsyncSession, user_id: int, delta: int) -> User:
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User must exist before balance update")
    user.balance += delta
    await session.flush()
    return user


async def add_transaction(
    session: AsyncSession, *, from_id: Optional[int], to_id: Optional[int], amount: int, tx_type: TransactionType, meta: dict
) -> Transaction:
    tx = Transaction(from_id=from_id, to_id=to_id, amount=amount, type=tx_type, meta_json=meta)
    session.add(tx)
    await session.flush()
    return tx


async def leaderboard_balance(session: AsyncSession, limit: int = 10) -> list[User]:
    result = await session.execute(select(User).order_by(User.balance.desc()).limit(limit))
    return list(result.scalars())


async def recent_transactions(session: AsyncSession, user_id: int, limit: int = 10) -> list[Transaction]:
    result = await session.execute(
        select(Transaction).where((Transaction.from_id == user_id) | (Transaction.to_id == user_id)).order_by(
            Transaction.created_at.desc()
        ).limit(limit)
    )
    return list(result.scalars())


async def increment_kill(session: AsyncSession, killer_id: int, victim_id: int):
    killer = await get_or_create_user(session, killer_id, None, None)
    victim = await get_or_create_user(session, victim_id, None, None)
    killer.kills += 1
    victim.deaths += 1
    await session.flush()


async def top_killers(session: AsyncSession, limit: int = 10) -> list[User]:
    result = await session.execute(select(User).order_by(User.kills.desc()).limit(limit))
    return list(result.scalars())
