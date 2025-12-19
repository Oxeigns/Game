"""Database models for the premium bot."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class WarnAction(enum.StrEnum):
    mute = "mute"
    ban = "ban"


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[Optional[str]] = mapped_column(String(32))
    first_name: Mapped[Optional[str]] = mapped_column(String(128))
    balance: Mapped[int] = mapped_column(Integer, default=0)
    kills: Mapped[int] = mapped_column(Integer, default=0)
    deaths: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_daily_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    shield_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    warns: Mapped[list["Warn"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Group(Base):
    __tablename__ = "groups"

    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(255))
    moderation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    antiflood_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    flood_limit: Mapped[int] = mapped_column(Integer, default=6)
    flood_window: Mapped[int] = mapped_column(Integer, default=10)
    max_warns: Mapped[int] = mapped_column(Integer, default=3)
    warn_action: Mapped[str] = mapped_column(String(8), default=WarnAction.mute)
    welcome_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    goodbye_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    rules_text: Mapped[str] = mapped_column(String(4096), default="")
    locks_json: Mapped[dict] = mapped_column(JSON, default=dict)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    log_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    warns: Mapped[list["Warn"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class Warn(Base):
    __tablename__ = "warns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.group_id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    admin_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    group: Mapped[Group] = relationship(back_populates="warns")
    user: Mapped[User] = relationship(back_populates="warns")

    __table_args__ = (UniqueConstraint("id", "group_id"),)


class TransactionType(enum.StrEnum):
    daily = "daily"
    transfer = "transfer"
    reward = "reward"
    penalty = "penalty"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    to_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    amount: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(16))
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


__all__ = ["User", "Group", "Warn", "Transaction", "WarnAction", "TransactionType"]
