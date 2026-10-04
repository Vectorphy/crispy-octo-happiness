import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from cogs.study_groups import GroupInvitationView, StudyGroup, StudyGroupCog


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["set_group_category", "purge_groups"])
async def test_group_owner_cannot_change_server_settings_or_purge(command):
    cog, guild, people, *_ = environment()
    bot = cog.bot
    manager = MagicMock()
    manager.get_permission_level = AsyncMock(return_value=2)
    bot.get_cog.return_value = manager
    request = interaction(bot, guild, people[5])
    args = [guild.get_channel(20)] if command == "set_group_category" else []

    await getattr(cog, command).callback(cog, request, *args)

    bot.db.update_group_category.assert_not_awaited()
    bot.db.get_all_study_groups.assert_not_awaited()
    assert request.followup.send.call_args.kwargs["ephemeral"] is True


def member(user_id: int, name: str = "vec") -> MagicMock:
    user = MagicMock(spec=discord.Member)
    user.id = user_id
    user.name = name
    user.display_name = name
    user.bot = False
    user.guild_permissions = discord.Permissions.none()
    user.roles = []
    user.add_roles = AsyncMock()
    user.remove_roles = AsyncMock()
    user.send = AsyncMock()
    return user


def interaction(bot, guild, user) -> MagicMock:
    request = MagicMock(spec=discord.Interaction)
    request.client = bot
    request.guild = guild
    request.guild_id = guild.id if guild else None
    request.user = user
    request.channel_id = 30
    request.channel = guild.get_channel(30) if guild else None
    request.extras = {}
    request.response = AsyncMock()
    request.response.is_done = MagicMock(return_value=True)
    request.followup = AsyncMock()
    request.delete_original_response = AsyncMock()
    return request


def environment():
    bot = MagicMock()
    bot.bot_developer_id = 9999
    bot.db = AsyncMock()
    bot.db.get_manager.return_value = None
    bot.db.get_group_category.return_value = 20
    bot.db.get_default_max_members.return_value = 3
    bot.db.get_guild_group_names.return_value = []
    bot.db.get_commands_channel.return_value = 30
    bot.db.get_default_group_duration.return_value = 86400
    bot.get_cog.return_value = None
    guild = MagicMock(spec=discord.Guild)
    guild.id = 1
    guild.owner_id = 999
    guild.me = member(100, "bot")
    guild.me.guild_permissions = discord.Permissions.all()
    guild.me.top_role = MagicMock(spec=discord.Role, position=10)
    people = {identifier: member(identifier) for identifier in (5, 6, 7, 8)}
    guild.get_member.side_effect = people.get
    role = MagicMock(spec=discord.Role)
    role.id = 90
    role.delete = AsyncMock()
    guild.get_role.return_value = role
    guild.create_role = AsyncMock(return_value=role)
    category = MagicMock(spec=discord.CategoryChannel)
    category.id = 20
    category.guild = guild
    category.permissions_for.return_value = discord.Permissions.all()
    category.overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=True)}
    text = AsyncMock(spec=discord.TextChannel)
    text.id = 30
    voice = AsyncMock(spec=discord.VoiceChannel)
    voice.id = 40
    category.create_text_channel = AsyncMock(return_value=text)
    category.create_voice_channel = AsyncMock(return_value=voice)
    guild.get_channel.side_effect = {20: category, 30: text, 40: voice}.get
    guild.categories = [category]
    cog = StudyGroupCog(bot)
    cog.log_mod_action = AsyncMock()
    return cog, guild, people, category, text, voice


@pytest.fixture
def creation(monkeypatch):
    monkeypatch.setattr(StudyGroup, "button_view", AsyncMock())
    monkeypatch.setattr(StudyGroup, "group_info_embed", AsyncMock())
    monkeypatch.setattr(StudyGroup, "check_end_condition", AsyncMock())
    return environment()


