from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, Sequence

from aiogram.types import Chat, User as TgUser
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Clan,
    ClanMember,
    ClanRole,
    ClanSettings,
    ClanWeeklyPoints,
    DailyActivity,
    Gift,
    GiftHistory,
    Group,
    PendingRequest,
    Relationship,
    RelationshipType,
    RequestStatus,
    RequestType,
    User,
    UserGroup,
)
from utils import consecutive_streak


async def get_or_create_user(session: AsyncSession, user: TgUser) -> User:
    result = await session.execute(select(User).where(User.telegram_id == user.id))
    db_user = result.scalar_one_or_none()
    if db_user:
        db_user.username = user.username
        db_user.first_name = user.first_name
        db_user.last_name = user.last_name
        return db_user
    db_user = User(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    session.add(db_user)
    await session.flush()
    return db_user


async def get_or_create_group(session: AsyncSession, chat: Chat) -> Group:
    result = await session.execute(select(Group).where(Group.telegram_id == chat.id))
    group = result.scalar_one_or_none()
    if group:
        group.title = chat.title or group.title
        return group
    group = Group(telegram_id=chat.id, title=chat.title or "Group")
    session.add(group)
    await session.flush()
    return group


async def ensure_participants(session: AsyncSession, actor: TgUser, chat: Chat, target: TgUser | None = None):
    user_db = await get_or_create_user(session, actor)
    group_db = await get_or_create_group(session, chat)
    await ensure_user_group(session, user_db, group_db)
    target_db = None
    if target:
        target_db = await get_or_create_user(session, target)
        await ensure_user_group(session, target_db, group_db)
    await session.flush()
    return user_db, target_db, group_db


async def ensure_user_group(session: AsyncSession, user: User, group: Group) -> UserGroup:
    result = await session.execute(
        select(UserGroup).where(UserGroup.user_id == user.id, UserGroup.group_id == group.id)
    )
    ug = result.scalar_one_or_none()
    if ug:
        return ug
    ug = UserGroup(user_id=user.id, group_id=group.id)
    session.add(ug)
    await session.flush()
    return ug


async def adjust_points(session: AsyncSession, user: User, delta: int) -> None:
    user.points += delta
    await session.flush()
    membership = await session.execute(select(ClanMember).where(ClanMember.user_id == user.id))
    member = membership.scalar_one_or_none()
    if member:
        clan = await session.get(Clan, member.clan_id)
        if clan:
            clan.score += delta
            await session.flush()
            weekly = await session.execute(
                select(ClanWeeklyPoints).where(
                    ClanWeeklyPoints.clan_id == clan.id, ClanWeeklyPoints.user_id == user.id
                )
            )
            wp = weekly.scalar_one_or_none()
            if not wp:
                wp = ClanWeeklyPoints(clan_id=clan.id, user_id=user.id, weekly_points=0)
                session.add(wp)
            wp.weekly_points += max(delta, 0)


async def log_message(session: AsyncSession, user: User, group: Group) -> None:
    await ensure_user_group(session, user, group)
    user.total_messages += 1
    group.total_messages += 1
    await session.execute(
        update(UserGroup)
        .where(UserGroup.user_id == user.id, UserGroup.group_id == group.id)
        .values(message_count=UserGroup.message_count + 1)
    )
    today = date.today()
    result = await session.execute(
        select(DailyActivity).where(DailyActivity.user_id == user.id, DailyActivity.day == today)
    )
    activity = result.scalar_one_or_none()
    if not activity:
        activity = DailyActivity(user_id=user.id, day=today, count=0)
        session.add(activity)
    activity.count += 1


async def get_streak(session: AsyncSession, user: User) -> int:
    thirty_days_ago = date.today() - timedelta(days=60)
    result = await session.execute(
        select(DailyActivity.day).where(DailyActivity.user_id == user.id, DailyActivity.day >= thirty_days_ago)
    )
    days = [row[0] for row in result.all()]
    return consecutive_streak(days)


async def create_pending_request(
    session: AsyncSession, requester: User, target: User, group: Group, req_type: RequestType, ttl_seconds: int
) -> PendingRequest:
    await session.execute(
        update(PendingRequest)
        .where(
            PendingRequest.requester_id == requester.id,
            PendingRequest.target_id == target.id,
            PendingRequest.type == req_type,
            PendingRequest.status == RequestStatus.PENDING,
        )
        .values(status=RequestStatus.EXPIRED)
    )
    req = PendingRequest(
        requester_id=requester.id,
        target_id=target.id,
        group_id=group.id,
        type=req_type,
        status=RequestStatus.PENDING,
        expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
    )
    session.add(req)
    await session.flush()
    return req


async def resolve_request(
    session: AsyncSession, request_id: int, actor_id: int, accept: bool
) -> PendingRequest | None:
    req = await session.get(PendingRequest, request_id)
    if not req or req.status != RequestStatus.PENDING or req.expires_at < datetime.utcnow():
        if req and req.status == RequestStatus.PENDING and req.expires_at < datetime.utcnow():
            req.status = RequestStatus.EXPIRED
        return None
    if req.target_id != actor_id:
        return None
    req.status = RequestStatus.ACCEPTED if accept else RequestStatus.DECLINED
    return req


async def set_relationship(session: AsyncSession, user: User, target: User, rel_type: RelationshipType) -> None:
    try:
        session.add(Relationship(user_id=user.id, target_id=target.id, type=rel_type))
        if rel_type == RelationshipType.LOVER:
            session.add(Relationship(user_id=target.id, target_id=user.id, type=rel_type))
        elif rel_type == RelationshipType.PARENT:
            session.add(Relationship(user_id=target.id, target_id=user.id, type=RelationshipType.CHILD))
    except IntegrityError:
        await session.rollback()


async def remove_relationship(session: AsyncSession, user: User, target: User, rel_type: RelationshipType) -> None:
    if rel_type == RelationshipType.LOVER:
        await session.execute(
            delete(Relationship).where(
                and_(
                    Relationship.type == rel_type,
                    Relationship.user_id.in_([user.id, target.id]),
                    Relationship.target_id.in_([user.id, target.id]),
                )
            )
        )
    else:
        await session.execute(
            delete(Relationship).where(
                Relationship.user_id == user.id, Relationship.target_id == target.id, Relationship.type == rel_type
            )
        )


async def get_membership(session: AsyncSession, user: User) -> ClanMember | None:
    result = await session.execute(select(ClanMember).where(ClanMember.user_id == user.id))
    return result.scalar_one_or_none()


async def create_clan(session: AsyncSession, name: str, leader: User) -> Clan:
    clan = Clan(name=name, leader_id=leader.id, score=leader.points)
    session.add(clan)
    await session.flush()
    settings = ClanSettings(clan_id=clan.id, min_join_points=0)
    session.add(settings)
    session.add(ClanMember(clan_id=clan.id, user_id=leader.id, role=ClanRole.LEADER))
    return clan


async def join_clan(session: AsyncSession, user: User, clan: Clan) -> bool:
    existing = await get_membership(session, user)
    if existing:
        return False
    session.add(ClanMember(clan_id=clan.id, user_id=user.id, role=ClanRole.MEMBER))
    clan.score += user.points
    await session.flush()
    return True


async def leave_clan(session: AsyncSession, user: User) -> None:
    membership = await get_membership(session, user)
    if not membership:
        return
    clan = await session.get(Clan, membership.clan_id)
    await session.execute(delete(ClanMember).where(ClanMember.id == membership.id))
    if clan:
        clan.score -= user.points
        if clan.leader_id == user.id:
            clan.leader_id = None
        if clan.coleader_id == user.id:
            clan.coleader_id = None


async def set_coleader(session: AsyncSession, clan: Clan, user: User | None) -> None:
    clan.coleader_id = user.id if user else None
    member = await session.execute(
        select(ClanMember).where(ClanMember.user_id == user.id, ClanMember.clan_id == clan.id)
    ) if user else None
    member_obj = member.scalar_one_or_none() if member else None
    if member_obj:
        member_obj.role = ClanRole.CO_LEADER


async def set_leader_cooldown(session: AsyncSession, clan: Clan, seconds: int = 30) -> bool:
    if not clan.settings:
        settings = ClanSettings(clan_id=clan.id, min_join_points=0)
        session.add(settings)
        await session.flush()
    now = datetime.utcnow()
    if clan.settings and clan.settings.leader_cooldown_until and clan.settings.leader_cooldown_until > now:
        return False
    clan.settings.leader_cooldown_until = now + timedelta(seconds=seconds)
    return True


async def top_users_for_group(session: AsyncSession, group: Group, limit: int = 10) -> list[tuple[User, UserGroup]]:
    result = await session.execute(
        select(User, UserGroup)
        .join(UserGroup, UserGroup.user_id == User.id)
        .where(UserGroup.group_id == group.id)
        .order_by(User.points.desc(), UserGroup.message_count.desc())
        .limit(limit)
    )
    return result.all()


async def top_clans(session: AsyncSession, limit: int = 10) -> list[Clan]:
    result = await session.execute(select(Clan).order_by(Clan.score.desc()).limit(limit))
    return result.scalars().all()


async def top_groups(session: AsyncSession, limit: int = 5) -> list[Group]:
    result = await session.execute(select(Group).order_by(Group.total_messages.desc()).limit(limit))
    return result.scalars().all()


async def enabled_groups(session: AsyncSession) -> list[Group]:
    result = await session.execute(select(Group).where(Group.leaderboard_enabled.is_(True)))
    return result.scalars().all()


async def set_group_leaderboard(session: AsyncSession, group: Group, enabled: bool) -> None:
    group.leaderboard_enabled = enabled


async def get_gift(session: AsyncSession, key: str) -> Gift | None:
    return await session.get(Gift, key)


async def record_gift(
    session: AsyncSession, sender: User, receiver: User, gift: Gift, group: Group | None
) -> GiftHistory:
    entry = GiftHistory(sender_id=sender.id, receiver_id=receiver.id, gift_key=gift.key, group_id=group.id if group else None)
    session.add(entry)
    return entry


async def gift_history(session: AsyncSession, user: User, limit: int = 10) -> Sequence[GiftHistory]:
    result = await session.execute(
        select(GiftHistory)
        .where((GiftHistory.sender_id == user.id) | (GiftHistory.receiver_id == user.id))
        .order_by(GiftHistory.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def update_clan_min_points(session: AsyncSession, clan: Clan, min_points: int) -> None:
    if not clan.settings:
        settings = ClanSettings(clan_id=clan.id, min_join_points=min_points)
        session.add(settings)
    else:
        clan.settings.min_join_points = min_points


async def reset_weekly_points(session: AsyncSession, clan: Clan) -> None:
    await session.execute(
        update(ClanWeeklyPoints).where(ClanWeeklyPoints.clan_id == clan.id).values(weekly_points=0)
    )


async def clan_member_count(session: AsyncSession, clan: Clan) -> int:
    result = await session.execute(select(func.count(ClanMember.id)).where(ClanMember.clan_id == clan.id))
    return result.scalar_one()


async def clan_score(session: AsyncSession, clan: Clan) -> int:
    result = await session.execute(
        select(func.sum(User.points)).join(ClanMember, ClanMember.user_id == User.id).where(ClanMember.clan_id == clan.id)
    )
    return result.scalar_one() or 0


async def clan_by_name(session: AsyncSession, name: str) -> Clan | None:
    result = await session.execute(select(Clan).where(Clan.name.ilike(name)))
    return result.scalar_one_or_none()


async def get_clan_settings(session: AsyncSession, clan: Clan) -> ClanSettings:
    if clan.settings:
        return clan.settings
    settings = ClanSettings(clan_id=clan.id, min_join_points=0)
    session.add(settings)
    await session.flush()
    return settings


async def get_user_group_stats(session: AsyncSession, user: User, group: Group) -> UserGroup:
    return await ensure_user_group(session, user, group)

