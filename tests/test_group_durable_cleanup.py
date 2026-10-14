import asyncio
import sqlite3
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from cogs.pomodoro import Pomodoro, PomodoroSession
from cogs.study_groups import StudyGroup, StudyGroupCog
from database import DBHandler
from tests.test_group_controls import environment, interaction


@pytest.fixture
async def cleanup_group(tmp_path):
    db = DBHandler(str(tmp_path / "cleanup.sqlite"))
    await db.connect()
    cog, guild, people, _, text, voice = environment()
    cog.bot.db = db
    cog.bot.get_guild.return_value = guild
    manager = MagicMock()
    manager.get_permission_level = AsyncMock(return_value=3)
    cog.bot.get_cog.side_effect = {"StudyGroupCog": cog, "Manager": manager}.get
    cog._start_group_monitor = MagicMock()
    guild.me.roles = []
    guild.me.top_role.__le__.return_value = False
    role = guild.get_role(90)
    role.guild = guild
    role.name = "study-role"
    role.managed = False
    guild.fetch_roles = AsyncMock(return_value=[role])
    for channel in (text, voice):
        channel.guild = guild
        channel.permissions_for.return_value = discord.Permissions.all()
    cog.bot.fetch_channel = AsyncMock(side_effect={30: text, 40: voice}.get)
    group = StudyGroup(db, cog, 1, "cleanup", 5, 20, 5, [5, 6])
    group.guild = guild
    group.active = True
    group.text_id, group.vc_id, group.group_role_id = 30, 40, 90
    cog.active_study_groups[group.group_id] = group
    await db.save_study_group(
        {
            "group_id": group.group_id,
            "guild_id": 1,
            "name": "cleanup",
            "creator_id": 5,
            "owner_id": 5,
            "member_ids": [5, 6],
            "text_id": 30,
            "vc_id": 40,
            "group_role_id": 90,
            "active": 1,
        }
    )
    yield group, cog, guild, people, text, voice, role
    await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["manual", "expiry", "empty", "inactive", "purge"])
async def test_all_end_triggers_delete_text_voice_and_role(cleanup_group, trigger):
    group, cog, guild, people, text, voice, role = cleanup_group
    group_id = group.group_id
    if trigger == "manual":
        assert await group.end_group(delay=0)
    elif trigger == "purge":
        await cog.purge_groups.callback(cog, interaction(cog.bot, guild, people[5]))
    else:
        if trigger == "expiry":
            group.end_time = 0
        elif trigger == "empty":
            group.member_ids.clear()
        else:
            group.active = False

        async def end(**kwargs):
            assert kwargs.get("delete_text_channel", True)
            return await StudyGroup.end_group(group, delay=0, **kwargs)

        group.end_group = end
        await group.check_end_condition()
    for resource in (text, voice, role):
        resource.delete.assert_awaited_once()
    assert (await group.db.fetch_study_group_by_id(group_id))["active"] == 0
    assert not await group.db.fetch_members_of_group(group_id)
    assert not await group.db.get_pending_cleanups(1)
    assert group.ended and group_id not in cog.active_study_groups


