from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class RequestType(enum.Enum):
    KISS = "kiss"
    LOVER = "lover"
    SON = "son"


class RequestStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


class RelationshipType(enum.Enum):
    LOVER = "lover"
    PARENT = "parent"
    CHILD = "child"


class ClanRole(enum.Enum):
    LEADER = "leader"
    CO_LEADER = "coleader"
    MEMBER = "member"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    points = Column(Integer, default=0, nullable=False)
    total_messages = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    memberships = relationship("ClanMember", back_populates="user")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    leaderboard_enabled = Column(Boolean, default=True, nullable=False)
    total_messages = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserGroup(Base):
    __tablename__ = "user_groups"
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_group"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    message_count = Column(Integer, default=0, nullable=False)

    user = relationship("User")
    group = relationship("Group")


class DailyActivity(Base):
    __tablename__ = "daily_activity"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_user_day"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day = Column(Date, nullable=False)
    count = Column(Integer, default=0, nullable=False)


class Clan(Base):
    __tablename__ = "clans"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    leader_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    coleader_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    score = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    leader = relationship("User", foreign_keys=[leader_id])
    coleader = relationship("User", foreign_keys=[coleader_id])
    members = relationship("ClanMember", back_populates="clan")
    settings = relationship("ClanSettings", back_populates="clan", uselist=False)


class ClanMember(Base):
    __tablename__ = "clan_members"
    __table_args__ = (UniqueConstraint("user_id", name="uq_clan_member_user"),)

    id = Column(Integer, primary_key=True)
    clan_id = Column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(ClanRole), default=ClanRole.MEMBER, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    clan = relationship("Clan", back_populates="members")
    user = relationship("User", back_populates="memberships")


class ClanSettings(Base):
    __tablename__ = "clan_settings"

    id = Column(Integer, primary_key=True)
    clan_id = Column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), unique=True, nullable=False)
    min_join_points = Column(Integer, default=0, nullable=False)
    leader_cooldown_until = Column(DateTime, nullable=True)

    clan = relationship("Clan", back_populates="settings")


class ClanWeeklyPoints(Base):
    __tablename__ = "weekly_clan_stats"
    __table_args__ = (UniqueConstraint("clan_id", "user_id", name="uq_weekly_clan_user"),)

    id = Column(Integer, primary_key=True)
    clan_id = Column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    weekly_points = Column(Integer, default=0, nullable=False)


class PendingRequest(Base):
    __tablename__ = "pending_requests"

    id = Column(Integer, primary_key=True)
    requester_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    type = Column(Enum(RequestType), nullable=False)
    status = Column(Enum(RequestStatus), default=RequestStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (UniqueConstraint("user_id", "target_id", "type", name="uq_relationship"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(Enum(RelationshipType), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Gift(Base):
    __tablename__ = "gifts"

    key = Column(String, primary_key=True)
    emoji = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    bonus_points = Column(Integer, default=0, nullable=False)


class GiftHistory(Base):
    __tablename__ = "gift_history"

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    gift_key = Column(String, ForeignKey("gifts.key"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


__all__ = [
    "Base",
    "User",
    "Group",
    "UserGroup",
    "DailyActivity",
    "Clan",
    "ClanMember",
    "ClanSettings",
    "ClanWeeklyPoints",
    "PendingRequest",
    "Relationship",
    "RelationshipType",
    "RequestStatus",
    "RequestType",
    "ClanRole",
    "Gift",
    "GiftHistory",
]
