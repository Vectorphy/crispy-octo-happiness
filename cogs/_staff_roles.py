"""Synchronize CPO staff roles with stored permission grants in one guild."""

import asyncio
import logging
from typing import Any

import discord

from utils import has_guild_permissions

logger = logging.getLogger(__name__)

MANAGER_ROLE_NAME = "CPO Manager"
DEVELOPER_ROLE_NAME = "CPO Bot Developer"
SUPREME_ROLE_NAME = "CPO Supreme Commander"

_COMMON_ACCESS = (
    "view_channel",
    "send_messages",
    "read_message_history",
    "embed_links",
    "attach_files",
    "connect",
    "speak",
    "stream",
)
_MANAGER_ACCESS = (
    "manage_channels",
    "manage_messages",
    "move_members",
    "mute_members",
    "deafen_members",
)
_DEVELOPER_ACCESS = ("manage_roles", "manage_webhooks")


def _staff_lock(bot: Any, guild_id: int) -> asyncio.Lock:
    locks = bot.__dict__.setdefault("_staff_role_locks", {})
    return locks.setdefault(guild_id, asyncio.Lock())


class StaffRoleSyncError(RuntimeError):
    """A saved staff grant could not be reflected in Discord roles or channels."""


async def log_overwrites(
    bot: Any, guild: discord.Guild, overwrites: Any, *, staff: bool = True
) -> dict[Any, discord.PermissionOverwrite]:
    """Use member grants so stale CPO role membership cannot expose logs."""
    result = {}
    for target, existing in overwrites.items():
        overwrite = discord.PermissionOverwrite.from_pair(*existing.pair())
        overwrite.update(view_channel=False)
        result[target] = overwrite
    default = result.get(guild.default_role, discord.PermissionOverwrite())
    default.update(view_channel=False)
    result[guild.default_role] = default
    for role in guild.roles:
        if role.name in (MANAGER_ROLE_NAME, DEVELOPER_ROLE_NAME, SUPREME_ROLE_NAME):
            access = result.get(role, discord.PermissionOverwrite())
            access.update(view_channel=False)
            result[role] = access
    if guild.me is None:
        raise StaffRoleSyncError("The bot member is unavailable; log privacy cannot be configured.")
    bot_access = result.get(guild.me, discord.PermissionOverwrite())
    bot_access.update(view_channel=True, send_messages=True, embed_links=True, read_message_history=True)
    result[guild.me] = bot_access
    if staff:
        records = await bot.db.get_all_managers(guild.id)
        members = {member.id: member for member in guild.members}
        for record in records:
            member = guild.get_member(int(record["user_id"]))
            if member is not None:
                members[member.id] = member
        for member in members.values():
            if await has_guild_permissions(member, guild, bot):
                access = result.get(member, discord.PermissionOverwrite())
                access.update(view_channel=True, read_message_history=True)
                result[member] = access
    return result


async def sync_log_privacy(bot: Any, guild: discord.Guild, *, staff: bool = True) -> discord.TextChannel | None:
    async with _staff_lock(bot, guild.id):
        return await _sync_log_privacy_locked(bot, guild, staff=staff)


async def _sync_log_privacy_locked(bot: Any, guild: discord.Guild, *, staff: bool) -> discord.TextChannel | None:
    log_id = await bot.db.get_mod_log_channel(guild.id)
    if not isinstance(log_id, int):
        return None
    channel: Any = guild.get_channel(log_id)
    if channel is None:
        channel = await bot.fetch_channel(log_id)
    if not isinstance(channel, discord.TextChannel) or channel.guild.id != guild.id:
        raise StaffRoleSyncError("The saved log channel is unavailable in this server.")
    sealed = await log_overwrites(bot, guild, channel.overwrites, staff=False)
    channel = await channel.edit(overwrites=sealed, reason="CPO log privacy") or channel
    if staff:
        await channel.edit(overwrites=await log_overwrites(bot, guild, sealed), reason="CPO log staff access")
    return channel


def _member_in_guild(member: discord.Member | None, guild: discord.Guild) -> bool:
    return member is not None and member.guild.id == guild.id


def _overwrite(channel: Any, role: discord.Role, *, developer: bool) -> discord.PermissionOverwrite:
    overwrite: discord.PermissionOverwrite = channel.overwrites_for(role)
    for permission in _COMMON_ACCESS + _MANAGER_ACCESS:
        setattr(overwrite, permission, True)
    for permission in _DEVELOPER_ACCESS:
        setattr(overwrite, permission, True if developer else None)
    return overwrite


async def _ensure_role(guild: discord.Guild, name: str) -> discord.Role:
    role = discord.utils.get(guild.roles, name=name)
    if role is None:
        role = await guild.create_role(
            name=name,
            permissions=discord.Permissions.none(),
            mentionable=False,
            reason="CPO staff access",
        )
    elif role.permissions != discord.Permissions.none():
        await role.edit(permissions=discord.Permissions.none(), reason="Limit CPO staff role to category access")
    return role