@pytest.mark.asyncio
async def test_creation_sends_consent_invites_without_adding_recipients(creation):
    cog, guild, people, category, text, voice = creation
    request = interaction(cog.bot, guild, people[5])

    await StudyGroupCog.create_group.callback(cog, request, "<@6> <@7>", name="vec")

    group = next(iter(cog.active_study_groups.values()))
    assert group.member_ids == [5]
    uuid.UUID(group.group_id)
    cog.bot.db.add_member_to_study_group_db.assert_awaited_once_with(group.group_id, 5)
    assert cog.bot.db.save_study_group.call_args.kwargs["study_group_data"]["member_ids"] == [5]
    people[6].add_roles.assert_not_awaited()
    people[7].add_roles.assert_not_awaited()
    assert category.create_text_channel.call_args.kwargs["overwrites"] == category.overwrites
    assert category.create_voice_channel.call_args.kwargs["overwrites"] == category.overwrites
    text.set_permissions.assert_not_awaited()
    voice.set_permissions.assert_not_awaited()

    invitation = people[6].send.call_args.kwargs["view"]
    assert isinstance(invitation, GroupInvitationView)
    await invitation.join_button.callback(interaction(cog.bot, None, people[6]))
    assert group.member_ids == [5, 6]
    people[6].add_roles.assert_awaited_once()
    declined = people[7].send.call_args.kwargs["view"]
    await declined.decline_button.callback(interaction(cog.bot, None, people[7]))
    assert group.member_ids == [5, 6]
    people[7].add_roles.assert_not_awaited()


@pytest.mark.asyncio
async def test_invite_consent_rechecks_capacity_and_rejects_other_users(creation):
    cog, guild, people, _, _, _ = creation
    await StudyGroupCog.create_group.callback(
        cog, interaction(cog.bot, guild, people[5]), "<@6>", name="vec", max_members=1
    )
    group = next(iter(cog.active_study_groups.values()))
    invitation = people[6].send.call_args.kwargs["view"]
    await invitation.join_button.callback(interaction(cog.bot, None, people[7]))
    await invitation.join_button.callback(interaction(cog.bot, None, people[6]))
    assert group.member_ids == [5]
    people[6].add_roles.assert_not_awaited()
    assert invitation.is_finished()


@pytest.mark.asyncio
async def test_blocked_invitation_dm_does_not_add_recipient(creation):
    cog, guild, people, _, _, _ = creation
    people[6].send.side_effect = discord.Forbidden(MagicMock(status=403, reason="Forbidden"), "blocked")
    request = interaction(cog.bot, guild, people[5])

    await StudyGroupCog.create_group.callback(cog, request, "<@6>", name="vec")

    group = next(iter(cog.active_study_groups.values()))
    assert group.member_ids == [5]
    people[6].add_roles.assert_not_awaited()
    assert "invitation could not be delivered" in request.followup.send.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("group_name, channel_id", [("  VEC  ", 30), (None, 30), (None, 40)])
async def test_invite_resolves_active_group_by_name_or_channel(group_name, channel_id):
    group, people = existing_group()
    group.send_invite = AsyncMock()
    request = interaction(group.bot, group.guild, people[5])
    request.channel_id = channel_id

    await StudyGroupCog.invite_to_group.callback(group.cog, request, people[7], group_name=group_name)

    group.send_invite.assert_awaited_once()
    assert group.send_invite.call_args.args[1] is people[7]


@pytest.mark.asyncio
@pytest.mark.parametrize("group_name", ["  VEC  ", None])
async def test_invite_hydrates_active_group_after_restart(monkeypatch, group_name):
    cog, guild, people, _, _, _ = environment()
    record = {
        "id": 12,
        "group_id": "group-12",
        "guild_id": guild.id,
        "name": "vec",
        "creator_id": 5,
        "owner_id": 5,
        "active": 1,
        "category_id": 20,
        "max_members": 3,
        "text_id": 30,
        "vc_id": 40,
        "group_role_id": 90,
        "end_time": (datetime.now() + timedelta(hours=1)).timestamp(),
    }
    cog.bot.db.fetch_study_group_by_name.return_value = record
    cog.bot.db.get_study_group_by_channel.return_value = record
    cog.bot.db.fetch_members_of_group.return_value = [5, 6]
    monkeypatch.setattr(StudyGroup, "check_end_condition", AsyncMock())

    await StudyGroupCog.invite_to_group.callback(
        cog, interaction(cog.bot, guild, people[5]), people[7], group_name=group_name
    )

    group = cog.active_study_groups["group-12"]
    assert group.member_ids == [5, 6]
    assert group.owner_id == 5
    people[7].send.assert_awaited_once()
    assert people[7].send.call_args.kwargs["view"].group is group


