"""Core moderation logic shared across handlers."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from aiogram.enums import ChatType
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db import crud
from bot.db.models import WarnAction
from bot.utils.errors import PermissionError


async def ensure_admin_rights(actor, target_status) -> None:
    if isinstance(target_status, (ChatMemberAdministrator, ChatMemberOwner)):
        raise PermissionError("You cannot moderate other admins.")
    if isinstance(actor, (ChatMemberOwner,)):
        return


async def warn_user(session: AsyncSession, chat, actor, target, reason: str) -> tuple[int, WarnAction]:
    group = await crud.get_or_create_group(session, chat.id, chat.title)
    await crud.get_or_create_user(session, target.id, target.username, target.first_name)
    await crud.add_warn(session, group_id=chat.id, user_id=target.id, admin_id=actor.id, reason=reason)
    warns = await crud.get_warns(session, chat.id, target.id)
    await session.commit()
    action = group.warn_action or settings.warn_action_default
    return len(warns), WarnAction(action)


async def reset_warns(session: AsyncSession, chat, target_id: int) -> int:
    count = await crud.reset_warns(session, chat.id, target_id)
    await session.commit()
    return count


async def ensure_group(session: AsyncSession, chat) -> None:
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await crud.get_or_create_group(session, chat.id, chat.title)
        await session.commit()


async def get_group_settings(session: AsyncSession, chat) -> dict:
    group = await crud.get_or_create_group(session, chat.id, chat.title)
    await session.commit()
    return {
        "max_warns": group.max_warns or settings.max_warns_default,
        "warn_action": group.warn_action or settings.warn_action_default,
        "antiflood_enabled": group.antiflood_enabled,
        "flood_limit": group.flood_limit or settings.flood_limit_default,
        "flood_window": group.flood_window or settings.flood_window_seconds,
        "welcome_enabled": group.welcome_enabled,
        "goodbye_enabled": group.goodbye_enabled,
    }
