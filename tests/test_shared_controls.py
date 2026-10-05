import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord.ext import commands

from cogs._session_controls import EndRequestView, request_session_end
from cogs.help import Help
from cogs.manager import Manager, PermissionLevel
from cogs.voice_channels import VoiceChannels
from cogs.voice_channels import setup as setup_voice_channels
from database import DBHandler
from utils import get_context_group, has_guild_permissions


def interaction(user_id=5):
    result = MagicMock(spec=discord.Interaction)
    result.user.id = user_id
    result.user.display_name = "Member"
    result.guild = MagicMock(spec=discord.Guild)
    result.guild.id = result.guild_id = 1
    result.response = MagicMock()
    result.response.is_done.return_value = False
    result.response.send_message = AsyncMock()
    result.followup.send = AsyncMock()
    result.extras = {}
    result.delete_original_response = AsyncMock()
    return result


def control(view, label):
    return next(item for item in view.children if isinstance(item, discord.ui.Button) and item.label == label)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command,actor_level,level,allowed",
    [
        ("remove_guild_manager", 0, None, False),
        ("remove_guild_manager", 3, None, True),
        ("set_permission_level", 0, 3, False),
        ("set_permission_level", 4, 2, False),
        ("set_permission_level", 4, 3, True),
    ],
)
async def test_grant_command_result_clears_private_acknowledgement(command, actor_level, level, allowed):
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_study_group_by_channel.return_value = None
    bot.db.get_commands_channel.return_value = None
    cog = Manager(bot)
    cog.get_permission_level = AsyncMock(return_value=actor_level)
    cog._sync_staff_access = AsyncMock(return_value="")
    request = interaction()
    target = SimpleNamespace(id=6, name="Member")
    kwargs = {"level": level} if level is not None else {}

    await getattr(cog, command).callback(cog, request, target, **kwargs)

    request.delete_original_response.assert_awaited_once()
    assert "cpo_acknowledged" not in request.extras
    assert request.followup.send.call_args.kwargs["ephemeral"] is True
    if not allowed:
        bot.db.add_manager.assert_not_awaited()
        bot.db.remove_manager.assert_not_awaited()
    elif command == "remove_guild_manager":
        bot.db.remove_manager.assert_awaited_once_with(target.id, request.guild.id)
    else:
        bot.db.add_manager.assert_awaited_once_with(target.id, request.guild.id, level)


@pytest.mark.asyncio
async def test_end_approval_requires_owner_and_live_request():
    finish = AsyncMock()
    active = True
    view = EndRequestView(5, "Study", lambda: active, finish)
    await control(view, "End session").callback(interaction(6))
    finish.assert_not_awaited()
    active = False
    await control(view, "End session").callback(interaction(5))
    finish.assert_not_awaited()
    assert not view.decided
    await view.on_timeout()


@pytest.mark.asyncio
async def test_concurrent_owner_approvals_end_only_once():
    finish = AsyncMock()
    view = EndRequestView(5, "Study", lambda: True, finish)
    view.message = MagicMock(spec=discord.Message)
    view.message.edit = AsyncMock()
    await asyncio.gather(*(control(view, "End session").callback(interaction()) for _ in range(2)))
    finish.assert_awaited_once()
    assert view.decided and view.is_finished()
    assert all(item.disabled for item in view.children)


@pytest.mark.asyncio
@pytest.mark.parametrize("decline", [True, False])
async def test_decline_and_timeout_keep_session_running(decline):
    finish = AsyncMock()
    view = EndRequestView(5, "Study", lambda: True, finish)
    if decline:
        await control(view, "Keep running").callback(interaction())
    else:
        await view.on_timeout()
    await control(view, "End session").callback(interaction())
    finish.assert_not_awaited()
    assert view.decided