@pytest.mark.asyncio
async def test_invite_rejects_foreign_guild_record_and_does_not_switch_named_target():
    cog, guild, people, _, _, _ = environment()
    cog.bot.db.fetch_study_group_by_name.return_value = {
        "id": 12,
        "group_id": "group-12",
        "guild_id": 2,
        "name": "vec",
        "active": 1,
    }
    cog.bot.db.get_user_group.return_value = {"group_id": "another-group", "guild_id": guild.id, "active": 1}
    request = interaction(cog.bot, guild, people[5])

    await StudyGroupCog.invite_to_group.callback(cog, request, people[7], group_name="vec")

    assert "Could not locate" in request.followup.send.call_args.args[0]
    cog.bot.db.get_user_group.assert_not_awaited()
    people[7].send.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_custom_names_include_history_case_insensitively(creation):
    cog, guild, people, _, _, _ = creation
    cog.bot.db.get_guild_group_names.return_value = ["vec", "VEC-2"]
    await asyncio.gather(
        StudyGroupCog.create_group.callback(cog, interaction(cog.bot, guild, people[5]), "", name="Vec"),
        StudyGroupCog.create_group.callback(cog, interaction(cog.bot, guild, people[6]), "", name="vec"),
    )
    assert {group.name.casefold() for group in cog.active_study_groups.values()} == {"vec-3", "vec-4"}


@pytest.mark.asyncio
async def test_default_name_advances_historical_sequence_and_uses_guild_duration(creation):
    cog, guild, people, _, _, _ = creation
    cog.bot.db.get_guild_group_names.return_value = ["vec-studysession-1", "VEC-STUDYSESSION-3"]
    cog.bot.db.get_default_group_duration.return_value = 7200
    await StudyGroupCog.create_group.callback(cog, interaction(cog.bot, guild, people[5]), "")
    group = next(iter(cog.active_study_groups.values()))
    assert group.name == "vec-studysession-4"
    assert group.duration == 7200
    assert group.end_time == group.start_time + 7200


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["   ", "x" * 101])
async def test_invalid_name_creates_no_discord_resources(creation, name):
    cog, guild, people, _, _, _ = creation
    request = interaction(cog.bot, guild, people[5])
    await StudyGroupCog.create_group.callback(cog, request, "", name=name)
    guild.create_role.assert_not_awaited()
    assert request.followup.send.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", ["manage_roles", "role_hierarchy"])
async def test_role_permission_preflight_creates_no_resources(creation, permission):
    cog, guild, people, category, _, _ = creation
    if permission == "manage_roles":
        guild.me.guild_permissions.manage_roles = False
    else:
        guild.me.top_role.position = 0
    request = interaction(cog.bot, guild, people[5])
    await StudyGroupCog.create_group.callback(cog, request, "")
    guild.create_role.assert_not_awaited()
    category.create_text_channel.assert_not_awaited()
    assert request.followup.send.call_args.kwargs["ephemeral"] is True


def existing_group():
    cog, guild, people, _, _, _ = environment()
    group = StudyGroup(cog.bot.db, cog, guild.id, "vec", 5, 20, 3, [5, 6])
    group.guild = guild
    group.active = True
    group.text_id = 30
    group.vc_id = 40
    group.end_group = AsyncMock()
    cog.active_study_groups[group.group_id] = group
    return group, people


@pytest.mark.asyncio
async def test_regular_member_end_waits_for_current_owner_consent():
    group, people = existing_group()
    await group.end_group_callback(interaction(group.bot, group.guild, people[6]))
    group.end_group.assert_not_awaited()
    view = people[5].send.call_args.kwargs["view"]
    await view.approve.callback(interaction(group.bot, None, people[5]))
    group.end_group.assert_awaited_once_with(delay=0, actor_id=5)


@pytest.mark.asyncio
async def test_outsiders_and_misleading_staff_role_cannot_end_or_request():
    group, people = existing_group()
    people[7].roles = [MagicMock(name="Administrator")]
    await group.end_group_callback(interaction(group.bot, group.guild, people[7]))
    people[5].send.assert_not_awaited()
    group.end_group.assert_not_awaited()


