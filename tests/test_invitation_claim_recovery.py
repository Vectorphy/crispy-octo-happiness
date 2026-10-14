import asyncio
import sqlite3
import threading
import time
from unittest.mock import AsyncMock, patch

import pytest

from cogs._invitations import InvitationService, service_for
from cogs.pomodoro import Pomodoro, PomodoroInvitationView, PomodoroSession
from tests import test_p1_audit_regressions
from tests.test_group_controls import interaction

persisted_group = test_p1_audit_regressions.persisted_group


@pytest.fixture
async def pomodoro_invitation(persisted_group):
    group, people, manager = persisted_group
    cog = Pomodoro(group.bot)
    group.bot.get_cog.side_effect = {"StudyGroupCog": group.cog, "Manager": manager, "Pomodoro": cog}.get
    session = PomodoroSession(group.group_id, 25, 5, 15, guild_id=1, text_id=30, require_vc=False, owner_id=5)
    cog.sessions[group.group_id] = session
    await cog._persist_session(session, required=True)
    view = PomodoroInvitationView(cog, session, 8)
    await group.db.create_session_invitation(view.invitation_id, 1, "pomodoro", session.tracking_id, 8, 5, time.time())
    service = service_for(group.bot)
    yield group, people, cog, session, view, service
    await service.close_kind("pomodoro")


@pytest.mark.asyncio
async def test_runtime_dal_failure_and_callback_error_leave_claim_retryable(pomodoro_invitation):
    group, people, _, session, view, _ = pomodoro_invitation
    async with group.db.lock:
        await group.db._run_in_thread(
            group.db._execute_commit_sync,
            "CREATE TRIGGER reject_runtime BEFORE INSERT ON pomodoro_runtime BEGIN SELECT RAISE(ABORT, 'blocked'); END",
        )
    with patch("cogs.pomodoro.send_response", AsyncMock(side_effect=RuntimeError("reply unavailable"))):
        await view.join.callback(interaction(group.bot, group.guild, people[8]))
    assert session.participants == {5}
    assert (await group.db.get_active_pomodoro_runtime())[0]["state"]["participants"] == [5]
    assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == "pending"
    async with group.db.lock:
        await group.db._run_in_thread(group.db._execute_commit_sync, "DROP TRIGGER reject_runtime")
    await view.join.callback(interaction(group.bot, group.guild, people[8]))
    assert session.participants == {5, 8}
    assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == "accepted"


@pytest.mark.asyncio
@pytest.mark.parametrize("admitted", [False, True])
async def test_cancelled_callback_reconciles_its_own_claim(pomodoro_invitation, admitted):
    group, people, cog, session, view, service = pomodoro_invitation
    started = asyncio.Event()

    async def callback(request):
        if admitted:
            session.participants.add(8)
            await cog._persist_session(session, required=True)
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(service.act(view, interaction(group.bot, group.guild, people[8]), "join", callback))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == (
        "accepted" if admitted else "pending"
    )
    assert not service.callbacks and not service.claims


@pytest.mark.asyncio
async def test_concurrent_clicks_and_ticks_never_reset_running_callback(pomodoro_invitation):
    group, people, _, _, view, service = pomodoro_invitation
    started, release = asyncio.Event(), asyncio.Event()

    async def callback(request):
        started.set()
        await release.wait()

    request = interaction(group.bot, group.guild, people[8])
    wrapped = AsyncMock(side_effect=callback)
    task = asyncio.create_task(service.act(view, request, "join", wrapped))
    await started.wait()
    other = InvitationService(group.bot)
    await other.act(view, request, "join", wrapped)
    assert await service.tick(view)
    assert await other.tick(view)
    assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == "accepting"
    wrapped.assert_awaited_once()
    release.set()
    await task
    assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("end_state", ["pending", "expired", "invalid"])
