import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from cogs.checkin import CheckinCog, CheckinGuildSettings, CheckinInvitationView, CheckinSession
from cogs.pomodoro import (
    Pomodoro,
    PomodoroInvitationView,
    PomodoroRenewView,
    PomodoroSession,
    calculate_pomodoro_ratio,
)


def test_short_focus_still_gives_two_minute_breaks():
    assert calculate_pomodoro_ratio(focus=2) == (2, 2, 2)
    assert calculate_pomodoro_ratio(focus=13) == (13, 2, 7)
    assert not hasattr(Pomodoro, "on_voice_state_update")


@pytest.mark.asyncio
@pytest.mark.parametrize("duration,accepted", [("1m", False), ("2m", True), ("240m", True), ("241m", False)])
async def test_checkin_duration_bounds(duration, accepted):
    bot = MagicMock()
    bot.db = AsyncMock()
    cog = CheckinCog(bot)
    interaction = MagicMock()
    interaction.guild.id = 42
    interaction.user.id = 10
    interaction.user.display_name = "Creator"
    interaction.client.bot_developer_id = 10
    interaction.channel.id = 100
    interaction.response.is_done.return_value = False
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    with (
        patch.object(CheckinSession, "setup_checkin_resources", new_callable=AsyncMock),
        patch.object(CheckinSession, "send_reminder_message", new_callable=AsyncMock),
        patch.object(CheckinSession, "run_checkin_reminders", new_callable=AsyncMock),
    ):
        await cog.start_checkin.callback(cog, interaction, "Standup", duration)
    assert bool(cog.active_sessions) is accepted


@pytest.mark.asyncio
async def test_checkin_invitation_joins_only_after_persistence():
    bot = MagicMock()
    bot.get_guild.return_value.get_member.return_value = MagicMock()
    cog = MagicMock(bot=bot)
    db = MagicMock()
    db.add_or_update_checkin_member = AsyncMock()
    interaction = MagicMock()
    interaction.guild.id = 42
    interaction.user.id = 10
    interaction.channel.id = 100
    session = CheckinSession(db, cog, interaction, "Standup", [10], 120, CheckinGuildSettings(interaction))
    cog.active_sessions = {session.session_id: session}
    invite_click = MagicMock()
    invite_click.user.id = 11
    invite_click.response.is_done.return_value = True
    invite_click.response.send_message = AsyncMock()
    invite_click.followup.send = AsyncMock()
    await session.join_session_callback(invite_click)
    db.add_or_update_checkin_member.assert_awaited_once_with(session.session_id, 11, "present", 0)
    assert 11 in session.member_ids
    assert 11 in session.member_statuses


@pytest.mark.asyncio
async def test_checkin_mentions_invite_without_admitting_recipients():
    bot = MagicMock()
    bot.db = AsyncMock()
    cog = CheckinCog(bot)
    creator = MagicMock()
    creator.id = 10
    creator.display_name = "Creator"
    invited = MagicMock()
    invited.id = 11
    invited.send = AsyncMock()
    blocked = MagicMock()
    blocked.id = 12
    blocked.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(status=403), "DM blocked"))
    guild = MagicMock()
    guild.id = 42
    guild.get_member.side_effect = {10: creator, 11: invited, 12: blocked}.get
    bot.get_guild.return_value = guild
    interaction = MagicMock()
    interaction.guild = guild
    interaction.user = creator
    interaction.client.bot_developer_id = 10
    interaction.channel.id = 100
    interaction.response.is_done.return_value = True
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    with (
        patch.object(CheckinSession, "setup_checkin_resources", new_callable=AsyncMock),
        patch.object(CheckinSession, "send_reminder_message", new_callable=AsyncMock),
        patch.object(CheckinSession, "run_checkin_reminders", new_callable=AsyncMock),
    ):
        await cog.start_checkin.callback(cog, interaction, "Standup", "2m", "<@11> <@12>")

    session = next(iter(cog.active_sessions.values()))
    assert session.member_ids == [10]
    assert set(session.member_statuses) == {10}
    invited.send.assert_awaited_once()
    blocked.send.assert_awaited_once()
    view = invited.send.await_args.kwargs["view"]
    session.update_embed = AsyncMock()
    click = MagicMock()
    click.user.id = 12
    click.response.send_message = AsyncMock()
    click.response.is_done.return_value = True
    click.followup.send = AsyncMock()
    await view.join.callback(click)
    assert session.member_ids == [10]
    click.user.id = 11
    await view.join.callback(click)
    assert session.member_ids == [10, 11]
    assert 12 not in session.member_statuses