@pytest.mark.asyncio
async def test_blocked_owner_dm_reports_private_failure():
    request = interaction(6)
    request.guild.get_member.return_value.send = AsyncMock(
        side_effect=discord.Forbidden(MagicMock(status=403, reason="Forbidden"), "DM blocked")
    )
    finish = AsyncMock()
    await request_session_end(request, 5, "Study", lambda: True, finish)
    finish.assert_not_awaited()
    assert "couldn't message" in request.followup.send.call_args.args[0]
    assert request.followup.send.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_help_is_private_and_within_discord_limits():
    request = interaction()
    request.response.defer = AsyncMock()
    await Help.help_command.callback(Help(), request)
    reply = request.followup.send.call_args.kwargs
    assert reply["ephemeral"] is True
    embed = reply["embed"]
    assert len(embed.fields) <= 25 and len(embed) <= 6000
    assert "reminder interval" in " ".join(field.value for field in embed.fields)


@pytest.mark.asyncio
@pytest.mark.parametrize("level", [0, 1, 2, 3, 4])
async def test_help_descriptions_follow_staff_level(level):
    request = interaction()
    request.response.defer = AsyncMock()
    manager = MagicMock(get_permission_level=AsyncMock(return_value=level))
    bot = MagicMock()
    bot.get_cog.return_value = manager
    await Help.help_command.callback(Help(bot), request)
    embed = request.followup.send.call_args.kwargs["embed"]
    descriptions = " ".join(field.value for field in embed.fields)
    assert ("/setup" in descriptions) == (level >= 3)
    assert ("/add_bot_developer" in descriptions) == (level >= 3)
    assert ("/purge_groups" in descriptions) == (level >= 3)
    assert "Report malicious or unintended bot behavior to server staff immediately" in descriptions
    assert len(embed) <= 6000


@pytest.mark.asyncio
async def test_role_name_does_not_grant_server_authority():
    guild = SimpleNamespace(id=1, owner_id=99)
    user = SimpleNamespace(
        id=5, guild=guild, guild_permissions=discord.Permissions.none(), roles=[SimpleNamespace(name="Moderator")]
    )
    bot = MagicMock()
    bot.bot_developer_id = 999
    bot.db = AsyncMock()
    bot.db.get_manager.return_value = None
    bot.get_guild.return_value = guild
    assert not await has_guild_permissions(user, guild, bot)
    assert await Manager(bot).get_permission_level(1, 5, member=user) == PermissionLevel.REGULAR_USER


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["administrator", "manage_guild", "manage_channels", "moderate_members"])
async def test_real_discord_permissions_grant_server_authority(name):
    guild = SimpleNamespace(id=1, owner_id=99)
    user = SimpleNamespace(id=5, guild=guild, guild_permissions=discord.Permissions(**{name: True}))
    bot = MagicMock()
    bot.bot_developer_id = 999
    bot.get_guild.return_value = guild
    bot.db = AsyncMock()
    bot.db.get_manager.return_value = None
    assert await has_guild_permissions(user, guild, bot)
    expected = PermissionLevel.ADMIN if name in {"administrator", "manage_guild"} else PermissionLevel.MODERATOR
    assert await Manager(bot).get_permission_level(1, 5, member=user) == expected


@pytest.mark.asyncio
async def test_legacy_global_developer_does_not_override_native_administrator_level():
    guild = SimpleNamespace(id=1, owner_id=99)
    user = SimpleNamespace(id=5, guild=guild, guild_permissions=discord.Permissions(administrator=True))
    bot = MagicMock()
    bot.bot_developer_id = 999
    bot.get_guild.return_value = guild
    bot.db = AsyncMock()
    bot.db.get_manager.return_value = {"guild_id": None, "permission_level": 4}
    assert await Manager(bot).get_permission_level(1, 5, member=user) == PermissionLevel.ADMIN


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "grant_guild,level,allowed",
    [(2, 3, False), (None, 3, False), (None, 4, False), (1, 3, True), (1, 4, True), (1, 5, False)],
)
async def test_stored_authority_is_scoped_to_guild(grant_guild, level, allowed):
    guild = SimpleNamespace(id=1, owner_id=99)
    user = SimpleNamespace(id=5, guild=guild, guild_permissions=discord.Permissions.none())
    bot = MagicMock()
    bot.bot_developer_id = 999
    bot.get_guild.return_value = guild
    bot.db = AsyncMock()
    bot.db.get_manager.return_value = {"guild_id": grant_guild, "permission_level": level}
    assert await has_guild_permissions(user, guild, bot) is allowed
    actual = await Manager(bot).get_permission_level(1, 5, member=user)
    assert (actual >= PermissionLevel.MODERATOR) is allowed


