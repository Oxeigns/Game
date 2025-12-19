"""Economy system operations."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import crud
from bot.db.models import TransactionType
from bot.utils.errors import BotError


class EconomyService:
    def __init__(self, rate_limiter):
        self.rate_limiter = rate_limiter

    async def ensure_user(self, session: AsyncSession, tg_user):
        return await crud.get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)

    async def balance(self, session: AsyncSession, tg_user):
        user = await self.ensure_user(session, tg_user)
        await session.commit()
        return user.balance

    async def daily(self, session: AsyncSession, tg_user, spam_limiter=None):
        user = await self.ensure_user(session, tg_user)
        now = datetime.now(timezone.utc)
        last_claim = user.last_daily_at
        if last_claim and last_claim.tzinfo is None:
            last_claim = last_claim.replace(tzinfo=timezone.utc)
        if last_claim:
            elapsed = now - last_claim
            if elapsed < timedelta(hours=24):
                remaining = timedelta(hours=24) - elapsed
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes = remainder // 60
                raise BotError(f"Daily already claimed. Wait {hours}h {minutes}m")

        limiter = spam_limiter or self.rate_limiter
        if limiter and not await limiter.hit(f"spam:daily:{tg_user.id}", 3):
            raise BotError("Too many attempts. Please slow down.")

        reward = 250
        user.balance += reward
        user.last_daily_at = now
        await crud.add_transaction(
            session, from_id=None, to_id=user.user_id, amount=reward, tx_type=TransactionType.daily, meta={"daily": True}
        )
        await session.commit()
        return reward

    async def transfer(self, session: AsyncSession, actor, target, amount: int):
        if amount <= 0:
            raise BotError("Amount must be positive")
        sender = await self.ensure_user(session, actor)
        recipient = await self.ensure_user(session, target)
        if sender.balance < amount:
            raise BotError("Insufficient balance")
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