@pytest.mark.asyncio
async def test_pomodoro_invites_group_members_without_auto_join():
    bot = MagicMock()
    bot.db = AsyncMock()
    group = {"id": 7, "group_id": "group", "guild_id": 42, "name": "Study", "text_id": 100}
    bot.db.get_user_group.return_value = group
    bot.db.fetch_members_of_group.return_value = [10, 11, 12]
    bot.db.get_default_pomodoro_duration.return_value = 86400
    cog = Pomodoro(bot)
    cog.send_notification = AsyncMock()
    cog._update_group_gui = AsyncMock()
    invited = MagicMock()
    invited.id = 11
    invited.send = AsyncMock()
    blocked = MagicMock()
    blocked.id = 12
    blocked.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(status=403), "DM blocked"))
    guild = MagicMock()
    guild.id = 42
    guild.get_member.side_effect = {11: invited, 12: blocked}.get
    bot.get_guild.return_value = guild
    interaction = MagicMock()
    interaction.guild = guild
    interaction.guild_id = 42
    interaction.channel_id = 100
    interaction.user.id = 10
    interaction.response.is_done.return_value = True
    interaction.followup.send = AsyncMock()
    try:
        await cog.start_pomodoro.callback(cog, interaction, require_vc=False)
        session = cog.sessions["group"]
        assert session.participants == {10}
        invited.send.assert_awaited_once()
        blocked.send.assert_awaited_once()
        view = invited.send.await_args.kwargs["view"]
        click = MagicMock()
        click.user.id = 12
        click.response.defer = AsyncMock()
        click.response.is_done.return_value = True
        click.followup.send = AsyncMock()
        await view.join.callback(click)
        assert session.participants == {10}
        click.user.id = 11
        await view.join.callback(click)
        assert session.participants == {10, 11}
        decline = PomodoroInvitationView(cog, session, 12)
        click.user.id = 11
        click.response.send_message = AsyncMock()
        await decline.decline.callback(click)
        assert not decline.is_finished()
        click.user.id = 12
        await decline.decline.callback(click)
        assert 12 not in session.participants
        await cog._remove_session(session)
        await PomodoroInvitationView(cog, session, 12).join.callback(click)
        assert 12 not in session.participants
    finally:
        if cog.run_timer.is_running():
            cog.run_timer.stop()


@pytest.mark.asyncio
async def test_declined_wrong_recipient_and_stale_checkin_invites_do_not_join():
    session = MagicMock()
    session.member_ids = []
    view = CheckinInvitationView(session, 11)
    interaction = MagicMock()
    interaction.user.id = 12
    interaction.response.send_message = AsyncMock()
    assert await view.interaction_check(interaction) is False
    session.join_session_callback.assert_not_called()
    await view.decline.callback(interaction)
    assert not view.is_finished()
    interaction.user.id = 11
    await view.decline.callback(interaction)
    session.join_session_callback.assert_not_called()

    bot = MagicMock()
    db = MagicMock()
    db.add_or_update_checkin_member = AsyncMock()
    cog = MagicMock(bot=bot, active_sessions={})
    creation = MagicMock()
    creation.guild.id = 42
    creation.user.id = 10
    creation.channel.id = 100
    ended = CheckinSession(db, cog, creation, "Standup", [10], 120, CheckinGuildSettings(creation))
    click = MagicMock()
    click.user.id = 11
    click.response.is_done.return_value = True
    click.response.send_message = AsyncMock()
    click.followup.send = AsyncMock()
    await ended.join_session_callback(click)
    db.add_or_update_checkin_member.assert_not_awaited()
    assert 11 not in ended.member_ids


