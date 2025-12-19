import asyncio
from typing import Sequence

from aiogram import Bot

from db import async_session
from repositories import leaderboard_enabled_groups, list_top_users, top_clans, top_groups
from utils import extract_name, format_clan_line, format_user_line, italic


async def compose_leaderboard(session, group) -> str:
    leaders = await list_top_users(session, group, limit=5)
    clans = await top_clans(session, group, limit=5)
    groups = await top_groups(session, limit=5)
    lines = ["🏆 Top Users:"]
    if leaders:
        lines += [format_user_line(idx + 1, extract_name(user), stats.points, stats.message_count) for idx, (stats, user) in enumerate(leaders)]
    else:
        lines.append("No users yet.")
    lines.append("\n🏰 Top Clans:")
    if clans:
        lines += [format_clan_line(idx + 1, clan.name, score, members) for idx, (clan, score, members) in enumerate(clans)]
    else:
        lines.append("No clans yet.")
    lines.append("\n🌍 Top Groups:")
    if groups:
        lines += [f"{idx + 1}. {g.title or 'Group'} — {g.message_count} msgs" for idx, g in enumerate(groups)]
    else:
        lines.append("No groups yet.")
    return "\n".join(lines)


async def leaderboard_scheduler(bot: Bot):
    while True:
        try:
            async with async_session() as session:
                groups = await leaderboard_enabled_groups(session)
                for group in groups:
                    text = await compose_leaderboard(session, group)
                    await bot.send_message(group.telegram_id, italic(text))
                await session.commit()
        except Exception:
            pass
        await asyncio.sleep(6 * 60 * 60)
