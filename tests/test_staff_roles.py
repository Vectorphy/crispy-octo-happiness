from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from cogs._staff_roles import StaffRoleSyncError, log_overwrites, sync_staff_roles
from cogs.manager import Manager


def staff_environment():
    guild = MagicMock(spec=discord.Guild)
    guild.id = 1
    guild.roles = []
    guild.me = MagicMock(spec=discord.Member)
    guild.me.top_role.position = 10
    guild.me.guild_permissions = discord.Permissions(manage_roles=True)

    members = {}
    for user_id in (5, 6, 7):
        member = MagicMock(spec=discord.Member)
        member.id = user_id
        member.guild = guild
        member.roles = []
        member.guild_permissions = discord.Permissions.none()

        async def add(role, *, reason, current=member):
            current.roles.append(role)

        async def remove(role, *, reason, current=member):
            current.roles.remove(role)

        member.add_roles = AsyncMock(side_effect=add)
        member.remove_roles = AsyncMock(side_effect=remove)
        members[user_id] = member
    guild.members = list(members.values())
    guild.get_member.side_effect = members.get

    next_role_id = 90

    async def create_role(*, name, permissions, mentionable, reason):
        nonlocal next_role_id
        role = MagicMock(spec=discord.Role)
        role.id = next_role_id
        next_role_id += 1
        role.name = name
        role.permissions = permissions
        role.position = 1
        role.edit = AsyncMock()
        guild.roles.append(role)
        return role

    guild.create_role = AsyncMock(side_effect=create_role)

    category = MagicMock(spec=discord.CategoryChannel)
    category.id = 20
    category.guild = guild
    category.overwrites = {guild.default_role: discord.PermissionOverwrite(manage_threads=False)}

    async def edit_category(*, overwrites, reason):
        category.overwrites = overwrites
        return category

    category.edit = AsyncMock(side_effect=edit_category)
    text = MagicMock(spec=discord.TextChannel)
    text.set_permissions = AsyncMock()
    text.overwrites_for.side_effect = lambda role: discord.PermissionOverwrite(use_external_emojis=False)
    voice = MagicMock(spec=discord.VoiceChannel)
    voice.set_permissions = AsyncMock()
    voice.overwrites_for.side_effect = lambda role: discord.PermissionOverwrite(priority_speaker=False)
    category.channels = [text, voice]

    bot = MagicMock()
    bot.bot_developer_id = 6
    bot.db = AsyncMock()
    bot.db.get_all_managers.return_value = [
        {"user_id": 5, "guild_id": guild.id, "permission_level": 3},
        {"user_id": 7, "guild_id": 2, "permission_level": 4},
    ]
    return bot, guild, category, text, voice, members


@pytest.mark.asyncio
async def test_revoked_native_staff_loses_role_despite_stale_synced_grant():
    bot, guild, category, _, _, members = staff_environment()
    record = {"user_id": 5, "guild_id": guild.id, "permission_level": 3, "grant_source": "server_sync"}
    bot.db.get_all_managers.return_value = [record]
    bot.db.get_manager.return_value = record
    members[5].guild_permissions = discord.Permissions(moderate_members=True)
    await sync_staff_roles(bot, guild, category)
    manager_role = guild.roles[0]
    assert manager_role in members[5].roles

    members[5].guild_permissions = discord.Permissions.none()
    await sync_staff_roles(bot, guild, category)

    assert manager_role not in members[5].roles
    members[5].remove_roles.assert_awaited_once_with(manager_role, reason="CPO staff grant sync")


@pytest.mark.asyncio
async def test_staff_roles_are_scoped_and_category_children_receive_overwrites():
    bot, guild, category, text, voice, members = staff_environment()

    assert await sync_staff_roles(bot, guild, category) is category

    manager_role, developer_role, supreme_role = guild.roles
    assert manager_role.name == "CPO Manager"
    assert developer_role.name == "CPO Bot Developer"
    assert manager_role.permissions == discord.Permissions.none()
    assert developer_role.permissions == discord.Permissions.none()
    assert members[5].roles == [manager_role]
    assert supreme_role.name == "CPO Supreme Commander"
    assert members[6].roles == [supreme_role]
    assert members[7].roles == []
    assert category.overwrites[guild.default_role].manage_threads is False
    assert category.overwrites[manager_role].view_channel is True
    assert category.overwrites[developer_role].manage_roles is True
    for channel in (text, voice):
        assert channel.set_permissions.await_count == 3
        overwrites = {call.args[0]: call.kwargs["overwrite"] for call in channel.set_permissions.await_args_list}
        assert overwrites[manager_role].view_channel is True
        assert overwrites[manager_role].manage_channels is True
        assert overwrites[manager_role].manage_roles is None
        assert overwrites[developer_role].manage_roles is True
        assert overwrites[developer_role].manage_webhooks is True
    assert text.set_permissions.await_args_list[0].kwargs["overwrite"].use_external_emojis is False
    assert voice.set_permissions.await_args_list[0].kwargs["overwrite"].priority_speaker is False


