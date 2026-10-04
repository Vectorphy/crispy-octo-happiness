from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from cogs.manager import Manager, PermissionLevel


def _create_interaction():
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.response.send_message = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_remove_bot_developer_authorized():
    bot = MagicMock()
    bot.bot_developer_id = 999
    bot.db = AsyncMock()

    cog = Manager(bot)

    interaction = _create_interaction()
    interaction.user.id = 999
    interaction.user.name = "GlobalDev"
    interaction.guild_id = 123

    target_user = MagicMock(spec=discord.User)
    target_user.id = 777
    target_user.name = "TargetUser"

    cog.get_permission_level = AsyncMock(return_value=PermissionLevel.BOT_DEVELOPER)
    cog._sync_staff_access = AsyncMock(return_value="")
    bot.db.get_manager = AsyncMock(return_value={"permission_level": PermissionLevel.BOT_DEVELOPER})

    with patch("cogs.manager.send_response") as mock_send:
        await cog.remove_bot_developer.callback(cog, interaction, user=target_user)

        bot.db.remove_manager.assert_awaited_once_with(777, None)
        mock_send.assert_awaited_once()
        assert "has been removed as a bot developer" in mock_send.call_args.args[1]


@pytest.mark.asyncio
async def test_remove_bot_developer_rejects_primary():
    bot = MagicMock()
    bot.bot_developer_id = 999
    bot.db = AsyncMock()

    cog = Manager(bot)

    interaction = _create_interaction()
    interaction.user.id = 1234
    interaction.guild_id = 123

    target_user = MagicMock(spec=discord.User)
    target_user.id = 999

    cog.get_permission_level = AsyncMock(return_value=PermissionLevel.BOT_DEVELOPER)

    with patch("cogs.manager.send_response") as mock_send:
        await cog.remove_bot_developer.callback(cog, interaction, user=target_user)

        bot.db.remove_manager.assert_not_awaited()
        mock_send.assert_awaited_once()
        assert "primary bot developer" in mock_send.call_args.args[1]


@pytest.mark.asyncio
async def test_self_role_update_attempt_blocks_and_dms():
    bot = MagicMock()
    bot.bot_developer_id = 999
    bot.db = AsyncMock()

    bot.db.get_all_managers.return_value = [
        {"user_id": 888, "guild_id": 123, "permission_level": 4},
    ]

    primary_dev = MagicMock(spec=discord.User)
    primary_dev.send = AsyncMock()

    server_dev = MagicMock(spec=discord.User)
    server_dev.send = AsyncMock()

    async def fetch_user(uid):
        if uid == 999:
            return primary_dev
        if uid == 888:
            return server_dev
        return None

    bot.get_user = MagicMock(return_value=None)
    bot.fetch_user = AsyncMock(side_effect=fetch_user)

    cog = Manager(bot)

    interaction = _create_interaction()
    interaction.user.id = 777
    interaction.user.name = "RogueUser"
    interaction.guild_id = 123
    interaction.guild.name = "Test Server"
    interaction.channel.name = "general"

    target_user = MagicMock(spec=discord.User)
    target_user.id = 777

    cog.get_permission_level = AsyncMock(return_value=PermissionLevel.REGULAR_USER)

    with patch("cogs.manager.send_response") as mock_send:
        await cog.add_bot_developer.callback(cog, interaction, user=target_user)

        primary_dev.send.assert_awaited_once()
        server_dev.send.assert_awaited_once()

        embed = primary_dev.send.call_args.kwargs["embed"]
        assert "Self-Role Update Attempt" in embed.title

        mock_send.assert_awaited_once()
        assert "Go away peasent" in mock_send.call_args.args[1]

    mock_send.reset_mock()
    primary_dev.send.reset_mock()

    cog.get_permission_level = AsyncMock(return_value=PermissionLevel.BOT_DEVELOPER)
    with patch("cogs.manager.send_response") as mock_send:
        await cog.add_bot_developer.callback(cog, interaction, user=target_user)

        primary_dev.send.assert_awaited_once()
        mock_send.assert_awaited_once()
        assert "You cannot update your own roles or permissions." in mock_send.call_args.args[1]