@pytest.mark.asyncio
async def test_context_lookup_rejects_other_guild_and_ended_groups():
    request = interaction()
    db = AsyncMock()
    for record in ({"guild_id": 2, "active": 1}, {"guild_id": 1, "active": 0}):
        db.get_study_group_by_channel.return_value = record
        assert await get_context_group(request, db) is None


@pytest.mark.asyncio
async def test_member_permissions_from_another_guild_do_not_escalate():
    guild = SimpleNamespace(id=1, owner_id=99)
    other = SimpleNamespace(id=2, owner_id=5)
    member = SimpleNamespace(id=5, guild=other, guild_permissions=discord.Permissions(administrator=True))
    bot = MagicMock()
    bot.bot_developer_id = 999
    bot.get_guild.return_value = guild
    bot.db = AsyncMock()
    bot.db.get_manager.return_value = None
    assert await Manager(bot).get_permission_level(1, 5, member=member) == PermissionLevel.REGULAR_USER


@pytest.mark.asyncio
@pytest.mark.parametrize("storage_failure", [False, True])
async def test_voice_creation_inherits_category_and_rolls_back_failed_storage(storage_failure):
    request = interaction()
    request.channel_id = 20
    category = MagicMock(spec=discord.CategoryChannel)
    category.id = 10
    source = MagicMock(spec=discord.TextChannel)
    source.category = category
    request.guild.get_channel.side_effect = lambda identifier: {20: source, 10: category}.get(identifier)
    request.guild.me = MagicMock(spec=discord.Member)
    category.permissions_for.return_value = discord.Permissions(manage_channels=True)
    channel = MagicMock(spec=discord.VoiceChannel)
    channel.id = 91
    channel.mention = "<#91>"
    channel.delete = AsyncMock()
    request.guild.create_voice_channel = AsyncMock(return_value=channel)
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_commands_channel.return_value = 20
    bot.db.get_study_group_by_channel.return_value = {
        "guild_id": 1,
        "group_id": "group-1",
        "text_id": 20,
        "vc_id": None,
        "name": "Study",
    }
    live_group = SimpleNamespace(vc_id=None)
    bot.get_cog.return_value.active_study_groups = {"group-1": live_group}
    if storage_failure:
        bot.db.update_voice_channel.side_effect = RuntimeError("storage unavailable")
    cog = VoiceChannels(bot)
    await cog.create_vc.callback(cog, request)
    assert request.guild.create_voice_channel.call_args.kwargs["category"] is category
    assert "overwrites" not in request.guild.create_voice_channel.call_args.kwargs
    if storage_failure:
        channel.delete.assert_awaited_once()
        assert live_group.vc_id is None
        assert request.followup.send.call_args.kwargs["ephemeral"] is True
    else:
        channel.delete.assert_not_awaited()
        assert live_group.vc_id == 91


@pytest.mark.asyncio
async def test_added_developers_and_guild_managers_appear_without_user_cache():
    db = DBHandler(":memory:")
    await db.connect()
    try:
        bot = MagicMock()
        bot.bot_developer_id = 5
        bot.db = db
        bot.get_user.return_value = None
        cog = Manager(bot)
        request = interaction()
        request.guild.get_member.return_value = None
        guild_manager = SimpleNamespace(id=6, name="New manager")
        developer = SimpleNamespace(id=7, name="New developer")
        await cog.add_guild_manager.callback(cog, request, guild_manager)
        await cog.add_bot_developer.callback(cog, interaction(), developer)
        # A grant in another guild must not demote this guild's developer.
        await db.add_manager(7, 2, PermissionLevel.ADMIN)
        await db.add_manager(8, 2, PermissionLevel.ADMIN)
        await cog.list_managers.callback(cog, request)
        embed = request.followup.send.call_args.kwargs["embed"]
        fields = {field.name: field.value for field in embed.fields}
        assert "<@6>" in fields["Manager"]
        assert "<@7>" in fields["Bot Developer"]
        assert "<@5>" in fields["Supreme Commander"]
        rendered = "\n".join(fields.values())
        assert rendered.count("<@7>") == 1
        assert "<@8>" not in rendered
        bot.fetch_user.assert_not_called()
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_large_manager_list_keeps_every_person_within_embed_limits():
    bot = MagicMock()
    bot.bot_developer_id = 5
    bot.db = AsyncMock()
    bot.db.get_study_group_by_channel.return_value = None
    bot.db.get_commands_channel.return_value = None
    ids = list(range(1000000000000001000, 1000000000000001600))
    bot.db.get_all_managers.return_value = [
        {"guild_id": 1, "user_id": user_id, "permission_level": 3} for user_id in ids
    ]
    bot.get_user.return_value = None
    request = interaction()
    request.guild.get_member.return_value = None
    await Manager.list_managers.callback(Manager(bot), request)
    embeds = [call.kwargs["embed"] for call in request.followup.send.call_args_list]
    assert len(embeds) > 1
    rendered = "\n".join(field.value for embed in embeds for field in embed.fields)
    for user_id in ids:
        assert rendered.count(f"<@{user_id}>") == 1
    for embed in embeds:
        assert len(embed) <= 6000 and len(embed.fields) <= 25
        assert all(len(field.value) <= 1024 for field in embed.fields)