@pytest.mark.asyncio
@pytest.mark.parametrize("focus,accepted", [(1, False), (2, True), (240, True), (241, False)])
async def test_pomodoro_stage_bounds(focus, accepted):
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_default_pomodoro_duration.return_value = 86400
    bot.db.get_user_group.return_value = {
        "id": 1,
        "group_id": "g",
        "guild_id": 42,
        "name": "Group",
        "text_id": 100,
        "vc_id": 200,
    }
    bot.db.fetch_members_of_group.return_value = [10]
    cog = Pomodoro(bot)
    cog.send_notification = AsyncMock()
    cog._update_group_gui = AsyncMock()
    interaction = MagicMock()
    interaction.guild.id = 42
    interaction.guild_id = 42
    interaction.channel_id = 100
    interaction.user.id = 10
    interaction.response.is_done.return_value = False
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    await cog.start_pomodoro.callback(cog, interaction, focus=focus, require_vc=False)
    assert bool(cog.sessions) is accepted
    if cog.run_timer.is_running():
        cog.run_timer.stop()


@pytest.mark.asyncio
async def test_pomodoro_rejects_group_from_another_server():
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_user_group.return_value = {"id": 1, "group_id": "other", "guild_id": 99}
    bot.db.get_study_group_by_channel.return_value = None
    bot.db.get_study_group.return_value = None
    cog = Pomodoro(bot)
    interaction = MagicMock()
    interaction.user.id = 10
    interaction.user.voice = None
    interaction.guild_id = 42
    interaction.channel_id = 100
    interaction.response.is_done.return_value = False
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    with patch("cogs.pomodoro.check_manager", new=AsyncMock(return_value=False)):
        await cog.start_pomodoro.callback(cog, interaction, require_vc=False)
    assert not cog.sessions


@pytest.mark.asyncio
async def test_pomodoro_fallback_voice_channel_inherits_category_permissions():
    bot = MagicMock()
    bot.db = AsyncMock()
    group = {"id": 7, "group_id": "group", "guild_id": 42, "name": "Study", "text_id": 100, "vc_id": None}
    bot.db.get_user_group.return_value = group
    bot.db.get_group_category.return_value = 300
    bot.db.get_default_pomodoro_duration.return_value = 86400
    bot.db.fetch_members_of_group.return_value = [10]
    category = MagicMock(spec=discord.CategoryChannel)
    overwrites = {MagicMock(spec=discord.Role): discord.PermissionOverwrite(view_channel=True)}
    category.overwrites = overwrites
    voice = MagicMock(spec=discord.VoiceChannel)
    voice.id = 200
    category.create_voice_channel = AsyncMock(return_value=voice)
    cog = Pomodoro(bot)
    cog.send_notification = AsyncMock()
    cog._update_group_gui = AsyncMock()
    interaction = MagicMock()
    interaction.guild.id = 42
    interaction.guild.get_channel.return_value = category
    interaction.guild_id = 42
    interaction.channel_id = 100
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = 10
    interaction.user.voice = MagicMock()
    interaction.user.move_to = AsyncMock()
    interaction.response.is_done.return_value = True
    interaction.followup.send = AsyncMock()

    await cog.start_pomodoro.callback(cog, interaction, require_vc=True)

    category.create_voice_channel.assert_awaited_once_with("Study VC", overwrites=overwrites)
    assert category.create_voice_channel.await_args.kwargs["overwrites"] is overwrites
    bot.db.update_voice_channel.assert_awaited_once_with(7, 200)
    assert group["vc_id"] == 200
    assert cog.sessions["group"].vc_id == 200
    if cog.run_timer.is_running():
        cog.run_timer.stop()


@pytest.mark.asyncio
async def test_renew_button_adds_one_day_only_once():
    cog = Pomodoro(MagicMock())
    session = PomodoroSession("group", 25, 5, 15, guild_id=42, owner_id=10)
    session.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    cog.sessions["group"] = session
    initial_deadline = session.expires_at
    view = PomodoroRenewView(cog, session, initial_deadline)
    interaction = MagicMock()
    interaction.user.id = 10
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.response.is_done.return_value = True
    await view.renew.callback(interaction)
    assert session.expires_at == initial_deadline + timedelta(hours=24)
    await view.renew.callback(interaction)
    assert session.expires_at == initial_deadline + timedelta(hours=24)