@pytest.mark.asyncio
async def test_end_request_expires_on_transfer_and_decline_keeps_running():
    group, people = existing_group()
    await group.request_end(interaction(group.bot, group.guild, people[6]))
    view = people[5].send.call_args.kwargs["view"]
    group.owner_id = 7
    await view.approve.callback(interaction(group.bot, None, people[5]))
    group.end_group.assert_not_awaited()
    view.stop()
    group.owner_id = 5
    await group.request_end(interaction(group.bot, group.guild, people[6]))
    decline = people[5].send.call_args.kwargs["view"]
    await decline.decline.callback(interaction(group.bot, None, people[5]))
    group.end_group.assert_not_awaited()


@pytest.mark.asyncio
async def test_former_creator_requires_current_owner_approval():
    group, people = existing_group()
    group.owner_id = 7
    group.member_ids.append(7)

    await group.end_group_callback(interaction(group.bot, group.guild, people[5]))

    group.end_group.assert_not_awaited()
    people[7].send.assert_awaited_once()


@pytest.mark.asyncio
async def test_blocked_owner_dm_keeps_group_running():
    group, people = existing_group()
    people[5].send.side_effect = discord.Forbidden(MagicMock(status=403, reason="Forbidden"), "blocked")
    request = interaction(group.bot, group.guild, people[6])

    await group.end_group_callback(request)

    group.end_group.assert_not_awaited()
    assert "couldn't message the owner" in request.followup.send.call_args.args[0]


@pytest.mark.asyncio
async def test_persisted_end_request_rechecks_current_owner(monkeypatch):
    cog, guild, people, _, _, _ = environment()
    record = {
        "id": 12,
        "group_id": "group-12",
        "guild_id": guild.id,
        "name": "vec",
        "creator_id": 5,
        "owner_id": 5,
        "active": 1,
        "category_id": 20,
        "max_members": 3,
        "text_id": 30,
        "vc_id": 40,
        "group_role_id": 90,
    }
    cog.bot.db.fetch_study_group_by_name.return_value = record
    cog.bot.db.fetch_members_of_group.return_value = [5, 6]
    cog.bot.db.fetch_study_group_by_id.return_value = {**record, "owner_id": 7}
    end_group = AsyncMock()
    monkeypatch.setattr(StudyGroup, "end_group", end_group)

    await StudyGroupCog.end_group.callback(cog, interaction(cog.bot, guild, people[6]), name="vec")
    view = people[5].send.call_args.kwargs["view"]
    await view.approve.callback(interaction(cog.bot, None, people[5]))

    end_group.assert_not_awaited()
    cog.bot.db.delete_study_group.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("user_id", [5, 7])
async def test_owner_and_actual_moderator_can_end_directly(user_id):
    group, people = existing_group()
    if user_id == 7:
        people[7].guild_permissions.moderate_members = True
    await group.end_group_callback(interaction(group.bot, group.guild, people[user_id]))
    group.end_group.assert_awaited_once_with(actor_id=user_id)
    people[5].send.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("camera,stream", [(True, False), (False, True), (True, True)])
async def test_video_requirement_accepts_camera_or_screen_share(monkeypatch, camera, stream):
    group, people = existing_group()
    group.video_mode = "force"
    participant = people[6]
    participant.voice = MagicMock(spec=discord.VoiceState)
    participant.voice.channel = MagicMock(id=40)
    participant.voice.self_video = camera
    participant.voice.self_stream = stream
    participant.move_to = AsyncMock()
    monkeypatch.setattr("cogs.study_groups.asyncio.sleep", AsyncMock())
    await group._enforce_video(participant)
    participant.move_to.assert_not_awaited()
    participant.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_video_requirement_disconnects_only_when_both_are_off(monkeypatch):
    group, people = existing_group()
    group.video_mode = "force"
    participant = people[6]
    participant.voice = MagicMock(spec=discord.VoiceState)
    participant.voice.channel = MagicMock(id=40)
    participant.voice.self_video = False
    participant.voice.self_stream = False
    participant.move_to = AsyncMock()
    monkeypatch.setattr("cogs.study_groups.asyncio.sleep", AsyncMock())
    await group._enforce_video(participant)
    participant.move_to.assert_awaited_once_with(None, reason=f"Video required in study group {group.group_id}")
    assert "camera or screen sharing" in participant.send.call_args.args[0]
