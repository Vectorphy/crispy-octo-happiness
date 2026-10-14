from unittest.mock import AsyncMock, patch

import pytest

from cogs.pomodoro import Pomodoro, PomodoroPresenceView, PomodoroSession
from tests.test_group_controls import environment, interaction


@pytest.mark.asyncio
async def test_dropout_guidance_does_not_offer_a_rejoin_command():
    group_cog, guild, people, *_ = environment()
    cog = Pomodoro(group_cog.bot)
    cog._persist_session = AsyncMock()
    session = PomodoroSession("dropout", 25, 5, 15, guild_id=1, owner_id=5)
    session.participants.add(8)
    session.dropped_out_members.add(8)
    request = interaction(group_cog.bot, guild, people[8])
    view = PomodoroPresenceView(cog, session)
    await view.present_btn.callback(request)
    request.response.send_message.assert_awaited_once_with(
        "You dropped out of this Pomodoro session. Attendance is unavailable while you are dropped out.", ephemeral=True
    )
    assert session.dropped_out_members == {8} and not session.present_members
    cog._persist_session.assert_not_awaited()
    view.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("actor,allowed", [(8, False), (5, True)])
async def test_resume_keeps_owner_authority_and_denies_regular_dropout(actor, allowed):
    group_cog, guild, people, *_ = environment()
    cog = Pomodoro(group_cog.bot)
    session = PomodoroSession("dropout", 25, 5, 15, guild_id=1, owner_id=5)
    session.is_paused = True
    session.participants.add(8)
    session.dropped_out_members.add(8)
    cog.sessions["dropout"] = session
    cog._resolve_group = AsyncMock(
        return_value={"id": 1, "group_id": "dropout", "guild_id": 1, "creator_id": 5, "owner_id": 5}
    )
    cog._persist_session = AsyncMock()
    cog._update_group_gui = AsyncMock()
    cog.send_notification = AsyncMock()
    request = interaction(group_cog.bot, guild, people[actor])
    with patch.dict(cog.resume_pomodoro.callback.__globals__, check_manager=AsyncMock(return_value=False)):
        await cog.resume_pomodoro.callback(cog, request)
    assert session.is_paused is (not allowed)
    assert session.dropped_out_members == {8}
    assert cog._persist_session.await_count == int(allowed)
    assert ("Pomodoro session resumed." if allowed else "Go away peasent") in str(request.followup.send.call_args_list)


@pytest.mark.asyncio
async def test_paused_owner_dropout_guidance_then_resume_then_present():
    group_cog, guild, people, *_ = environment()
    cog = Pomodoro(group_cog.bot)
    session = PomodoroSession("dropout", 25, 5, 15, guild_id=1, owner_id=5)
    session.is_paused = True
    session.dropped_out_members.add(5)
    cog.sessions["dropout"] = session
    cog._resolve_group = AsyncMock(
        return_value={"id": 1, "group_id": "dropout", "guild_id": 1, "creator_id": 5, "owner_id": 5}
    )
    cog._persist_session = AsyncMock()
    cog._update_group_gui = AsyncMock()
    cog.send_notification = AsyncMock()
    view = PomodoroPresenceView(cog, session)
    blocked = interaction(group_cog.bot, guild, people[5])
    await view.present_btn.callback(blocked)
    assert "while you are dropped out" in blocked.response.send_message.call_args.args[0]
    with patch.dict(cog.resume_pomodoro.callback.__globals__, check_manager=AsyncMock(return_value=False)):
        await cog.resume_pomodoro.callback(cog, interaction(group_cog.bot, guild, people[5]))
    assert not session.is_paused and not session.dropped_out_members
    present = interaction(group_cog.bot, guild, people[5])
    await view.present_btn.callback(present)
    assert session.present_members == {5}
    assert "marked as Present" in present.response.send_message.call_args.args[0]
    view.stop()
