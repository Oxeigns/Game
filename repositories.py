from datetime import datetime, timedelta
from typing import Iterable, Sequence

from sqlalchemy import and_, func, select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Clan,
    ClanMember,
    Group,
    Relationship,
    RelationshipRequest,
    RelationshipType,
    RequestStatus,
    RequestType,
    SocialActionLog,
    User,
    UserGroupStats,
)


async def get_or_create_user(session: AsyncSession, telegram_user) -> User:
    stmt = select(User).where(User.telegram_id == telegram_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        return user
    user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
    )
    session.add(user)
    await session.flush()
    return user


async def get_or_create_group(session: AsyncSession, chat) -> Group:
    stmt = select(Group).where(Group.telegram_id == chat.id)
    res = await session.execute(stmt)
    group = res.scalar_one_or_none()
    if group:
        group.title = chat.title or group.title
        return group
    group = Group(telegram_id=chat.id, title=chat.title)
    session.add(group)
    await session.flush()
    return group


async def get_or_create_stats(session: AsyncSession, user: User, group: Group) -> UserGroupStats:
    stmt = select(UserGroupStats).where(
        UserGroupStats.user_id == user.id, UserGroupStats.group_id == group.id
    )
    res = await session.execute(stmt)
    stats = res.scalar_one_or_none()
    if stats:
        return stats
    stats = UserGroupStats(user_id=user.id, group_id=group.id)
    session.add(stats)
    await session.flush()
    return stats


async def increment_message_count(session: AsyncSession, user: User, group: Group) -> None:
    stats = await get_or_create_stats(session, user, group)
    stats.message_count += 1
    group.message_count += 1
    await session.flush()


async def adjust_points(session: AsyncSession, user: User, group: Group, delta: int) -> int:
    stats = await get_or_create_stats(session, user, group)
    stats.points += delta
    stats.last_action_at = datetime.utcnow()
    await session.flush()
    return stats.points


async def increment_action(session: AsyncSession, stats: UserGroupStats, field: str) -> None:
    current = getattr(stats, field, 0)
    setattr(stats, field, current + 1)
    stats.last_action_at = datetime.utcnow()
    await session.flush()


async def ensure_participants(session: AsyncSession, actor_user, chat, target_user=None):
    group = await get_or_create_group(session, chat)
    actor = await get_or_create_user(session, actor_user)
    actor_stats = await get_or_create_stats(session, actor, group)
    target_stats = None
    if target_user:
        target = await get_or_create_user(session, target_user)
        target_stats = await get_or_create_stats(session, target, group)
    else:
        target = None
    return actor, target, group, actor_stats, target_stats


