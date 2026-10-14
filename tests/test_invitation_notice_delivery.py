import asyncio
import sqlite3
import time
from unittest.mock import AsyncMock, patch

import pytest

from cogs._invitations import InvitationService
from cogs.study_groups import GroupInvitationView
from tests import test_p1_audit_regressions

persisted_group = test_p1_audit_regressions.persisted_group


@pytest.mark.asyncio
@pytest.mark.parametrize("expired", [False, True])
@pytest.mark.parametrize("failure", ["fetch", "send", "ack", "timeout"])
async def test_failed_notice_retains_delivery_work_and_retry_acknowledges(persisted_group, expired, failure):
    group, people, _ = persisted_group
    view = GroupInvitationView(group, 8)
    created = time.time() - (601 if expired else 400)
    await group.db.create_session_invitation(view.invitation_id, 1, "group", group.group_id, 8, 5, created)
    service = InvitationService(group.bot)
    group.bot.fetch_user = AsyncMock(return_value=people[8])
    service.views[view.invitation_id] = view
    owner, attribute = (
        (group.bot, "fetch_user")
        if failure in {"fetch", "timeout"}
        else (people[8], "send")
        if failure == "send"
        else (group.db, "mark_invitation_notification")
    )
    error = asyncio.TimeoutError() if failure == "timeout" else sqlite3.OperationalError("unavailable")
    with patch.object(owner, attribute, AsyncMock(side_effect=error)):
        assert await service.tick(view)
    saved = await group.db.get_session_invitation(1, view.invitation_id)
    field = "expiry_notified" if expired else "warned"
    assert saved[field] == 0 and view.invitation_id in service.views
    delivered_before_retry = people[8].send.await_count
    assert await service.tick(view) is (not expired)
    assert (await group.db.get_session_invitation(1, view.invitation_id))[field] == 1
    assert people[8].send.await_count == delivered_before_retry + 1
    if failure == "ack":
        assert delivered_before_retry == 1  # A lost acknowledgement permits at-least-once delivery.
    if expired:
        assert view.invitation_id not in service.views
    else:
        await service.tick(view)
        assert people[8].send.await_count == delivered_before_retry + 1
    await service.close_kind("group")


@pytest.mark.asyncio
async def test_warning_and_expiry_use_absolute_boundaries(persisted_group):
    group, people, _ = persisted_group
    view = GroupInvitationView(group, 8)
    created = time.time()
    await group.db.create_session_invitation(view.invitation_id, 1, "group", group.group_id, 8, 5, created)
    group.bot.fetch_user = AsyncMock(return_value=people[8])
    service = InvitationService(group.bot)
    for offset, notices, status in [(359, 0, "pending"), (360, 1, "pending"), (599, 1, "pending"), (600, 2, "expired")]:
        with patch("cogs._invitations.time.time", return_value=created + offset):
            await service.tick(view)
        assert people[8].send.await_count == notices
        assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == status


@pytest.mark.asyncio
@pytest.mark.parametrize("expired", [False, True])
async def test_failed_notice_is_restored_after_restart(persisted_group, expired):
    group, people, _ = persisted_group
    created = time.time() - (601 if expired else 400)
    await group.db.create_session_invitation("restart-notice", 1, "group", group.group_id, 8, 5, created)
    group.bot.fetch_user = AsyncMock(side_effect=RuntimeError("offline"))
    service = InvitationService(group.bot)
    await service.restore()
    assert "restart-notice" in service.views
    await service.close_kind("group")
    await group.db.close()
    await group.db.connect()
    group.bot.fetch_user = AsyncMock(return_value=people[8])
    restored = InvitationService(group.bot)
    await restored.restore()
    saved = await group.db.get_session_invitation(1, "restart-notice")
    assert saved["created_at"] == created
    assert saved["expiry_notified" if expired else "warned"] == 1
    people[8].send.assert_awaited_once()
    await restored.close_kind("group")


@pytest.mark.asyncio
async def test_monitor_caps_notice_retry_delay_and_shutdown_drains_it(persisted_group):
    group, _, _ = persisted_group
    view = GroupInvitationView(group, 8)
    await group.db.create_session_invitation(view.invitation_id, 1, "group", group.group_id, 8, 5, time.time() - 601)
    group.bot.fetch_user = AsyncMock(side_effect=RuntimeError("offline"))
    service = InvitationService(group.bot)
    service.notice_retries[view.invitation_id] = 100
    sleeping = asyncio.Event()

    async def sleep(delay):
        assert delay == 30
        sleeping.set()
        await asyncio.Event().wait()

    with patch("cogs._invitations.asyncio.sleep", side_effect=sleep):
        service.register(view)
        await sleeping.wait()
        await service.close_kind("group")
    assert not service.views and not service.tasks and not service.notice_retries
    assert (await group.db.get_session_invitation(1, view.invitation_id))["expiry_notified"] == 0
    service.register(view)
    assert not service.views and not service.tasks  # An action finishing after shutdown cannot restart delivery.