@pytest.mark.asyncio
async def test_resource_maintenance_commands_are_not_registered_in_slash_tree():
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
    try:
        await setup_voice_channels(bot)
        assert bot.get_cog("VoiceChannels") is not None
        for name in ("create_vc", "delete_vc", "delete_role", "create_text_channel", "delete_text_channel"):
            assert bot.tree.get_command(name) is None
    finally:
        await bot.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "group,roster,grant,permissions,expected,number",
    [
        (None, [], None, {}, "Server Member", 0),
        ({"name": "Physics", "owner_id": 9}, [5], None, {}, "Physics Group Member", 1),
        ({"name": "Physics", "owner_id": 5}, [5], None, {}, "Physics Owner", 2),
        ({"name": "Physics", "owner_id": 9}, [], None, {}, "Server Member", 0),
        (
            {"name": "Physics", "owner_id": 5},
            [5],
            {"permission_level": 3, "grant_source": "explicit"},
            {},
            "Manager",
            3,
        ),
        (
            {"name": "Physics", "owner_id": 5},
            [5],
            {"permission_level": 4, "grant_source": "explicit"},
            {},
            "Bot Developer",
            4,
        ),
        (None, [], {"permission_level": 3, "grant_source": "server_sync"}, {"administrator": True}, "Admin", 3),
        (None, [], {"permission_level": 3, "grant_source": "server_sync"}, {"moderate_members": True}, "Mod", 3),
        (None, [], {"permission_level": 3, "grant_source": "server_sync"}, {}, "Server Member", 0),
    ],
)
async def test_user_level_uses_current_group_and_highest_authority(group, roster, grant, permissions, expected, number):
    request = interaction()
    request.channel_id = 20
    request.guild.owner_id = 99
    member = MagicMock(spec=discord.Member)
    member.id = 5
    member.guild = request.guild
    member.display_name = "Impulse"
    member.mention = "<@5>"
    member.guild_permissions = discord.Permissions(**permissions)
    request.user = member
    request.guild.get_member.return_value = member
    bot = MagicMock()
    bot.bot_developer_id = 999
    bot.get_guild.return_value = request.guild
    bot.db = AsyncMock()
    bot.db.get_manager.return_value = {"guild_id": 1, **grant} if grant else None
    bot.db.get_study_group_by_channel.return_value = (
        {"guild_id": 1, "active": 1, "group_id": "group", **group} if group else None
    )
    bot.db.fetch_members_of_group.return_value = roster
    bot.db.get_commands_channel.return_value = None
    cog = Manager(bot)
    await cog.user_level.callback(cog, request)
    embed = request.followup.send.call_args.kwargs["embed"]
    fields = {field.name: field.value for field in embed.fields}
    assert embed.title == "User Authorization Level"
    assert "Impulse" not in embed.title
    assert fields["User Level Tier"] == expected
    assert fields["Permission Level"] == f"Level {number}"
    bot.db.get_user_group.assert_not_awaited()