@pytest.mark.asyncio
async def test_cache_misses_fetch_all_resource_types(cleanup_group):
    group, _, guild, _, text, voice, role = cleanup_group
    guild.get_channel.side_effect = None
    guild.get_channel.return_value = None
    guild.get_role.return_value = None
    assert await group.end_group(delay=0)
    assert group.bot.fetch_channel.await_count == 2
    guild.fetch_roles.assert_awaited_once()
    for resource in (text, voice, role):
        resource.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_pending_cleanup_accepts_legacy_provisioning_types(cleanup_group):
    group, cog, guild, _, text, voice, _ = cleanup_group
    await group.db.retire_study_group_for_cleanup(guild.id, group.group_id)
    for item in await group.db.get_pending_cleanups(guild.id):
        await group.db.delete_pending_cleanup(item["id"])
    for kind, resource_id in (("text", text.id), ("voice", voice.id), ("mystery", 99)):
        await group.db.record_pending_cleanup(guild.id, group.group_id, kind, resource_id)

    summary = await cog.process_pending_cleanups(guild)

    assert summary["resolved"] == 2
    assert summary["failed"] == 1
    assert [(item["resource_type"], item["resource_id"]) for item in await group.db.get_pending_cleanups(guild.id)] == [
        ("mystery", 99)
    ]
    text.delete.assert_awaited_once()
    voice.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_rollback_provisioning_persists_executor_resource_types(cleanup_group):
    group, _, guild, _, text, voice, _ = cleanup_group
    text.delete.side_effect = discord.Forbidden(MagicMock(status=403), "denied")
    voice.delete.side_effect = discord.Forbidden(MagicMock(status=403), "denied")

    await group.rollback_provisioning()

    assert {item["resource_id"]: item["resource_type"] for item in await group.db.get_pending_cleanups(guild.id)} == {
        text.id: "text_channel",
        voice.id: "voice_channel",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("lookup", ["empty_channel", "missing_role_inventory"])
async def test_uncertain_rest_lookup_keeps_obligations(cleanup_group, lookup):
    group, _, guild, _, text, _, role = cleanup_group
    if lookup == "empty_channel":
        guild.get_channel.side_effect = None
        guild.get_channel.return_value = None
        group.bot.fetch_channel.return_value = None
        group.bot.fetch_channel.side_effect = None
        protected = text
    else:
        guild.get_role.return_value = None
        guild.fetch_roles.side_effect = discord.NotFound(MagicMock(status=404), "guild unavailable")
        protected = role
    assert await group.end_group(delay=0)
    protected.delete.assert_not_awaited()
    assert await group.db.get_pending_cleanups(1)


@pytest.mark.asyncio
async def test_forbidden_countdown_does_not_abandon_durable_ending(cleanup_group):
    group, _, _, _, text, _, _ = cleanup_group
    text.send.side_effect = discord.Forbidden(MagicMock(status=403), "countdown denied")
    with patch("cogs.study_groups.asyncio.sleep", AsyncMock()):
        assert await group.end_group(delay=1)
    text.delete.assert_awaited_once()
    assert not await group.db.get_pending_cleanups(1)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["insert", "retire", "conflict"])
async def test_queue_transaction_failure_preserves_active_retry_owner(cleanup_group, failure):
    group, cog, _, _, text, voice, role = cleanup_group
    group_id = group.group_id
    if failure == "conflict":
        await group.db.record_pending_cleanup(2, "foreign", "voice_channel", 40)
    else:
        statement = (
            "CREATE TRIGGER fail_queue BEFORE INSERT ON pending_resource_cleanups BEGIN SELECT RAISE(ABORT, 'blocked'); END"
            if failure == "insert"
            else "CREATE TRIGGER fail_retire BEFORE UPDATE OF active ON study_groups BEGIN SELECT RAISE(ABORT, 'blocked'); END"
        )
        async with group.db.lock:
            await group.db._run_in_thread(group.db._execute_commit_sync, statement)
    assert not await group.end_group(delay=0)
    assert group.active and cog.active_study_groups[group_id] is group
    assert (await group.db.fetch_study_group_by_id(group_id))["active"] == 1
    assert not await group.db.get_pending_cleanups(1)
    for resource in (text, voice, role):
        resource.delete.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["fetch", "delete", "ack"])
async def test_failed_discord_or_ack_work_stays_durable_and_retries(cleanup_group, failure):
    group, cog, guild, _, text, _, _ = cleanup_group
    group_id = group.group_id
    error = discord.HTTPException(MagicMock(status=503), "offline")
    if failure == "fetch":
        guild.get_channel.side_effect = None
        guild.get_channel.return_value = None
        failing, attr = group.bot, "fetch_channel"
    elif failure == "delete":
        failing, attr = text, "delete"
    else:
        failing, attr = group.db, "delete_pending_cleanup"
    with patch.object(failing, attr, AsyncMock(side_effect=error)):
        assert await group.end_group(delay=0)
    assert group.ended and group_id not in cog.active_study_groups
    assert await group.db.get_pending_cleanups(1)
    assert (await group.db.fetch_study_group_by_id(group_id))["text_id"] == 30
    summary = await cog.process_pending_cleanups(guild)
    assert summary["failed"] == 0 and summary["resolved"] > 0
    assert not await group.db.get_pending_cleanups(1)


@pytest.mark.asyncio
async def test_cancellation_after_retirement_survives_restart(cleanup_group):
    group, cog, guild, _, text, _, _ = cleanup_group
    db = group.db
    started = asyncio.Event()

    async def blocked_delete(**kwargs):
        started.set()
        await asyncio.Event().wait()

    text.delete.side_effect = blocked_delete
    task = asyncio.create_task(group.end_group(delay=0))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert group.ended and len(await db.get_pending_cleanups(1)) == 3
    # A new cog has no group memory and processes only persisted obligations.
    restored = StudyGroupCog(cog.bot)
    await db.close()
    await db.connect()
    text.delete.side_effect = None
    assert (await restored.process_pending_cleanups(guild))["resolved"] == 3
    assert not await db.get_pending_cleanups(1)