async def sync_staff_roles(
    bot: Any, guild: discord.Guild, category: discord.CategoryChannel
) -> discord.CategoryChannel:
    """Reflect saved admin/developer grants in roles and CPO channel overwrites.

    The database is authoritative. A failure leaves saved grants intact and raises an
    actionable error; callers should show it after the database operation succeeds.
    """
    if category.guild.id != guild.id:
        raise StaffRoleSyncError("Choose a CPO category from this server before syncing staff roles.")

    async with _staff_lock(bot, guild.id):
        log_channel = await _sync_log_privacy_locked(bot, guild, staff=False)
        me = guild.me
        if me is None or not me.guild_permissions.manage_roles:
            raise StaffRoleSyncError(
                "Give the bot Manage Roles in Server Settings, then retry CPO staff role sync. Saved grants remain active."
            )
        manager_role = discord.utils.get(guild.roles, name=MANAGER_ROLE_NAME)
        developer_role = discord.utils.get(guild.roles, name=DEVELOPER_ROLE_NAME)
        supreme_role = discord.utils.get(guild.roles, name=SUPREME_ROLE_NAME)
        for role in (manager_role, developer_role, supreme_role):
            if role is not None and me.top_role.position <= role.position:
                raise StaffRoleSyncError(
                    f"Move the bot's highest role above {role.name} (ID {role.id}), then retry CPO staff role sync."
                )

        records = await bot.db.get_all_managers(guild.id)
        manager_ids: set[int] = set()
        developer_ids: set[int] = set()
        for record in records:
            level = int(record["permission_level"])
            grant_guild_id = record["guild_id"]
            user_id = int(record["user_id"])
            if dict(record).get("grant_source") == "server_sync":
                member = guild.get_member(user_id)
                if not _member_in_guild(member, guild) or not await has_guild_permissions(member, guild, bot):
                    continue
            if level == 4 and grant_guild_id == guild.id:
                developer_ids.add(user_id)
            elif level == 3 and grant_guild_id == guild.id:
                manager_ids.add(user_id)
        supreme_ids: set[int] = set()
        configured_developer_id = getattr(bot, "bot_developer_id", None)
        if isinstance(configured_developer_id, int) and configured_developer_id > 0:
            supreme_ids.add(configured_developer_id)
        developer_ids -= supreme_ids
        manager_ids -= developer_ids | supreme_ids

        try:
            manager_role = await _ensure_role(guild, MANAGER_ROLE_NAME)
            developer_role = await _ensure_role(guild, DEVELOPER_ROLE_NAME)
            supreme_role = await _ensure_role(guild, SUPREME_ROLE_NAME)
            roles = ((manager_role, False), (developer_role, True), (supreme_role, True))
            for role, _ in roles:
                if me.top_role.position <= role.position:
                    raise StaffRoleSyncError(
                        f"Move the bot's highest role above {role.name} (ID {role.id}), then retry CPO staff role sync."
                    )

            if log_channel is not None:
                sealed = await log_overwrites(bot, guild, log_channel.overwrites, staff=False)
                log_channel = await log_channel.edit(overwrites=sealed, reason="CPO log privacy") or log_channel
                # Discord propagates category edits whenever the overwrite maps match.
                if sealed == category.overwrites:
                    raise StaffRoleSyncError("The log channel needs independent private permissions before staff sync.")

            category_overwrites = dict(category.overwrites)
            for role, developer in roles:
                overwrite = category_overwrites.get(role, discord.PermissionOverwrite())
                for permission in _COMMON_ACCESS + _MANAGER_ACCESS:
                    setattr(overwrite, permission, True)
                for permission in _DEVELOPER_ACCESS:
                    setattr(overwrite, permission, True if developer else None)
                category_overwrites[role] = overwrite
            updated_category = await category.edit(overwrites=category_overwrites, reason="CPO staff access sync")
            if updated_category is None:
                updated_category = category

            for channel in category.channels:
                if log_channel is not None and channel.id == log_channel.id:
                    continue
                for role, developer in roles:
                    overwrite = _overwrite(channel, role, developer=developer)
                    await channel.set_permissions(role, overwrite=overwrite, reason="CPO staff access sync")

            candidates = {member.id: member for member in guild.members if _member_in_guild(member, guild)}
            for user_id in manager_ids | developer_ids | supreme_ids:
                granted_member = guild.get_member(user_id)
                if granted_member is not None and _member_in_guild(granted_member, guild):
                    candidates[user_id] = granted_member
            for member in candidates.values():
                for role, wanted_ids in (
                    (manager_role, manager_ids),
                    (developer_role, developer_ids),
                    (supreme_role, supreme_ids),
                ):
                    has_role = role in member.roles
                    if member.id in wanted_ids and not has_role:
                        await member.add_roles(role, reason="CPO staff grant sync")
                    elif member.id not in wanted_ids and has_role:
                        await member.remove_roles(role, reason="CPO staff grant sync")
            if isinstance(log_channel, discord.TextChannel):
                await log_channel.edit(
                    overwrites=await log_overwrites(bot, guild, log_channel.overwrites), reason="CPO log staff access"
                )
        except discord.HTTPException as exc:
            if log_channel is not None:
                try:
                    await log_channel.edit(
                        overwrites=await log_overwrites(bot, guild, log_channel.overwrites, staff=False),
                        reason="CPO log privacy after failed staff sync",
                    )
                except discord.HTTPException:
                    logger.exception("Cannot reseal log channel guild_id=%s channel_id=%s", guild.id, log_channel.id)
            role_ids = ", ".join(
                str(role.id) for role in (manager_role, developer_role, supreme_role) if role is not None
            )
            logger.exception(
                "CPO staff role sync failed guild_id=%s category_id=%s role_ids=%s", guild.id, category.id, role_ids
            )
            raise StaffRoleSyncError(
                f"Discord could not sync CPO staff roles (IDs: {role_ids or 'none'}) in category {category.id}. "
                "Check the bot's Manage Roles permission, role order, and channel permissions, then retry. "
                "Saved grants remain active."
            ) from exc

        logger.info(
            "CPO staff roles synced guild_id=%s category_id=%s manager_role_id=%s developer_role_id=%s supreme_role_id=%s",
            guild.id,
            category.id,
            manager_role.id,
            developer_role.id,
            supreme_role.id,
        )
        return updated_category
