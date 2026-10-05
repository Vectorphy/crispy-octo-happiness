import asyncio
import sqlite3
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from cogs.checkin import CheckinCog, CheckinGuildSettings
from cogs.manager import Manager, PermissionLevel
from cogs.pomodoro import Pomodoro
from database import DBHandler
from tests.test_async_lifecycle import checkin_session
from utils import complete_operation


@pytest.mark.asyncio
async def test_checkin_settings_restart_isolated_and_applied_to_current_sessions(tmp_path):
    path = str(tmp_path / "settings.sqlite")
    db = DBHandler(path)
    await db.connect()
    bot = MagicMock(db=db)
    cog, session, _ = checkin_session(bot)
    session.member_ids = [5, 6, 7]
    session.member_statuses = {user_id: {"status": "present", "absences": 0} for user_id in session.member_ids}
    await session.setup_checkin_resources()
    foreign = MagicMock(guild_id=2, max_members=10)
    foreign.join_lock = asyncio.Lock()
    cog.active_sessions["foreign"] = foreign
    settings = CheckinGuildSettings(max_members=2, max_absences=7, max_breaks=4)
    settings.whitelist_channels = [20, 20]
    settings.blacklist_roles = [90]
    await cog._commit_checkin_settings(1, settings)
    assert session.member_ids == [5, 6, 7]
    assert (session.max_members, session.max_absences, session.max_breaks) == (2, 7, 4)
    assert foreign.max_members == 10
    await cog._commit_checkin_settings(2, CheckinGuildSettings(max_members=15))
    assert (await db.get_checkin_guild_settings(1))["whitelist_channels"] == [20]
    await db.close()
    restarted = DBHandler(path)
    try:
        await restarted.connect()
        restored = CheckinCog(MagicMock(db=restarted))
        restored._start_reminders = MagicMock()
        await restored.cog_load()
        assert restored.guild_settings[1].max_members == 2
        assert restored.guild_settings[2].max_members == 15
        recovered = restored.active_sessions[session.session_id]
        assert (recovered.max_members, recovered.max_absences, recovered.max_breaks) == (2, 7, 4)
        assert recovered.member_ids == [5, 6, 7]
    finally:
        await restarted.close()


@pytest.mark.asyncio
async def test_checkin_settings_failed_write_preserves_memory_and_session_policy():
    cog, session, _ = checkin_session()
    original = CheckinGuildSettings()
    cog.guild_settings[1] = original
    cog.db.save_checkin_guild_settings.side_effect = sqlite3.OperationalError("busy")
    with pytest.raises(sqlite3.OperationalError):
        await cog._commit_checkin_settings(1, CheckinGuildSettings(max_members=2))
    assert cog.guild_settings[1] is original
    assert session.max_members == 10


@pytest.mark.asyncio
async def test_checkin_settings_cancelled_save_finishes_db_and_memory_before_cancellation():
    cog, session, _ = checkin_session()
    entered, release = asyncio.Event(), asyncio.Event()

    async def save(*args):
        entered.set()
        await release.wait()

    cog.db.save_checkin_guild_settings.side_effect = save
    task = asyncio.create_task(complete_operation(cog._commit_checkin_settings(1, CheckinGuildSettings(max_members=3))))
    await entered.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cog.guild_settings[1].max_members == session.max_members == 3


@pytest.mark.asyncio
async def test_malformed_checkin_settings_fail_closed_without_replacing_them():
    db = DBHandler(":memory:")
    await db.connect()
    try:
        async with db.lock:
            db.conn.execute(
                "INSERT INTO checkin_guild_settings (guild_id, state_json) VALUES (?, ?)", (1, '{"version":1}')
            )
            db.conn.commit()
        cog = CheckinCog(MagicMock(db=db))
        with pytest.raises(ValueError):
            await cog._get_guild_settings(1)
        assert 1 not in cog.guild_settings
        assert await db.get_checkin_guild_settings(2) is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_checkin_failed_delete_keeps_active_state_and_retry_removes_it():
    db = DBHandler(":memory:")
    await db.connect()
    cog, session, request = checkin_session(MagicMock(db=db))
    try:
        await session.setup_checkin_resources()
        real_delete = db.delete_checkin_session
        db.delete_checkin_session = AsyncMock(side_effect=sqlite3.OperationalError("busy"))
        await session._finish_end_session(request)
        assert session.session_id in cog.active_sessions
        assert not session.end_session_event.is_set()
        assert (await db.fetch_active_checkin_sessions())[0]["session_id"] == session.session_id
        db.delete_checkin_session = real_delete
        await session._finish_end_session(request)
        assert session.end_session_event.is_set()
        assert session.session_id not in cog.active_sessions
        assert await db.fetch_active_checkin_sessions() == []
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_checkin_failed_button_cleanup_cannot_leave_deleted_session_in_memory():
    cog, session, _ = checkin_session()
    session.disable_previous_buttons.side_effect = discord.Forbidden(
        MagicMock(status=403, reason="Forbidden"), "denied"
    )
    await session.clear_session_data()
    assert session.end_session_event.is_set()
    assert session.session_id not in cog.active_sessions
    assert not session.member_ids
    session.db.delete_checkin_session.assert_awaited_once_with(session.session_id)