@pytest.mark.asyncio
async def test_renew_button_rejects_unjoined_user():
    cog = Pomodoro(MagicMock())
    session = PomodoroSession("group", 25, 5, 15, guild_id=42, owner_id=10)
    cog.sessions["group"] = session
    deadline = session.expires_at
    view = PomodoroRenewView(cog, session, deadline)
    interaction = MagicMock()
    interaction.user.id = 11
    interaction.guild = None
    interaction.response.defer = AsyncMock()
    interaction.response.is_done.return_value = True
    interaction.followup.send = AsyncMock()
    await view.renew.callback(interaction)
    assert session.expires_at == deadline


@pytest.mark.asyncio
async def test_pomodoro_lifetime_warns_and_expires_even_when_paused():
    bot = MagicMock()
    bot.db = AsyncMock()
    cog = Pomodoro(bot)
    cog.send_notification = AsyncMock()
    cog._update_group_gui = AsyncMock()
    session = PomodoroSession("group", 25, 5, 15, guild_id=42, owner_id=10)
    session.is_paused = True
    session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=59)
    cog.sessions["group"] = session
    await cog.run_timer.coro(cog)
    assert cog.send_notification.await_count == 1
    assert session.warned_deadline == session.expires_at
    await cog.run_timer.coro(cog)
    assert cog.send_notification.await_count == 1
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await cog.run_timer.coro(cog)
    assert not cog.sessions


@pytest.mark.asyncio
async def test_dashboard_pause_rejects_expired_session_and_end_removes_all_aliases():
    bot = MagicMock()
    bot.db = AsyncMock()
    cog = Pomodoro(bot)
    cog._update_group_gui = AsyncMock()
    session = PomodoroSession("group", 25, 5, 15, guild_id=42, owner_id=10)
    cog.sessions.update({"group": session, 7: session, "7": session})
    assert await cog.set_paused(session, True)
    assert session.is_paused
    cog._update_group_gui.assert_awaited_once_with("group")

    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert not await cog.set_paused(session, False)
    assert session.is_paused
    interaction = MagicMock()
    interaction.response.is_done.return_value = True
    interaction.followup.send = AsyncMock()
    await cog.finish_session(interaction, {"id": 7, "group_id": "group"}, session)
    assert not cog.sessions
    interaction.followup.send.assert_awaited()


@pytest.mark.asyncio
async def test_checkin_concurrent_joins_observe_member_limit():
    bot = MagicMock()
    bot.get_guild.return_value.get_member.return_value = MagicMock()
    cog = MagicMock(bot=bot)
    db = MagicMock()
    db.add_or_update_checkin_member = AsyncMock()
    creation = MagicMock()
    creation.guild.id = 42
    creation.user.id = 10
    creation.channel.id = 100
    settings = CheckinGuildSettings(creation, max_members=2)
    session = CheckinSession(db, cog, creation, "Standup", [10], 120, settings)
    cog.active_sessions = {session.session_id: session}
    interactions = []
    for user_id in (11, 12):
        interaction = MagicMock()
        interaction.user.id = user_id
        interaction.response.is_done.return_value = True
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        interactions.append(interaction)
    await asyncio.gather(*(session.join_session_callback(interaction) for interaction in interactions))
    assert len(session.member_ids) == 2
    assert db.add_or_update_checkin_member.await_count == 1


