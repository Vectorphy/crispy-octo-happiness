import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from cogs.pomodoro import Pomodoro, PomodoroSession
from database import DBHandler

GROUP_ID = "307fefda-7815-4f9b-9842-66c988fc5995"


def new_cog(bot):
    cog = Pomodoro(bot)
    cog.send_notification = AsyncMock()
    cog._update_group_gui = AsyncMock()
    running = False

    def start():
        nonlocal running
        running = True

    cog.run_timer.start = MagicMock(side_effect=start)
    cog.run_timer.is_running = MagicMock(side_effect=lambda: running)
    cog.run_timer.stop = MagicMock()
    return cog


@pytest.fixture
async def runtime():
    db = DBHandler(":memory:")
    await db.connect()
    await db.save_study_group(
        {
            "group_id": GROUP_ID,
            "guild_id": 42,
            "creator_id": 10,
            "name": "Study",
            "text_id": 100,
            "vc_id": 200,
            "member_ids": [10, 11, 14],
        }
    )
    group = await db.fetch_study_group_by_id(GROUP_ID)
    guild = MagicMock(spec=discord.Guild)
    guild.id = 42
    guild.me = MagicMock(spec=discord.Member)
    channels = {}
    for channel_id, kind in ((100, discord.TextChannel), (200, discord.VoiceChannel)):
        channel = MagicMock(spec=kind)
        channel.id = channel_id
        channel.guild = guild
        channel.permissions_for.return_value = discord.Permissions.all()
        channels[channel_id] = channel
    guild.get_channel.side_effect = channels.get
    members = {}
    for user_id in (10, 11, 14):
        member = MagicMock(spec=discord.Member)
        member.id = user_id
        member.guild = guild
        members[user_id] = member
    guild.get_member.side_effect = members.get
    bot = MagicMock()
    bot.db = db
    bot.get_guild.side_effect = lambda guild_id: guild if guild_id == 42 else None
    cog = new_cog(bot)
    session = PomodoroSession(GROUP_ID, 2, 2, 3, guild_id=42, text_id=100, vc_id=200, owner_id=10)
    session.expires_at = datetime.now(timezone.utc) + timedelta(days=2)
    cog.sessions[GROUP_ID] = session
    try:
        yield db, bot, cog, session, group, channels, members
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_real_database_recovery_preserves_paused_state_and_consent(runtime):
    db, bot, cog, session, group, _, members = runtime
    session.current_stage = "long_break"
    session.cycles = 4
    session.timer = 150
    session.is_paused = True
    session.participants = {10, 11, 12, 13}
    session.current_session_marked = {10, 12}
    session.dropped_out_members = {11, 12}
    session.absent_counts = {10: 1, 11: 4, 12: 2, 13: 0}
    session.focus_seconds = {10: 57.0, 12: 9.0}
    foreign = MagicMock(spec=discord.Member)
    foreign.guild.id = 99
    members[12] = foreign
    session.warned_deadline = session.expires_at
    session.timer_updated_at -= timedelta(hours=8)
    await cog._persist_session(session)

    restored = new_cog(bot)
    await restored.load_active_sessions_from_db()
    recovered = restored.sessions[GROUP_ID]

    assert recovered is restored.sessions[group["id"]] is restored.sessions[str(group["id"])]
    assert (recovered.current_stage, recovered.cycles, recovered.timer, recovered.is_paused) == (
        "long_break",
        4,
        150,
        True,
    )
    assert recovered.expires_at == session.expires_at and recovered.expires_at.tzinfo == timezone.utc
    assert recovered.warned_deadline == session.warned_deadline
    assert recovered.participants == {10, 11}
    assert recovered.current_session_marked == {10}
    assert recovered.dropped_out_members == {11}
    assert recovered.absent_counts == {10: 1, 11: 4}
    assert recovered.tracking_id == session.tracking_id
    assert recovered.focus_seconds == session.focus_seconds
    assert await db.get_productivity_focus_seconds(10) == 57.0


@pytest.mark.asyncio
async def test_offline_elapsed_crosses_stages_without_attendance_or_focus_credit(runtime):
    db, bot, cog, session, _, _, _ = runtime
    session.cycles = 3
    session.timer = 30
    session.timer_updated_at -= timedelta(seconds=230)
    session.current_session_marked = {10}
    session.absent_counts = {10: 1}
    session.focus_seconds = {10: 57.0}
    await cog._persist_session(session)
    restored = new_cog(bot)
    await asyncio.gather(*(restored.load_active_sessions_from_db() for _ in range(3)))
    recovered = restored.sessions[GROUP_ID]
    assert (recovered.current_stage, recovered.cycles, recovered.timer) == ("focus", 4, 100)
    assert recovered.absent_counts == {10: 1}
    assert not recovered.current_session_marked
    assert recovered.focus_seconds == {10: 57.0}
    assert await db.get_productivity_focus_seconds(10) == 57.0
    restored.run_timer.start.assert_called_once()
    await restored.load_active_sessions_from_db()
    assert restored.sessions[GROUP_ID] is recovered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"current_stage": "invalid"},
        {"focus": 1},
        {"timer": -1},
        {"timer": 121},
        {"is_paused": "false"},
        {"require_vc": 1},
        {"participants": [True]},
        {"expires_at": "2026-10-04T00:00:00"},
        {"cycles": -1},
        {"text_id": 200},
        {"focus_seconds": {"10": -1}},
        {"tracking_id": "broken"},
    ],
)
async def test_malformed_runtime_is_retired(runtime, changes):
    db, bot, cog, session, _, _, _ = runtime
    state = {**cog._runtime_state(session), **changes}
    await db.save_pomodoro_runtime(GROUP_ID, GROUP_ID, 42, state)
    restored = new_cog(bot)
    await restored.load_active_sessions_from_db()
    assert not restored.sessions
    assert await db.get_active_pomodoro_runtime() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["guild", "uuid", "text_permission", "voice_permission", "voice_missing"])