async def test_failed_recovery_write_is_retried_without_reinvoking_callback(pomodoro_invitation, end_state):
    group, people, _, _, view, service = pomodoro_invitation
    transition = group.db.transition_session_invitation

    async def fail_recovery(guild_id, identifier, expected, desired, *, now):
        if expected == "accepting":
            raise sqlite3.OperationalError("busy")
        return await transition(guild_id, identifier, expected, desired, now=now)

    async def callback(request):
        raise RuntimeError("callback failed")

    with patch.object(group.db, "transition_session_invitation", side_effect=fail_recovery):
        await service.act(view, interaction(group.bot, group.guild, people[8]), "join", callback)
        assert view.invitation_id in service.views
        assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == "accepting"
    clock = time.time() + (601 if end_state == "expired" else 0)
    if end_state == "invalid":
        view.invitation_session.owner_id = 6
    with patch("cogs._invitations.time.time", return_value=clock):
        await service.tick(view)
    assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == end_state


@pytest.mark.asyncio
async def test_cancelled_admission_before_runtime_save_restores_persisted_membership(pomodoro_invitation):
    group, people, cog, session, view, _ = pomodoro_invitation
    await cog._runtime_lock.acquire()

    async def admission_started():
        while 8 not in session.participants:
            await asyncio.sleep(0)

    task = asyncio.create_task(view.join.callback(interaction(group.bot, group.guild, people[8])))
    try:
        await asyncio.wait_for(admission_started(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        cog._runtime_lock.release()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert session.participants == {5}
    assert (await group.db.get_active_pomodoro_runtime())[0]["state"]["participants"] == [5]
    assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == "pending"
    await view.join.callback(interaction(group.bot, group.guild, people[8]))
    assert session.participants == {5, 8}
    assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == "accepted"


@pytest.mark.asyncio
@pytest.mark.parametrize("repeated", [False, True])
async def test_cancellation_while_claim_result_is_pending_recovers_committed_claim(pomodoro_invitation, repeated):
    group, people, _, _, view, service = pomodoro_invitation
    committed, release = asyncio.Event(), asyncio.Event()
    transition = group.db.transition_session_invitation

    async def blocked_result(guild_id, identifier, expected, desired, *, now):
        result = await transition(guild_id, identifier, expected, desired, now=now)
        if expected == "pending" and desired == "accepting":
            committed.set()
            await release.wait()
        return result

    callback = AsyncMock()
    with patch.object(group.db, "transition_session_invitation", side_effect=blocked_result):
        task = asyncio.create_task(service.act(view, interaction(group.bot, group.guild, people[8]), "join", callback))
        await asyncio.wait_for(committed.wait(), timeout=5)
        task.cancel()
        if repeated:
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    callback.assert_not_awaited()
    assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == "pending"
    assert not service.claims and not service.callbacks


@pytest.mark.asyncio
@pytest.mark.parametrize("storage_fails", [False, True])
async def test_cancelled_sqlite_worker_reconciles_the_actual_admission(pomodoro_invitation, storage_fails):
    group, people, _, session, view, service = pomodoro_invitation
    if storage_fails:
        async with group.db.lock:
            await group.db._run_in_thread(
                group.db._execute_commit_sync,
                "CREATE TRIGGER reject_runtime BEFORE INSERT ON pomodoro_runtime BEGIN SELECT RAISE(ABORT, 'blocked'); END",
            )
    started, release = threading.Event(), threading.Event()
    run_in_thread = group.db._run_in_thread

    async def gated_worker(func, *args):
        if func.__qualname__ != "DBHandler.save_pomodoro_runtime.<locals>._sync":
            return await run_in_thread(func, *args)

        def blocked_worker():
            started.set()
            if not release.wait(timeout=5):
                raise RuntimeError("test worker was not released")
            return func(*args)

        return await run_in_thread(blocked_worker)

    with patch.object(group.db, "_run_in_thread", side_effect=gated_worker):
        task = asyncio.create_task(view.join.callback(interaction(group.bot, group.guild, people[8])))
        try:
            assert await asyncio.to_thread(started.wait, 5)
            task.cancel()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    expected = {5} if storage_fails else {5, 8}
    assert session.participants == expected
    assert set((await group.db.get_active_pomodoro_runtime())[0]["state"]["participants"]) == expected
    assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == (
        "pending" if storage_fails else "accepted"
    )
    assert not service.callbacks and not service.claims