@pytest.mark.asyncio
async def test_checkin_join_failure_keeps_roster_and_hides_database_error():
    bot = MagicMock()
    bot.get_guild.return_value.get_member.return_value = MagicMock()
    cog = MagicMock(bot=bot)
    db = MagicMock()
    db.add_or_update_checkin_member = AsyncMock(side_effect=RuntimeError("sensitive database detail"))
    creation = MagicMock()
    creation.guild.id = 42
    creation.user.id = 10
    creation.channel.id = 100
    session = CheckinSession(db, cog, creation, "Standup", [10], 120, CheckinGuildSettings(creation))
    cog.active_sessions = {session.session_id: session}
    click = MagicMock()
    click.user.id = 11
    click.response.is_done.return_value = True
    click.followup.send = AsyncMock()
    await session.join_session_callback(click)
    assert session.member_ids == [10]
    assert 11 not in session.member_statuses
    assert "sensitive database detail" not in str(click.followup.send.call_args)


@pytest.mark.asyncio
async def test_former_checkin_creator_requests_current_owner_approval():
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_manager.return_value = None
    bot.bot_developer_id = None
    cog = MagicMock(bot=bot)
    creation = MagicMock()
    creation.guild.id = 42
    creation.user.id = 10
    creation.channel.id = 100
    session = CheckinSession(bot.db, cog, creation, "Standup", [10, 11], 120, CheckinGuildSettings(creation))
    session.owner_id = 11
    cog.active_sessions = {session.session_id: session}
    click = MagicMock()
    click.user.id = 10
    click.user.display_name = "Former owner"
    click.user.guild_permissions = None
    click.client = bot
    click.guild.id = 42
    click.guild.owner_id = 99
    owner = MagicMock()
    owner.send = AsyncMock()
    click.guild.get_member.return_value = owner
    click.response.is_done.return_value = True
    click.followup.send = AsyncMock()
    await session.end_session_callback(click)
    owner.send.assert_awaited_once()
    bot.db.update_checkin_session.assert_not_awaited()
    assert cog.active_sessions[session.session_id] is session


@pytest.mark.asyncio
async def test_checkin_owner_transfer_excludes_unjoined_and_exited_users():
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_manager.return_value = None
    bot.bot_developer_id = None
    cog = MagicMock(bot=bot)
    creation = MagicMock()
    creation.guild.id = 42
    creation.user.id = 10
    creation.channel.id = 100
    session = CheckinSession(bot.db, cog, creation, "Standup", [10, 11], 120, CheckinGuildSettings(creation))
    session.member_statuses[11]["status"] = "exited"
    click = MagicMock()
    click.user.id = 10
    click.user.mention = "<@10>"
    click.response.is_done.return_value = True
    click.response.send_message = AsyncMock()
    click.followup.send = AsyncMock()
    await session.change_owner_callback(click)
    assert session.owner_id == 10
    assert any("no other members" in str(call).lower() for call in click.followup.send.await_args_list)

    session.member_statuses[11]["status"] = "present"
    session.owner_id = 11
    click.client = bot
    click.guild.id = 42
    click.guild.owner_id = 99
    click.user.guild_permissions = None
    click.response.is_done.return_value = False
    click.response.send_message = AsyncMock()
    await session.change_owner_callback(click)
    assert session.owner_id == 11
    assert any("not authorized" in str(call).lower() for call in click.response.send_message.await_args_list)


@pytest.mark.asyncio
async def test_former_group_creator_cannot_end_others_pomodoro_directly():
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_manager.return_value = None
    bot.bot_developer_id = None
    cog = Pomodoro(bot)
    group = {"id": 7, "group_id": "group", "guild_id": 42, "creator_id": 10, "owner_id": 11}
    cog._resolve_group = AsyncMock(return_value=group)
    session = PomodoroSession("group", 25, 5, 15, guild_id=42, owner_id=11)
    session.participants.add(10)
    cog.sessions["group"] = session
    click = MagicMock()
    click.user.id = 10
    click.user.display_name = "Former group owner"
    click.user.guild_permissions = None
    click.client = bot
    click.guild.id = 42
    click.guild.owner_id = 99
    owner = MagicMock()
    owner.send = AsyncMock()
    click.guild.get_member.return_value = owner
    click.response.is_done.return_value = True
    click.followup.send = AsyncMock()
    await cog.end_pomodoro.callback(cog, click)
    owner.send.assert_awaited_once()
    assert cog.sessions["group"] is session