async def test_recovery_rejects_wrong_scope_and_unavailable_channels(runtime, failure):
    db, bot, cog, session, group, channels, _ = runtime
    await cog._persist_session(session)
    if failure == "guild":
        foreign = MagicMock(spec=discord.Guild)
        foreign.id = 99
        bot.get_guild.side_effect = lambda guild_id: foreign if guild_id == 99 else None
        async with db.lock:
            db.conn.execute("UPDATE pomodoro_runtime SET guild_id = ? WHERE session_key = ?", (99, GROUP_ID))
            db.conn.commit()
    elif failure == "uuid":
        async with db.lock:
            db.conn.execute(
                "UPDATE pomodoro_runtime SET group_id = ? WHERE session_key = ?", (str(group["id"]), GROUP_ID)
            )
            db.conn.commit()
    elif failure == "text_permission":
        channels[100].permissions_for.return_value = discord.Permissions.none()
    elif failure == "voice_permission":
        channels[200].permissions_for.return_value = discord.Permissions.none()
    else:
        channels.pop(200)
    restored = new_cog(bot)
    await restored.load_active_sessions_from_db()
    assert not restored.sessions
    assert await db.get_active_pomodoro_runtime() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("expired", [False, True])
async def test_retirement_is_durable_and_late_timer_save_cannot_resurrect(runtime, expired):
    db, bot, cog, session, _, _, _ = runtime
    await cog._persist_session(session)
    if expired:
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await cog.run_timer.coro(cog)
    else:
        await cog._remove_session(session)
    await cog._persist_session(session)
    restored = new_cog(bot)
    await restored.load_active_sessions_from_db()
    assert not restored.sessions and not cog.sessions
    assert await db.get_active_pomodoro_runtime() == []


@pytest.mark.asyncio
async def test_inflight_save_finishes_before_retirement(runtime, monkeypatch):
    db, _, cog, session, _, _, _ = runtime
    entered, release = asyncio.Event(), asyncio.Event()
    original = db.save_pomodoro_runtime

    async def blocked_save(*args):
        entered.set()
        await release.wait()
        await original(*args)

    monkeypatch.setattr(db, "save_pomodoro_runtime", blocked_save)
    save = asyncio.create_task(cog._persist_session(session))
    await entered.wait()
    retire = asyncio.create_task(cog._remove_session(session))
    release.set()
    await asyncio.gather(save, retire)
    assert await db.get_active_pomodoro_runtime() == []
    assert not cog.sessions


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage,paused,present,dropped,expected",
    [
        ("focus", False, True, False, 8.0),
        ("focus", True, True, False, 0.0),
        ("short_break", False, True, False, 0.0),
        ("focus", False, False, False, 0.0),
        ("focus", False, True, True, 0.0),
    ],
)
async def test_only_observed_present_focus_time_is_measured(
    runtime, monkeypatch, stage, paused, present, dropped, expected
):
    db, bot, cog, session, _, _, _ = runtime
    session.current_stage = stage
    session.is_paused = paused
    session.timer = 20
    session.current_session_marked = {10} if present else set()
    session.dropped_out_members = {10} if dropped else set()
    session.last_tick_at = 92.0
    monkeypatch.setattr("cogs.pomodoro.time.monotonic", lambda: 100.0)
    await cog.run_timer.coro(cog)
    await cog._persist_session(session)
    assert session.focus_seconds.get(10, 0.0) == expected
    assert await db.get_productivity_focus_seconds(10) == expected
    restored = new_cog(bot)
    await restored.load_active_sessions_from_db()
    await restored._persist_session(restored.sessions[GROUP_ID])
    assert await db.get_productivity_focus_seconds(10) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("all_absent", [False, True])
async def test_stage_change_and_automatic_pause_are_saved_immediately(runtime, all_absent):
    db, bot, cog, session, _, _, _ = runtime
    session.timer = 1
    session.absent_counts = {10: 3}
    session.current_session_marked = set() if all_absent else {10}
    await cog._persist_session(session)
    await cog.run_timer.coro(cog)
    state = (await db.get_active_pomodoro_runtime())[0]["state"]
    assert state["is_paused"] is all_absent
    assert state["current_stage"] == ("focus" if all_absent else "short_break")
    restored = new_cog(bot)
    await restored.load_active_sessions_from_db()
    assert restored.sessions[GROUP_ID].is_paused is all_absent