@pytest.mark.asyncio
async def test_duplicate_end_and_notfound_acknowledge_once(cleanup_group):
    group, _, _, _, text, voice, role = cleanup_group
    missing = discord.NotFound(MagicMock(status=404), "gone")
    for resource in (text, voice, role):
        resource.delete.side_effect = missing
    assert await group.end_group(delay=0)
    assert await group.end_group(delay=0)
    for resource in (text, voice, role):
        resource.delete.assert_awaited_once()
    assert not await group.db.get_pending_cleanups(1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "protection",
    ["default_vc", "default_role", "staff", "managed", "bot_role", "active_group", "wrong_guild", "wrong_type"],
)
async def test_cleanup_preserves_protected_or_uncertain_resources(cleanup_group, protection):
    group, cog, guild, _, text, voice, role = cleanup_group
    if protection == "default_vc":
        group.db.get_default_vc = AsyncMock(return_value=40)
        protected = voice
    elif protection == "default_role":
        group.db.get_default_role = AsyncMock(return_value=90)
        protected = role
    elif protection in {"staff", "managed", "bot_role"}:
        if protection == "staff":
            role.name = "CPO Manager"
        elif protection == "managed":
            role.managed = True
        else:
            guild.me.roles = [role]
        protected = role
    elif protection == "active_group":
        await group.db.save_study_group(
            {"group_id": "other", "guild_id": 1, "name": "other", "creator_id": 7, "text_id": 30, "active": 1}
        )
        protected = text
    else:
        if protection == "wrong_guild":
            text.guild = MagicMock(id=2)
        else:
            guild.get_channel.side_effect = {30: voice, 40: voice}.get
        protected = text
    assert await group.end_group(delay=0)
    protected.delete.assert_not_awaited()
    assert await group.db.get_pending_cleanups(1)
    assert (await cog.process_pending_cleanups(guild))["failed"] >= 1


@pytest.mark.asyncio
async def test_failed_final_accounting_keeps_all_cleanup_unstarted(cleanup_group):
    group, cog, _, _, text, voice, role = cleanup_group
    pomo = Pomodoro(group.bot)
    session = PomodoroSession(group.group_id, 25, 5, 15, guild_id=1, owner_id=5)
    session.focus_seconds = {5: 10}
    pomo.sessions[group.group_id] = session
    group.bot.get_cog.side_effect = {"StudyGroupCog": cog, "Pomodoro": pomo}.get
    with patch.object(
        group.db, "save_productivity_focus_time", AsyncMock(side_effect=sqlite3.OperationalError("busy"))
    ):
        assert not await group.end_group(delay=0)
    assert group.active and session.runtime_active and session in pomo.sessions.values()
    assert not await group.db.get_pending_cleanups(1)
    for resource in (text, voice, role):
        resource.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_mixed_purge_reports_pending_and_failed_and_retains_failed_group(cleanup_group):
    group, cog, guild, people, text, _, _ = cleanup_group
    await group.db.save_study_group(
        {"group_id": "failed", "guild_id": 1, "name": "failed", "creator_id": 7, "text_id": 31, "active": 1}
    )
    text.delete.side_effect = discord.Forbidden(MagicMock(status=403), "denied")
    original = group.db.retire_study_group_for_cleanup

    async def retire(guild_id, group_id):
        if group_id == "failed":
            raise sqlite3.OperationalError("busy")
        await original(guild_id, group_id)

    request = interaction(cog.bot, guild, people[5])
    with patch.object(group.db, "retire_study_group_for_cleanup", side_effect=retire):
        await cog.purge_groups.callback(cog, request)
    assert "completed 0; cleanup pending 1; failed 1" in str(request.followup.send.call_args_list)
    assert "failed" in cog.active_study_groups and cog.active_study_groups["failed"].active
    cog._start_group_monitor.assert_called_once_with(cog.active_study_groups["failed"])


@pytest.mark.asyncio
async def test_persisted_runtime_missing_from_memory_is_accounted_before_retirement(cleanup_group):
    group, cog, _, _, _, _, _ = cleanup_group
    pomo = Pomodoro(group.bot)
    session = PomodoroSession(group.group_id, 25, 5, 15, guild_id=1, owner_id=5)
    session.focus_seconds = {5: 90}
    await group.db.save_pomodoro_runtime(group.group_id, group.group_id, 1, pomo._runtime_state(session))
    group.bot.get_cog.side_effect = {"StudyGroupCog": cog, "Pomodoro": pomo}.get
    assert not pomo.sessions
    assert await group.end_group(delay=0)
    assert await group.db.get_productivity_focus_seconds(5, 1) == 90
    assert not await group.db.get_active_pomodoro_runtime()