@pytest.mark.asyncio
async def test_repeated_cancellation_drains_failed_operation_and_preserves_cancellation(caplog):
    entered, release = asyncio.Event(), asyncio.Event()

    async def fail():
        entered.set()
        await release.wait()
        raise sqlite3.OperationalError("busy")

    task = asyncio.create_task(complete_operation(fail()))
    await entered.wait()
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "Cancelled operation failed" in caplog.text


@pytest.mark.asyncio
async def test_group_creation_and_join_limits_count_only_current_guild():
    db = DBHandler(":memory:")
    await db.connect()
    try:
        for group_id, guild_id, owner in (("one", 1, 5), ("two", 2, 5), ("three", 2, 6)):
            await db.save_study_group(
                {"group_id": group_id, "guild_id": guild_id, "name": group_id, "creator_id": owner, "max_members": 3}
            )
        assert await db.add_member_to_study_group_db("three", 5)
        assert await db.get_user_created_group_count(5, 1) == 1
        assert await db.get_user_created_group_count(5, 2) == 1
        assert await db.get_user_joined_group_count(5, 1) == 1
        assert await db.get_user_joined_group_count(5, 2) == 2
        assert await db.get_user_joined_group_count(5) == 0
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_tracking_id_cannot_be_reused_for_another_guild_or_group():
    db = DBHandler(":memory:")
    await db.connect()
    try:
        await db.save_productivity_focus_time("tracking", 1, "group", {5: 60})
        for guild_id, group_id in ((2, "group"), (1, "other")):
            with pytest.raises(ValueError):
                await db.save_productivity_focus_time("tracking", guild_id, group_id, {5: 100, 6: 90})
        assert await db.get_session_productivity_focus_seconds("tracking", 1, "group") == {5: 60}
        assert await db.get_session_productivity_focus_seconds("tracking", 2, "group") == {}
        assert await db.get_productivity_focus_seconds(6, 1) == 0
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_guild_grants_legacy_and_database_level_five_never_become_global():
    db = DBHandler(":memory:")
    await db.connect()
    try:
        async with db.lock:
            db.conn.executemany(
                "INSERT INTO managers (user_id, guild_id, permission_level, grant_source) VALUES (?, ?, ?, ?)",
                [(7, None, 4, "explicit"), (8, 1, 5, "explicit")],
            )
            db.conn.commit()
        await db.add_manager(9, 1, 4)
        bot = MagicMock(db=db, bot_developer_id=5)
        bot.get_guild.return_value = None
        manager = Manager(bot)
        assert await manager.get_permission_level(1, 5) == PermissionLevel.SUPREME_COMMANDER
        assert await manager.get_permission_level(2, 5) == PermissionLevel.SUPREME_COMMANDER
        assert await manager.get_permission_level(1, 7) == PermissionLevel.REGULAR_USER
        assert await manager.get_permission_level(1, 8) == PermissionLevel.REGULAR_USER
        assert await manager.get_permission_level(1, 9) == PermissionLevel.BOT_DEVELOPER
        assert await manager.get_permission_level(2, 9) == PermissionLevel.REGULAR_USER
        with pytest.raises(ValueError):
            await db.add_manager(10, 1, 5)
        async with db.lock:
            assert db.conn.execute("SELECT COUNT(*) FROM managers WHERE guild_id IS NULL").fetchone()[0] == 1
    finally:
        await db.close()


def test_session_alias_requires_matching_guild_provenance():
    cog = Pomodoro(MagicMock(db=AsyncMock()))
    wrong = MagicMock(guild_id=2)
    cog.sessions["same"] = wrong
    assert cog._get_session({"group_id": "same", "guild_id": 1}) is None
    assert cog._get_session({"group_id": "same"}) is None
