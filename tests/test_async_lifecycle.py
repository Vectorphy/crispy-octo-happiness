import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from bot import CPO
from cogs.checkin import CheckinCog, CheckinGuildSettings, CheckinSession
from cogs.pomodoro import Pomodoro, PomodoroSession
from cogs.study_groups import StudyGroup, StudyGroupCog
from tests.test_group_controls import environment


def checkin_session(bot=None):
    bot = bot or MagicMock(db=AsyncMock())
    cog = CheckinCog(bot)
    request = MagicMock(spec=discord.Interaction)
    request.guild.id = 1
    request.user.id = 5
    request.channel.id = 20
    request.followup = AsyncMock()
    session = CheckinSession(bot.db, cog, request, "Check-in", [5], 120, CheckinGuildSettings(request))
    cog.active_sessions[session.session_id] = session
    session.update_member_statuses = AsyncMock()
    session.send_reminder_message = AsyncMock()
    session.disable_previous_buttons = AsyncMock()
    return cog, session, request


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_mode", ["end", "cancel", "overdue"])
async def test_checkin_reminder_exit_drains_waiters_and_has_no_detached_saves(exit_mode):
    _, session, _ = checkin_session()
    baseline = set(asyncio.all_tasks())
    if exit_mode == "overdue":
        session.next_reminder_time = datetime.now().timestamp() - 1
        session.send_reminder_message.side_effect = lambda: session.end_session_event.set()
    task = asyncio.create_task(session.run_checkin_reminders())
    for _ in range(3):
        await asyncio.sleep(0)
    if exit_mode == "cancel":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        session.end_session_event.set()
        await asyncio.wait_for(task, timeout=1)
    await asyncio.sleep(0)
    assert not {value for value in asyncio.all_tasks() - baseline if not value.done()}
    assert all("active" not in call.args[0] for call in session.db.update_checkin_session.await_args_list)
    assert session.db.update_checkin_session.await_count == (1 if exit_mode == "overdue" else 0)


@pytest.mark.asyncio
async def test_manual_checkin_end_waits_for_cycle_and_runs_once():
    cog, session, request = checkin_session()
    paused = asyncio.Event()
    release = asyncio.Event()
    session.next_reminder_time = datetime.now().timestamp() - 1
    session.last_reminder_message_id = 50

    async def disable():
        paused.set()
        await release.wait()

    session.disable_previous_buttons.side_effect = disable
    reminder = asyncio.create_task(session.run_checkin_reminders())
    await paused.wait()
    endings = [asyncio.create_task(session._finish_end_session(request)) for _ in range(2)]
    await asyncio.sleep(0)
    assert all(not task.done() for task in endings)
    release.set()
    await asyncio.wait_for(asyncio.gather(reminder, *endings), timeout=1)
    assert session.session_id not in cog.active_sessions
    session.db.delete_checkin_session.assert_awaited_once_with(session.session_id)
    assert [call.args[0].get("active") for call in session.db.update_checkin_session.await_args_list] == [None]


@pytest.mark.asyncio
async def test_cancelled_old_video_timer_cannot_unregister_replacement(monkeypatch):
    cog, guild, people, category, _, voice = environment()
    group = StudyGroup(cog.bot.db, cog, 1, "group", 5, category.id, 3, [5])
    group.guild = guild
    group.active = True
    group.video_mode = "force"
    group.vc_id = voice.id
    first_sleep = asyncio.Event()
    second_sleep = asyncio.Event()
    count = 0

    async def sleep(delay):
        nonlocal count
        count += 1
        (first_sleep if count == 1 else second_sleep).set()
        await asyncio.Event().wait()

    monkeypatch.setattr("cogs.study_groups.asyncio.sleep", sleep)
    group._schedule_video_enforcement(people[5])
    old = group.video_enforcement_tasks[5]
    await first_sleep.wait()
    group._schedule_video_enforcement(people[5])
    replacement = group.video_enforcement_tasks[5]
    await second_sleep.wait()
    await old
    assert group.video_enforcement_tasks[5] is replacement
    group._cancel_video_enforcement(5)
    await replacement
    assert not group.video_enforcement_tasks
    people[5].move_to.assert_not_awaited()


@pytest.mark.asyncio
async def test_bot_shutdown_drains_cog_tasks_before_database_close_and_is_idempotent():
    bot = CPO(bot_developer_id=999)
    await bot._async_setup_hook()
    bot.db = AsyncMock()
    bot.db.fetch_active_checkin_sessions.return_value = []
    checkins, session, _ = checkin_session(bot)
    groups = StudyGroupCog(bot)
    pomodoro = Pomodoro(bot)
    runtime = PomodoroSession("group", 25, 5, 15, guild_id=1, text_id=20, require_vc=False, owner_id=5)
    pomodoro.sessions["group"] = runtime
    group = StudyGroup(bot.db, groups, 1, "group", 5, 10, 3, [5])
    group.active = True
    group.check_end_condition = AsyncMock(side_effect=asyncio.Event().wait)
    groups.active_study_groups[group.group_id] = group
    await bot.add_cog(checkins)
    await bot.add_cog(groups)
    await bot.add_cog(pomodoro)
    checkins._start_reminders(session, delay=120)
    checkins._start_reminders(session, delay=120)
    assert len(checkins._reminder_tasks) == 1
    groups._start_group_monitor(group)
    video = asyncio.create_task(asyncio.Event().wait())
    group.video_enforcement_tasks[5] = video
    pomodoro.run_timer.start()
    tasks = [
        *checkins._reminder_tasks.values(),
        *groups._monitor_tasks,
        video,
        pomodoro.run_timer.get_task(),
        groups.cleanup_retry_loop.get_task(),
    ]

    async def close_database():
        assert all(task.done() for task in tasks)
        assert runtime.runtime_active
        assert group.active
        assert session.session_id in checkins.active_sessions

    bot.db.close.side_effect = close_database
    await asyncio.gather(bot.close(), bot.close())
    await bot.close()
    bot.db.close.assert_awaited_once()
    bot.db.save_pomodoro_runtime.assert_awaited()
    bot.db.delete_checkin_session.assert_not_awaited()
    bot.db.delete_study_group.assert_not_awaited()
    assert not checkins._reminder_tasks
    assert not groups._monitor_tasks
    assert not group.video_enforcement_tasks


@pytest.mark.asyncio
async def test_cancelled_shutdown_caller_does_not_interrupt_shared_shutdown():
    bot = CPO(bot_developer_id=999)
    await bot._async_setup_hook()
    bot.db = AsyncMock()
    closing = asyncio.Event()
    release = asyncio.Event()

    async def close_database():
        closing.set()
        await release.wait()

    bot.db.close.side_effect = close_database
    caller = asyncio.create_task(bot.close())
    await closing.wait()
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert bot._shutdown_task is not None and not bot._shutdown_task.done()
    release.set()
    await asyncio.wait_for(bot.close(), timeout=1)
    bot.db.close.assert_awaited_once()
