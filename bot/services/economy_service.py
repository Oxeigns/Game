"""Economy system operations."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import crud
from bot.db.models import TransactionType


class EconomyService:
    def __init__(self, rate_limiter):
        self.rate_limiter = rate_limiter

    async def ensure_user(self, session: AsyncSession, tg_user):
        return await crud.get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)

    async def balance(self, session: AsyncSession, tg_user):
        user = await self.ensure_user(session, tg_user)
        await session.commit()
        return user.balance

    async def daily(self, session: AsyncSession, tg_user):
        user = await self.ensure_user(session, tg_user)
        key = f"daily:{tg_user.id}"
        if not await self.rate_limiter.hit(key, 24 * 3600):
            remaining = await self.rate_limiter.remaining(key)
            raise ValueError(f"Daily already claimed. Wait {remaining/3600:.1f}h")
        reward = 250
        user.balance += reward
        user.last_daily_at = datetime.utcnow()
        await crud.add_transaction(
            session, from_id=None, to_id=user.user_id, amount=reward, tx_type=TransactionType.daily, meta={"daily": True}
        )
        await session.commit()
        return reward

    async def transfer(self, session: AsyncSession, actor, target, amount: int):
        if amount <= 0:
            raise ValueError("Amount must be positive")
        sender = await self.ensure_user(session, actor)
        recipient = await self.ensure_user(session, target)
        if sender.balance < amount:
            raise ValueError("Insufficient balance")
        sender.balance -= amount
        recipient.balance += amount
        await crud.add_transaction(
            session, from_id=sender.user_id, to_id=recipient.user_id, amount=amount, tx_type=TransactionType.transfer, meta={}
        )
        await session.commit()
        return sender.balance, recipient.balance

    async def top(self, session: AsyncSession, limit: int = 10):
        users = await crud.leaderboard_balance(session, limit)
        await session.commit()
        return users

    async def transactions(self, session: AsyncSession, tg_user, limit: int = 10):
        txs = await crud.recent_transactions(session, tg_user.id, limit)
        await session.commit()
        return txs