@pytest.mark.asyncio
async def test_demoted_manager_loses_cpo_role_but_configured_developer_keeps_access():
    bot, guild, category, _, _, members = staff_environment()
    await sync_staff_roles(bot, guild, category)
    bot.db.get_all_managers.return_value = []

    await sync_staff_roles(bot, guild, category)

    assert members[5].roles == []
    assert members[6].roles == [guild.roles[2]]
    members[5].remove_roles.assert_awaited_once()
    members[6].remove_roles.assert_not_awaited()
    guild.create_role.assert_awaited()
    assert guild.create_role.await_count == 3


@pytest.mark.asyncio
async def test_sync_returns_refreshed_category_for_new_channel_inheritance():
    bot, guild, category, _, _, _ = staff_environment()
    refreshed = MagicMock(spec=discord.CategoryChannel)
    refreshed.id = category.id
    refreshed.guild = guild
    category.edit = AsyncMock(return_value=refreshed)

    result = await sync_staff_roles(bot, guild, category)

    assert result is refreshed
    overwrites = category.edit.call_args.kwargs["overwrites"]
    assert overwrites[guild.roles[0]].view_channel is True
    assert overwrites[guild.roles[1]].manage_roles is True


@pytest.mark.asyncio
async def test_missing_manage_roles_reports_action_without_mutation():
    bot, guild, category, _, _, _ = staff_environment()
    guild.me.guild_permissions.manage_roles = False

    with pytest.raises(StaffRoleSyncError, match="Manage Roles"):
        await sync_staff_roles(bot, guild, category)

    guild.create_role.assert_not_awaited()
    category.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_role_hierarchy_preflight_does_not_edit_existing_staff_role():
    bot, guild, category, _, _, _ = staff_environment()
    existing_role = MagicMock(spec=discord.Role)
    existing_role.name = "CPO Manager"
    existing_role.id = 91
    existing_role.position = 11
    existing_role.permissions = discord.Permissions.none()
    existing_role.edit = AsyncMock()
    guild.roles = [existing_role]

    with pytest.raises(StaffRoleSyncError, match="highest role"):
        await sync_staff_roles(bot, guild, category)

    guild.create_role.assert_not_awaited()
    existing_role.edit.assert_not_awaited()
    category.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_foreign_category_is_rejected_before_role_creation():
    bot, guild, category, _, _, _ = staff_environment()
    category.guild = MagicMock(spec=discord.Guild)
    category.guild.id = 2

    with pytest.raises(StaffRoleSyncError, match="this server"):
        await sync_staff_roles(bot, guild, category)

    guild.create_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_discord_category_failure_reports_created_role_ids():
    bot, guild, category, _, _, _ = staff_environment()
    category.edit.side_effect = discord.Forbidden(MagicMock(status=403, reason="Forbidden"), "denied")

    with pytest.raises(StaffRoleSyncError, match="IDs: 90, 91"):
        await sync_staff_roles(bot, guild, category)

    bot.db.get_all_managers.assert_awaited_once_with(guild.id)
    assert len(guild.roles) == 3


