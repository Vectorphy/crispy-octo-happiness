"""Current guild membership and the optional setup access role."""

import asyncio
import logging
import sqlite3
from typing import Any

import discord
from discord import app_commands

logger = logging.getLogger(__name__)


async def require_guild_access(
    bot: Any, interaction: discord.Interaction, *, guild_id: int | None = None, setup_exempt: bool = False
) -> bool:
    try:
        return await asyncio.wait_for(
            _require_guild_access(bot, interaction, guild_id=guild_id, setup_exempt=setup_exempt), timeout=2
        )
    except TimeoutError:
        logger.warning(
            "Guild access lookup timed out guild_id=%s user_id=%s",
            guild_id or interaction.guild_id,
            interaction.user.id,
        )
        return False


async def _require_guild_access(
    bot: Any, interaction: discord.Interaction, *, guild_id: int | None = None, setup_exempt: bool = False
) -> bool:
    guild_id = guild_id if guild_id is not None else interaction.guild_id
    if guild_id is None:
        return True
    guild = bot.get_guild(guild_id)
    if guild is None and interaction.guild is not None and interaction.guild.id == guild_id:
        guild = interaction.guild
    if guild is None or guild.id != guild_id or (interaction.guild_id is not None and interaction.guild_id != guild_id):
        return False
    try:
        member = interaction.user
        if not isinstance(member, discord.Member) or member.guild.id != guild_id:
            member = await guild.fetch_member(interaction.user.id)
        if not isinstance(member, discord.Member) or member.id != interaction.user.id or member.guild.id != guild_id:
            return False
        if setup_exempt:
            manager = bot.get_cog("Manager")
            return manager is not None and await manager.get_permission_level(guild_id, member.id, member=member) >= 3
        role_id = await bot.db.get_default_role(guild_id)
        member = await guild.fetch_member(interaction.user.id)
        if not isinstance(member, discord.Member) or member.id != interaction.user.id or member.guild.id != guild_id:
            return False
        if role_id is None:
            return True
        if type(role_id) is not int or guild.get_role(role_id) is None:
            return False
        return any(role.id == role_id for role in member.roles)
    except (discord.HTTPException, sqlite3.Error, OSError, RuntimeError, ValueError):
        logger.exception("Guild access could not be verified guild_id=%s user_id=%s", guild_id, interaction.user.id)
        return False


async def deny_access(interaction: discord.Interaction) -> None:
    message = "You must be a current member of this server with its configured CPO access role. Ask server staff to review Setup."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


class AccessCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        command_data: Any = interaction.data or {}
        command_name = command_data.get("name")
        if await require_guild_access(self.client, interaction, setup_exempt=command_name == "setup"):
            return True
        await deny_access(interaction)
        return False


def _context_guild(view: Any) -> int | None:
    for value in (
        view,
        getattr(view, "group", None),
        getattr(view, "study_group", None),
        getattr(view, "session", None),
    ):
        identifier = getattr(value, "guild_id", None)
        if type(identifier) is int and identifier > 0:
            return identifier
        guild = getattr(value, "guild", None)
        if guild is not None and type(getattr(guild, "id", None)) is int:
            return guild.id
    return None


class AccessView(discord.ui.View):
    guild_id: int | None = None
    group: Any = None
    session: Any = None

    async def _scheduled_task(self, item: Any, interaction: discord.Interaction) -> None:
        if not await require_guild_access(interaction.client, interaction, guild_id=_context_guild(self)):
            await deny_access(interaction)
            return
        await super()._scheduled_task(item, interaction)


class AccessModal(discord.ui.Modal):
    async def _scheduled_task(self, *args: Any, **kwargs: Any) -> None:
        interaction = args[0]
        if not await require_guild_access(interaction.client, interaction, guild_id=_context_guild(self)):
            await deny_access(interaction)
            return
        await super()._scheduled_task(*args, **kwargs)
