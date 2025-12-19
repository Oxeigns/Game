import enum
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from db import Base


class RelationshipType(str, enum.Enum):
    LOVER = "lover"
    SON = "son"


class RequestType(str, enum.Enum):
    KISS = "kiss"
    LOVER = "lover"
    SON = "son"


class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String(64))
    first_name = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    stats = relationship("UserGroupStats", back_populates="user", cascade="all, delete-orphan")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    title = Column(String(255))
    leaderboard_enabled = Column(Boolean, default=True, nullable=False)
    message_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    stats = relationship("UserGroupStats", back_populates="group", cascade="all, delete-orphan")
    clans = relationship("Clan", back_populates="group", cascade="all, delete-orphan")


class UserGroupStats(Base):
    __tablename__ = "user_group_stats"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    points = Column(Integer, default=0, nullable=False)
    message_count = Column(Integer, default=0, nullable=False)
    hugs = Column(Integer, default=0, nullable=False)
    kisses = Column(Integer, default=0, nullable=False)
    punches = Column(Integer, default=0, nullable=False)
    bites = Column(Integer, default=0, nullable=False)
    dares = Column(Integer, default=0, nullable=False)
    last_action_at = Column(DateTime)

    user = relationship("User", back_populates="stats")
    group = relationship("Group", back_populates="stats")
    clan_member = relationship("ClanMember", back_populates="stats", uselist=False)

    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_group"),)


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(Enum(RelationshipType), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("group_id", "user_id", "type", name="uq_relationship"),)


class RelationshipRequest(Base):
    __tablename__ = "relationship_requests"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    requester_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(Enum(RequestType), nullable=False)
    status = Column(Enum(RequestStatus), default=RequestStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("group_id", "requester_id", "target_id", "type", name="uq_request"),
    )


class Clan(Base):
    __tablename__ = "clans"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(64), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_bonus_at = Column(DateTime)

    group = relationship("Group", back_populates="clans")
    members = relationship("ClanMember", back_populates="clan", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("group_id", "name", name="uq_clan_name_group"),
        Index("idx_clan_group", "group_id"),
    )


class ClanMember(Base):
    __tablename__ = "clan_members"

    id = Column(Integer, primary_key=True)
    clan_id = Column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    stats_id = Column(Integer, ForeignKey("user_group_stats.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    clan = relationship("Clan", back_populates="members")
    stats = relationship("UserGroupStats", back_populates="clan_member")

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_member_group"),
        Index("idx_member_clan", "clan_id"),
    )


class SocialActionLog(Base):
    __tablename__ = "social_action_logs"

    id = Column(Integer, primary_key=True)
    clan_id = Column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_action_window", "clan_id", "group_id", "created_at"),
    )
