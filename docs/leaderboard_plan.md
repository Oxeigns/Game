# 6-Hour Leaderboard Broadcast System (Design)

## Goals
- Post every 6 hours in each active group with top users/clans/groups and 6h stats.
- Text-only, HTML parse mode; every line italicized; no media/borders.
- Stable scheduling in Asia/Kolkata at 00:00/06:00/12:00/18:00 with DB-backed next_run_at.

## Database Additions (SQLAlchemy models/migrations)
### Tables
- `user_stats`
  - `chat_id` BIGINT, `user_id` BIGINT, `points` INT default 0, `message_count` BIGINT default 0, `last_message_at` TIMESTAMP, `updated_at` TIMESTAMP
  - Constraint: `UNIQUE(chat_id, user_id)`
- `group_stats`
  - `chat_id` BIGINT PK, `title` TEXT NOT NULL, `total_points` BIGINT default 0, `message_count` BIGINT default 0, `active_members` INT default 0, `last_broadcast_at` TIMESTAMP, `updated_at` TIMESTAMP
- `clans`
  - `chat_id` BIGINT, `clan_id` INTEGER PK AUTOINCREMENT, `name` TEXT NOT NULL, `owner_id` BIGINT, `created_at` TIMESTAMP
  - Constraint: `UNIQUE(chat_id, name)`
- `clan_members`
  - `chat_id` BIGINT, `clan_id` INT, `user_id` BIGINT, `joined_at` TIMESTAMP
  - Constraint: `UNIQUE(chat_id, user_id)`
- `action_events`
  - `id` INTEGER PK AUTOINCREMENT, `chat_id` BIGINT, `actor_id` BIGINT, `target_id` BIGINT NULL, `action_type` TEXT NOT NULL, `created_at` TIMESTAMP NOT NULL
  - Indexes: `(chat_id, created_at)`, `(chat_id, action_type, created_at)`
- `scheduled_jobs`
  - `chat_id` BIGINT PK, `job_type` TEXT NOT NULL, `last_run_at` TIMESTAMP, `next_run_at` TIMESTAMP, `enabled` BOOLEAN default TRUE
  - Used to dedupe broadcasts per chat.

### Model Sketch (SQLAlchemy 2.0, async)
```python
class UserStat(Base):
    __tablename__ = "user_stats"
    chat_id = mapped_column(BigInteger, primary_key=True)
    user_id = mapped_column(BigInteger, primary_key=True)
    points = mapped_column(Integer, default=0, nullable=False)
    message_count = mapped_column(BigInteger, default=0, nullable=False)
    last_message_at = mapped_column(DateTime(timezone=True))
    updated_at = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

class GroupStat(Base):
    __tablename__ = "group_stats"
    chat_id = mapped_column(BigInteger, primary_key=True)
    title = mapped_column(Text, nullable=False)
    total_points = mapped_column(BigInteger, default=0, nullable=False)
    message_count = mapped_column(BigInteger, default=0, nullable=False)
    active_members = mapped_column(Integer, default=0, nullable=False)
    last_broadcast_at = mapped_column(DateTime(timezone=True))
    updated_at = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

class Clan(Base):
    __tablename__ = "clans"
    clan_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id = mapped_column(BigInteger, index=True)
    name = mapped_column(Text, nullable=False)
    owner_id = mapped_column(BigInteger)
    created_at = mapped_column(DateTime(timezone=True), default=func.now())
    __table_args__ = (UniqueConstraint("chat_id", "name"),)

class ClanMember(Base):
    __tablename__ = "clan_members"
    chat_id = mapped_column(BigInteger, index=True)
    clan_id = mapped_column(ForeignKey("clans.clan_id"), index=True)
    user_id = mapped_column(BigInteger)
    joined_at = mapped_column(DateTime(timezone=True), default=func.now())
    __table_args__ = (UniqueConstraint("chat_id", "user_id"), PrimaryKeyConstraint("chat_id", "clan_id", "user_id"))

class ActionEvent(Base):
    __tablename__ = "action_events"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id = mapped_column(BigInteger, index=True)
    actor_id = mapped_column(BigInteger, index=True)
    target_id = mapped_column(BigInteger, nullable=True)
    action_type = mapped_column(Text, nullable=False, index=True)
    created_at = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    __table_args__ = (
        Index("ix_action_events_chat_created", "chat_id", "created_at"),
        Index("ix_action_events_chat_action_created", "chat_id", "action_type", "created_at"),
    )

class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    chat_id = mapped_column(BigInteger, primary_key=True)
    job_type = mapped_column(Text, nullable=False)
    last_run_at = mapped_column(DateTime(timezone=True))
    next_run_at = mapped_column(DateTime(timezone=True))
    enabled = mapped_column(Boolean, default=True, nullable=False)
```

## Message Tracking
- Add group text handler with `content_types=types.ContentType.TEXT`.
- Ignore service/empty/bot messages; skip forwards.
- On each valid message:
  - Upsert `GroupStat` title from `chat.title or chat.username or "Untitled Group"`.
  - Increment `user_stats.message_count`, `group_stats.message_count`; set `last_message_at`.
  - Store row in rolling window table or derive counts via timestamp filtering of action log if available; minimum: keep `last_message_at` and aggregate from message log table if exists. If not, add lightweight `message_events` table mirroring `action_events` shape for 6h window counts.