@pytest.mark.asyncio
async def test_add_guild_manager_rejects_non_server_member():
    bot = MagicMock()
    bot.db = AsyncMock()

    cog = Manager(bot)

    interaction = _create_interaction()
    interaction.user.id = 111
    interaction.guild_id = 123

    target_user = MagicMock(spec=discord.User)
    target_user.id = 222

    interaction.guild.get_member = MagicMock(return_value=None)
    interaction.guild.fetch_member = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Not found"))

    cog.get_permission_level = AsyncMock(return_value=PermissionLevel.ADMIN)

    with patch("cogs.manager.send_response") as mock_send:
        await cog.add_guild_manager.callback(cog, interaction, user=target_user)

        bot.db.add_manager.assert_not_awaited()
        mock_send.assert_awaited_once()
        assert "This user is not a member of this server." in mock_send.call_args.args[1]


@pytest.mark.asyncio
async def test_remove_guild_manager_rejects_non_server_non_manager():
    bot = MagicMock()
    bot.db = AsyncMock()

    cog = Manager(bot)

    interaction = _create_interaction()
    interaction.user.id = 111
    interaction.guild_id = 123

    target_user = MagicMock(spec=discord.User)
    target_user.id = 222
    target_user.name = "Stranger"

    cog.get_permission_level = AsyncMock(return_value=PermissionLevel.ADMIN)
    interaction.guild.get_member = MagicMock(return_value=None)
    bot.db.remove_manager = AsyncMock(return_value=0)

    with patch("cogs.manager.send_response") as mock_send:
        await cog.remove_guild_manager.callback(cog, interaction, user=target_user)

        mock_send.assert_awaited_once()
        assert "This user is not a member of this server." in mock_send.call_args.args[1]


@pytest.mark.asyncio
async def test_remove_guild_manager_rejects_member_non_manager():
    bot = MagicMock()
    bot.db = AsyncMock()

    cog = Manager(bot)

    interaction = _create_interaction()
    interaction.user.id = 111
    interaction.guild_id = 123

    target_user = MagicMock(spec=discord.User)
    target_user.id = 222
    target_user.name = "RegularMember"

    cog.get_permission_level = AsyncMock(return_value=PermissionLevel.ADMIN)
    interaction.guild.get_member = MagicMock(return_value=target_user)
    bot.db.remove_manager = AsyncMock(return_value=0)

    with patch("cogs.manager.send_response") as mock_send:
        await cog.remove_guild_manager.callback(cog, interaction, user=target_user)

        mock_send.assert_awaited_once()
        assert "is not a guild manager for this server." in mock_send.call_args.args[1]


@pytest.mark.asyncio
async def test_leave_group_fallback_rejects_non_group_member():
    bot = MagicMock()
    bot.db = AsyncMock()

    from cogs.study_groups import StudyGroupCog

    cog = StudyGroupCog(bot)

    interaction = _create_interaction()
    interaction.user.id = 111
    interaction.guild_id = 123
    interaction.channel.id = 456

    cog.get_study_group_by_channel = MagicMock(return_value=None)
    bot.db.fetch_members_of_group = AsyncMock(return_value=[222, 333])
    bot.db.get_study_group_by_channel = AsyncMock(
        return_value={"group_id": 10, "guild_id": 123, "text_id": 456, "name": "Test Group"}
    )

    with patch("cogs.study_groups.send_response") as mock_send:
        await cog.leave_group.callback(cog, interaction)

        bot.db.remove_member_from_group.assert_not_awaited()
        mock_send.assert_awaited_once()
        assert "You are not a member of study group" in mock_send.call_args.args[1]