async def list_top_users(session: AsyncSession, group: Group, limit: int = 10) -> Sequence[tuple[UserGroupStats, User]]:
    stmt = (
        select(UserGroupStats, User)
        .join(User, User.id == UserGroupStats.user_id)
        .where(UserGroupStats.group_id == group.id)
        .order_by(UserGroupStats.points.desc(), UserGroupStats.message_count.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    return res.all()


async def get_stats(session: AsyncSession, user: User, group: Group) -> UserGroupStats:
    return await get_or_create_stats(session, user, group)


async def upsert_relationship(session: AsyncSession, group: Group, user: User, target: User, r_type: RelationshipType) -> None:
    existing_stmt = select(Relationship).where(
        Relationship.group_id == group.id,
        Relationship.user_id == user.id,
        Relationship.type == r_type,
    )
    res = await session.execute(existing_stmt)
    rel = res.scalar_one_or_none()
    if rel:
        rel.target_user_id = target.id
        rel.created_at = datetime.utcnow()
        await session.flush()
        return
    rel = Relationship(group_id=group.id, user_id=user.id, target_user_id=target.id, type=r_type)
    session.add(rel)
    await session.flush()


async def remove_relationship(session: AsyncSession, group: Group, user: User, r_type: RelationshipType) -> bool:
    stmt = delete(Relationship).where(
        Relationship.group_id == group.id, Relationship.user_id == user.id, Relationship.type == r_type
    )
    res = await session.execute(stmt)
    return res.rowcount > 0


async def create_request(
    session: AsyncSession, group: Group, requester: User, target: User, r_type: RequestType, ttl_seconds: int
) -> RelationshipRequest:
    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=ttl_seconds)
    request = RelationshipRequest(
        group_id=group.id,
        requester_id=requester.id,
        target_id=target.id,
        type=r_type,
        status=RequestStatus.PENDING,
        created_at=now,
        expires_at=expires_at,
    )
    session.add(request)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        stmt = select(RelationshipRequest).where(
            RelationshipRequest.group_id == group.id,
            RelationshipRequest.requester_id == requester.id,
            RelationshipRequest.target_id == target.id,
            RelationshipRequest.type == r_type,
        )
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            existing.status = RequestStatus.PENDING
            existing.created_at = now
            existing.expires_at = expires_at
            await session.flush()
            return existing
        raise
    return request


async def resolve_request(
    session: AsyncSession, request_id: int, target_user_id: int, accept: bool
) -> RelationshipRequest | None:
    stmt = select(RelationshipRequest).where(RelationshipRequest.id == request_id)
    res = await session.execute(stmt)
    req = res.scalar_one_or_none()
    if not req:
        return None
    if req.target_id != target_user_id:
        return None
    if req.status != RequestStatus.PENDING:
        return req
    if req.expires_at < datetime.utcnow():
        req.status = RequestStatus.DECLINED
    else:
        req.status = RequestStatus.ACCEPTED if accept else RequestStatus.DECLINED
    await session.flush()
    return req


async def cleanup_expired_requests(session: AsyncSession) -> None:
    stmt = delete(RelationshipRequest).where(RelationshipRequest.expires_at < datetime.utcnow())
    await session.execute(stmt)


async def create_clan(session: AsyncSession, group: Group, name: str, creator_stats: UserGroupStats) -> Clan:
    clan = Clan(group_id=group.id, name=name, created_by=creator_stats.user_id)
    session.add(clan)
    await session.flush()
    member = ClanMember(clan_id=clan.id, user_id=creator_stats.user_id, group_id=group.id, stats_id=creator_stats.id)
    session.add(member)
    await session.flush()
    return clan


async def join_clan(session: AsyncSession, clan: Clan, stats: UserGroupStats) -> ClanMember:
    membership = ClanMember(clan_id=clan.id, user_id=stats.user_id, group_id=clan.group_id, stats_id=stats.id)
    session.add(membership)
    await session.flush()
    return membership


async def leave_clan(session: AsyncSession, stats: UserGroupStats) -> bool:
    stmt = delete(ClanMember).where(ClanMember.stats_id == stats.id)
    res = await session.execute(stmt)
    return res.rowcount > 0


async def get_clan_by_name(session: AsyncSession, group: Group, name: str) -> Clan | None:
    stmt = select(Clan).where(Clan.group_id == group.id, func.lower(Clan.name) == name.lower())
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_membership(session: AsyncSession, stats: UserGroupStats) -> ClanMember | None:
    stmt = select(ClanMember).where(ClanMember.stats_id == stats.id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def clan_member_count(session: AsyncSession, clan: Clan) -> int:
    stmt = select(func.count(ClanMember.id)).where(ClanMember.clan_id == clan.id)
    res = await session.execute(stmt)
    return res.scalar_one()


async def clan_score(session: AsyncSession, clan: Clan) -> int:
    stmt = (
        select(func.coalesce(func.sum(UserGroupStats.points), 0))
        .join(ClanMember, ClanMember.stats_id == UserGroupStats.id)
        .where(ClanMember.clan_id == clan.id)
    )
    res = await session.execute(stmt)
    return res.scalar_one()


async def top_clans(session: AsyncSession, group: Group, limit: int = 10) -> Sequence[tuple[Clan, int, int]]:
    stmt = (
        select(Clan, func.coalesce(func.sum(UserGroupStats.points), 0).label("score"), func.count(ClanMember.id))
        .join(ClanMember, ClanMember.clan_id == Clan.id)
        .join(UserGroupStats, UserGroupStats.id == ClanMember.stats_id)
        .where(Clan.group_id == group.id)
        .group_by(Clan.id)
        .order_by(func.coalesce(func.sum(UserGroupStats.points), 0).desc(), func.count(ClanMember.id).desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    return res.all()


async def top_groups(session: AsyncSession, limit: int = 10) -> Sequence[Group]:
    stmt = select(Group).order_by(Group.message_count.desc(), Group.updated_at.desc()).limit(limit)
    res = await session.execute(stmt)
    return [row for row in res.scalars()]


async def log_social_action(session: AsyncSession, clan: Clan, group: Group, user: User, action: str) -> None:
    entry = SocialActionLog(clan_id=clan.id, group_id=group.id, user_id=user.id, action=action)
    session.add(entry)
    await session.flush()


async def clan_bonus_due(session: AsyncSession, clan: Clan) -> bool:
    if clan.last_bonus_at and clan.last_bonus_at > datetime.utcnow() - timedelta(minutes=30):
        return False
    window_start = datetime.utcnow() - timedelta(minutes=10)
    stmt = (
        select(func.count(func.distinct(SocialActionLog.user_id)))
        .where(
            SocialActionLog.clan_id == clan.id,
            SocialActionLog.group_id == clan.group_id,
            SocialActionLog.created_at >= window_start,
        )
    )
    res = await session.execute(stmt)
    count = res.scalar_one()
    return count >= 3


async def apply_clan_bonus(session: AsyncSession, clan: Clan) -> None:
    stmt = (
        select(UserGroupStats)
        .join(ClanMember, ClanMember.stats_id == UserGroupStats.id)
        .where(ClanMember.clan_id == clan.id)
    )
    res = await session.execute(stmt)
    stats_list: Iterable[UserGroupStats] = res.scalars().all()
    for stats in stats_list:
        stats.points += 2
    clan.last_bonus_at = datetime.utcnow()
    await session.flush()


async def leaderboard_enabled_groups(session: AsyncSession) -> Sequence[Group]:
    stmt = select(Group).where(Group.leaderboard_enabled.is_(True))
    res = await session.execute(stmt)
    return res.scalars().all()


async def toggle_leaderboard(session: AsyncSession, group: Group, enabled: bool) -> None:
    group.leaderboard_enabled = enabled
    await session.flush()


async def group_stats_summary(session: AsyncSession, group: Group) -> tuple[int, int]:
    user_count_stmt = select(func.count(UserGroupStats.id)).where(UserGroupStats.group_id == group.id)
    points_stmt = select(func.coalesce(func.sum(UserGroupStats.points), 0)).where(UserGroupStats.group_id == group.id)
    user_res = await session.execute(user_count_stmt)
    points_res = await session.execute(points_stmt)
    return user_res.scalar_one(), points_res.scalar_one()