### Handler Snippet
```python
@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.text)
async def track_message(message: Message, session: AsyncSession):
    if message.from_user.is_bot:
        return
    if not (message.text and message.text.strip()):
        return
    stmt = insert(UserStat).values(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        message_count=1,
        last_message_at=message.date,
    ).on_conflict_do_update(
        index_elements=[UserStat.chat_id, UserStat.user_id],
        set_={
            UserStat.message_count: UserStat.message_count + 1,
            UserStat.last_message_at: message.date,
            UserStat.updated_at: func.now(),
        },
    )
    await session.execute(stmt)
    g_stmt = insert(GroupStat).values(
        chat_id=message.chat.id,
        title=message.chat.title or message.chat.username or "Untitled Group",
        message_count=1,
    ).on_conflict_do_update(
        index_elements=[GroupStat.chat_id],
        set_={
            GroupStat.message_count: GroupStat.message_count + 1,
            GroupStat.title: message.chat.title or message.chat.username or "Untitled Group",
            GroupStat.updated_at: func.now(),
        },
    )
    await session.execute(g_stmt)
```

## Action Tracking
- Hook existing commands `/hug`, `/kiss`, `/punch`, `/bite`, `/dare` final outcome to write `ActionEvent` once per action.
- Example insert:
```python
await session.execute(
    insert(ActionEvent).values(
        chat_id=message.chat.id,
        actor_id=message.from_user.id,
        target_id=target_id,
        action_type="hug",
        created_at=message.date,
    )
)
```

## Leaderboard Querying
- Time window: `now_utc - 6 hours` to now; convert to DB timezone aware.
- Ranking rules: order by primary metric then secondary then `user_id/clan_id/chat_id` for stability.
- Example: Top users per chat
```python
window_start = datetime.utcnow() - timedelta(hours=6)
result = await session.execute(
    select(UserStat.user_id, UserStat.points, UserStat.message_count)
    .where(UserStat.chat_id == chat_id)
    .order_by(UserStat.points.desc(), UserStat.message_count.desc(), UserStat.user_id)
    .limit(10)
)
```
- Use similar query for `clans` (aggregate over members) and `group_stats` (global top across chats or limited scope as desired). Ensure empty-state fallbacks if no rows.

## Broadcast Message (HTML, italic-only)
```
<i>📊 Leaderboard Update (Every 6 Hours)</i>
<i>🕒 Window: Last 6 hours</i>
<i></i>
<i>🏆 Top Users</i>
<i>{top_users_rows or "• Not enough data yet."}</i>
<i></i>
<i>🏰 Top Clans</i>
<i>{top_clans_rows or "• No clans yet. Create one with /createclan {name}"}</i>
<i></i>
<i>🌍 Top Groups</i>
<i>{top_groups_rows or "• No group stats yet."}</i>
<i></i>
<i>📌 Quick Stats</i>
<i>• 💬 Messages (last 6h): {messages_6h}</i>
<i>• 🔥 Top action: {top_action_name} ({top_action_count})</i>
<i>• 👑 Most active: {most_active_user}</i>
```

## Scheduler (AsyncIOScheduler or fallback loop)
- Compute next run at nearest of 00:00/06:00/12:00/18:00 Asia/Kolkata; store in `scheduled_jobs`.
- Loop every 60s: fetch jobs with `enabled` and `next_run_at <= now`. Wrap in transaction to avoid double-send; update `last_run_at=now`, `next_run_at += 6h` before sending to ensure single broadcast.
- Respect bot permissions; disable job if `Forbidden` on send.

### Pseudocode
```python
async def schedule_all(session):
    jobs = await session.execute(select(ScheduledJob).where(ScheduledJob.job_type == "leaderboard", ScheduledJob.enabled == True))
    for job in jobs.scalars():
        scheduler.add_job(run_leaderboard, "date", run_date=job.next_run_at, args=(job.chat_id,))

async def tick():
    while True:
        async with async_session() as session, session.begin():
            due_jobs = await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.job_type == "leaderboard",
                    ScheduledJob.enabled == True,
                    ScheduledJob.next_run_at <= func.now(),
                )
            )
            for job in due_jobs.scalars():
                job.last_run_at = func.now()
                job.next_run_at = job.next_run_at + timedelta(hours=6)
                await session.flush()
                asyncio.create_task(run_leaderboard(chat_id=job.chat_id))
        await asyncio.sleep(60)
```

## Commands
- `/leaderboard_on` (admins): enable job, compute next_run_at to next slot; reply `<i>✅ 6-hour leaderboard enabled in this group.</i>`
- `/leaderboard_off` (admins): set `enabled=False`; reply `<i>🛑 6-hour leaderboard disabled in this group.</i>`
- `/leaderboard_now` (admins): run broadcast immediately; reuse template.

## Edge Handling
- Enforce max 1 broadcast per 6h with DB transaction locking `scheduled_jobs` row.
- Handle empty states with defaults; ensure tie-breaking with IDs after metrics.
- Ignore bot/service/forward messages in tracking.
- If bot kicked, set `enabled=False` on `Forbidden` errors.

## Final User-Facing Copy (HTML italic)
- Enable: `<i>✅ 6-hour leaderboard enabled in this group.</i>`
- Disable: `<i>🛑 6-hour leaderboard disabled in this group.</i>`
- Now: reuse full leaderboard template; if empty: `<i>• Not enough data yet.</i>` style lines.