@pytest.mark.asyncio
@pytest.mark.parametrize("text_id", [0, 30])
async def test_missing_or_shared_text_channel_does_not_own_unrelated_checkins(cleanup_group, text_id):
    group, cog, _, _, _, _, _ = cleanup_group
    group.text_id = text_id
    await group.db.update_study_group_by_id({"group_id": group.group_id, "text_id": text_id})
    if text_id:
        await group.db.save_study_group(
            {"group_id": "other", "guild_id": 1, "name": "other", "creator_id": 8, "text_id": text_id, "active": 1}
        )
    await group.db.save_checkin_session(
        {
            "session_id": "unrelated",
            "guild_id": 1,
            "name": "unrelated",
            "creator_id": 8,
            "owner_id": 8,
            "text_id": text_id,
            "duration": 3600,
            "start_time": 0,
            "last_reminder_time": 0,
            "next_reminder_time": 0,
            "reminder_count": 0,
            "last_reminder_message_id": 0,
            "active": 1,
        }
    )
    session = SimpleNamespace(
        guild_id=1,
        text_id=text_id,
        session_id="unrelated",
        join_lock=asyncio.Lock(),
        end_session_event=asyncio.Event(),
        member_ids=[8],
        member_statuses={8: {}},
    )
    checkin = SimpleNamespace(active_sessions={"unrelated": session})
    group.bot.get_cog.side_effect = {"StudyGroupCog": cog, "CheckinCog": checkin}.get
    assert await group.end_group(delay=0)
    assert await group.db.fetch_checkin_session("unrelated") is not None
    assert checkin.active_sessions["unrelated"] is session
    assert session.member_ids == [8] and not session.end_session_event.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["write", "tracking_conflict"])
async def test_durable_runtime_accounting_failure_preserves_retirement_and_resources(cleanup_group, failure):
    group, _, _, _, text, voice, role = cleanup_group
    group_id = group.group_id
    pomo = Pomodoro(group.bot)
    session = PomodoroSession(group_id, 25, 5, 15, guild_id=1, owner_id=5)
    session.focus_seconds = {5: 90}
    await group.db.save_pomodoro_runtime(group_id, group_id, 1, pomo._runtime_state(session))
    if failure == "write":
        async with group.db.lock:
            await group.db._run_in_thread(
                group.db._execute_commit_sync,
                "CREATE TRIGGER reject_focus BEFORE INSERT ON productivity_focus_time BEGIN SELECT RAISE(ABORT, 'blocked'); END",
            )
    else:
        await group.db.save_productivity_focus_time(session.tracking_id, 2, "foreign", {5: 120})
    assert not await group.end_group(delay=0)
    assert group.active and (await group.db.fetch_study_group_by_id(group_id))["active"] == 1
    assert len(await group.db.get_active_pomodoro_runtime()) == 1
    assert not await group.db.get_pending_cleanups(1)
    assert await group.db.get_productivity_focus_seconds(5, 1) == 0
    for resource in (text, voice, role):
        resource.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancelled_retirement_worker_finishes_memory_transfer_and_retains_queue(cleanup_group):
    group, cog, _, _, _, _, _ = cleanup_group
    group_id = group.group_id
    started, release = threading.Event(), threading.Event()
    run_in_thread = group.db._run_in_thread

    async def gated_worker(func, *args):
        if func.__qualname__ != "DBHandler.retire_study_group_for_cleanup.<locals>._sync":
            return await run_in_thread(func, *args)

        def blocked_worker():
            started.set()
            if not release.wait(timeout=5):
                raise RuntimeError("test worker was not released")
            return func(*args)

        return await run_in_thread(blocked_worker)

    with patch.object(group.db, "_run_in_thread", side_effect=gated_worker):
        task = asyncio.create_task(group.end_group(delay=0))
        try:
            assert await asyncio.to_thread(started.wait, 5)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    assert group.ended and not group.active and group_id not in cog.active_study_groups
    assert (await group.db.fetch_study_group_by_id(group_id))["active"] == 0
    assert len(await group.db.get_pending_cleanups(1)) == 3


@pytest.mark.asyncio
async def test_resource_reassigned_during_rest_lookup_is_retained(cleanup_group):
    group, _, guild, _, text, voice, _ = cleanup_group
    guild.get_channel.side_effect = None
    guild.get_channel.return_value = None

    async def fetch(channel_id):
        if channel_id == 30:
            await group.db.set_mod_log_channel(1, 30)
            return text
        return voice

    group.bot.fetch_channel.side_effect = fetch
    assert await group.end_group(delay=0)
    text.delete.assert_not_awaited()
    assert [item["resource_id"] for item in await group.db.get_pending_cleanups(1)] == [30]