@pytest.mark.asyncio
async def test_synced_log_stays_private_when_stale_role_removal_fails():
    bot, guild, category, _, _, members = staff_environment()
    guild.default_role.id = 1
    guild.me.id = 100
    guild.me.guild = guild
    bot.db.get_all_managers.return_value = []
    stale_role = await guild.create_role(
        name="CPO Manager", permissions=discord.Permissions.none(), mentionable=False, reason="test"
    )
    members[5].roles = [stale_role]
    members[5].remove_roles.side_effect = discord.Forbidden(MagicMock(status=403), "denied")
    log = MagicMock(spec=discord.TextChannel, id=30, guild=guild)
    category.overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, embed_links=True, read_message_history=True
        ),
    }
    log.overwrites = dict(category.overwrites)
    category.channels = [log]
    bot.db.get_mod_log_channel.return_value = log.id
    guild.get_channel.return_value = log

    async def log_edit(*, overwrites, reason):
        log.overwrites = overwrites
        return log

    async def category_edit(*, overwrites, reason):
        if log.overwrites == category.overwrites:
            log.overwrites = dict(overwrites)
        category.overwrites = overwrites
        assert log.overwrites[stale_role].view_channel is False
        return category

    log.edit = AsyncMock(side_effect=log_edit)
    category.edit = AsyncMock(side_effect=category_edit)
    with pytest.raises(StaffRoleSyncError):
        await sync_staff_roles(bot, guild, category)
    assert stale_role in members[5].roles
    assert log.overwrites[stale_role].view_channel is False
    assert log.overwrites[guild.default_role].view_channel is False
    assert log.overwrites[guild.me].view_channel is True


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["member", "role", "deleted_role", "leave", "join", "owner"])
async def test_authority_events_revoke_stale_direct_log_access(event):
    bot, guild, _, _, _, members = staff_environment()
    guild.owner_id = 999
    guild.me.id = 100
    guild.default_role.id = 1
    record = {"user_id": 5, "guild_id": 1, "permission_level": 3, "grant_source": "server_sync"}
    bot.db.get_all_managers.return_value = [record]
    bot.db.get_manager.return_value = record
    log = MagicMock(spec=discord.TextChannel, id=30, guild=guild)
    log.overwrites = {members[5]: discord.PermissionOverwrite(view_channel=True, send_messages=False)}
    bot.db.get_mod_log_channel.return_value = 30
    guild.get_channel.return_value = log

    async def edit(*, overwrites, reason):
        log.overwrites = overwrites
        return log

    log.edit = AsyncMock(side_effect=edit)
    manager = Manager(bot)
    manager.sync_guild_managers = AsyncMock()
    if event == "member":
        before = MagicMock(spec=discord.Member, guild_permissions=discord.Permissions(moderate_members=True))
        await manager.on_member_update(before, members[5])
    elif event == "role":
        before = MagicMock(spec=discord.Role, permissions=discord.Permissions(moderate_members=True))
        after = MagicMock(spec=discord.Role, guild=guild, permissions=discord.Permissions.none())
        await manager.on_guild_role_update(before, after)
    elif event == "deleted_role":
        await manager.on_guild_role_delete(MagicMock(spec=discord.Role, guild=guild))
    elif event == "leave":
        guild.members.remove(members[5])
        guild.get_member.side_effect = lambda identifier: members.get(identifier) if identifier != 5 else None
        await manager.on_member_remove(members[5])
    elif event == "join":
        await manager.on_member_join(members[5])
    else:
        await manager.on_guild_update(MagicMock(spec=discord.Guild, owner_id=5), guild)
    assert log.overwrites[members[5]].view_channel is False
    assert log.overwrites[members[5]].send_messages is False
    assert log.overwrites[guild.me].view_channel is True


@pytest.mark.asyncio
async def test_authority_refresh_leaves_log_sealed_when_staff_lookup_fails():
    bot, guild, _, _, _, members = staff_environment()
    log = MagicMock(spec=discord.TextChannel, id=30, guild=guild)
    log.overwrites = {members[5]: discord.PermissionOverwrite(view_channel=True)}
    bot.db.get_mod_log_channel.return_value = 30
    bot.db.get_all_managers.side_effect = RuntimeError("unavailable")
    guild.get_channel.return_value = log

    async def edit(*, overwrites, reason):
        log.overwrites = overwrites
        return log

    log.edit = AsyncMock(side_effect=edit)
    manager = Manager(bot)
    manager.sync_guild_managers = AsyncMock()
    await manager._refresh_staff_authority(guild)
    assert log.overwrites[members[5]].view_channel is False


@pytest.mark.asyncio
async def test_identical_private_log_and_category_abort_before_category_allows():
    bot, guild, category, _, _, _ = staff_environment()
    for name in ("CPO Manager", "CPO Bot Developer", "CPO Supreme Commander"):
        await guild.create_role(name=name, permissions=discord.Permissions.none(), mentionable=False, reason="test")
    category.overwrites = await log_overwrites(bot, guild, {}, staff=False)
    log = MagicMock(spec=discord.TextChannel, id=30, guild=guild, overwrites=dict(category.overwrites))
    log.edit = AsyncMock(return_value=log)
    bot.db.get_mod_log_channel.return_value = 30
    guild.get_channel.return_value = log
    with pytest.raises(StaffRoleSyncError, match="independent"):
        await sync_staff_roles(bot, guild, category)
    category.edit.assert_not_awaited()
