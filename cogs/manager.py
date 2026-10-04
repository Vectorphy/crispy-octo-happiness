import asyncio
import logging
import sqlite3
from enum import IntEnum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs._setup_view import SetupView
from cogs._staff_roles import StaffRoleSyncError, sync_staff_roles
from utils import acknowledge_interaction, send_response, should_use_ephemeral

# Set up logging
logger = logging.getLogger(__name__)


class PermissionLevel(IntEnum):
    BOT_DEVELOPER = 4
    ADMIN = 3
    GUILD_MANAGER = 3  # Backward-compatible alias
    MODERATOR = 3
    GROUP_OWNER = 2
    GROUP_MEMBER = 1
    SERVER_MEMBER = 0
    REGULAR_USER = 0  # Compatibility for existing callers


class Manager(commands.Cog):
    max_sessions = 5
    max_groups = 6
    max_overall = 10

    @staticmethod
    def get_tier_name(level: int) -> str:
        if level >= PermissionLevel.BOT_DEVELOPER:
            return "Bot Developer"
        if level >= PermissionLevel.ADMIN:
            return "Manager"
        if level >= PermissionLevel.GROUP_OWNER:
            return "Group Owner"
        if level >= PermissionLevel.GROUP_MEMBER:
            return "Group Member"
        return "Server Member"

    def __init__(self, bot):
        self.bot = bot
        self._setup_locks: Dict[int, asyncio.Lock] = {}
        self._setup_views: Dict[int, SetupView] = {}
        logger.info("Manager cog initialized")

    async def _sync_staff_access(self, interaction: discord.Interaction, *, global_scope: bool = False) -> str:
        guilds = {interaction.guild.id: interaction.guild} if interaction.guild else {}
        if global_scope:
            guilds.update({guild.id: guild for guild in self.bot.guilds})
        warnings = []
        for guild in guilds.values():
            try:
                category_id = await self.bot.db.get_group_category(guild.id)
                category = guild.get_channel(category_id) if isinstance(category_id, int) else None
                if not isinstance(category, discord.CategoryChannel):
                    warnings.append(f"Server {guild.id}: run /setup to synchronize CPO staff roles.")
                    continue
                await sync_staff_roles(self.bot, guild, category)
            except (StaffRoleSyncError, sqlite3.Error, OSError):
                logger.exception("CPO staff-role synchronization failed guild_id=%s", guild.id)
                warnings.append(
                    f"Server {guild.id}: CPO role synchronization failed. Check Manage Roles and bot role hierarchy, then retry /sync_managers."
                )
        return "\n" + "\n".join(warnings) if warnings else ""

    ### --- DECORATOR FUNCTIONS --- ###

    # Decorator to check if user is a member
    @staticmethod
    def is_member(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(instance, interaction: discord.Interaction, *args, **kwargs):
            user_id = interaction.user.id
            member_list: List[int] = []
            class_name: str = ""
            session_name: str = ""
            logger.info(f"Checking if user {interaction.user.display_name} is a member...")

            # Check for CheckinSession
            if instance.__class__.__name__ == "CheckinSession":
                member_list = instance.member_ids
                class_name = type(instance).__name__
                session_name = instance.name
                logger.info("Instance is of type CheckinSession")

            # Check for StudyGroup
            if instance.__class__.__name__ == "StudyGroup":
                member_list = instance.member_ids
                class_name = type(instance).__name__
                session_name = instance.name
                logger.info("Instance is of type StudyGroup")

            if user_id in member_list:
                logger.info(
                    f"User {interaction.user.display_name} is a member of {class_name} with name: {session_name}"
                )
                return await func(instance, interaction, *args, **kwargs)
            else:
                logger.warning(
                    f"User {interaction.user.display_name} is not a member of {class_name} with name: {session_name}"
                )
                await interaction.response.send_message(
                    f"You are not a member of this {class_name} with name: {session_name}.",
                    ephemeral=True,
                )

        return wrapper

    # Decorator to check if user is the owner
    @staticmethod
    def is_owner(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(instance, interaction: discord.Interaction, *args, **kwargs):
            user_id = interaction.user.id
            owner_id: int = 0
            class_name: str = ""
            session_name: str = ""
            logger.info(f"Checking if user {interaction.user.display_name} is a member...")

            # Check for CheckinSession
            if instance.__class__.__name__ == "CheckinSession":
                owner_id = instance.owner_id
                class_name = type(instance).__name__
                session_name = instance.name
                logger.info("Instance is of type CheckinSession")

            # Check for StudyGroup
            if instance.__class__.__name__ == "StudyGroup":
                owner_id = instance.owner_id
                class_name = type(instance).__name__
                session_name = instance.name
                logger.info("Instance is of type StudyGroup")

            if user_id == owner_id:
                logger.info(
                    f"User {interaction.user.display_name} is a the owner of {class_name} with name: {session_name}"
                )
                return await func(instance, interaction, *args, **kwargs)
            else:
                logger.warning(
                    f"User {interaction.user.display_name} is not the owner of {class_name} with name: {session_name}"
                )
                await interaction.response.send_message(
                    f"You are not the owner of this {class_name} with name: {session_name}.",
                    ephemeral=True,
                )

        return wrapper

    ## Check the max sessions / groups of a user
    ## Expand as neeeded for other group / modules
    @staticmethod
    def check_user_groups(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(cog_instance, interaction: discord.Interaction, *args, **kwargs):
            logger.info(f"Checking if user {interaction.user.display_name} can join more modules...")
            user_id = interaction.user.id
            class_name = ""
            checkin_count = 0
            study_group_count = 0
            overall_count = 0

            # Check user participation in 'CheckinSession's
            if cog_instance.__class__.__name__ == "CheckinCog":
                class_name = type(cog_instance).__name__
                logger.info("Instance is of type CheckinCog")
                checkin_count = sum(user_id in session.member_ids for session in cog_instance.active_sessions.values())
                overall_count += checkin_count
                logger.info(f"User {interaction.user.display_name} has {checkin_count} checkin sessions")
                if checkin_count >= Manager.max_sessions:
                    logger.info(
                        f"User {interaction.user.display_name} has joined {checkin_count} checkin sessions, more than the limit of {Manager.max_sessions}"
                    )
                    await interaction.response.send_message(
                        f"You are already in {checkin_count} check-in sessions. You can't join more.",
                        ephemeral=True,
                    )
                    return

            # Check user participation in StudyGroups
            if cog_instance.__class__.__name__ == "StudyGroupCog":
                class_name = type(cog_instance).__name__
                logger.info("Instance is of type StudyGroupCog")
                study_group_count = sum(
                    user_id in study_group.member_ids for study_group in cog_instance.active_study_groups.values()
                )
                overall_count += study_group_count
                logger.info(f"User {interaction.user.display_name} has {study_group_count} study groups")
                if study_group_count >= Manager.max_groups:
                    logger.info(
                        f"User {interaction.user.display_name} has joined {study_group_count} study groups, more than the limit of {Manager.max_groups}"
                    )
                    await interaction.response.send_message(
                        f"You are already in {study_group_count} study groups. You can't join more.",
                        ephemeral=True,
                    )
                    return

            # Check overall participation limit
            if overall_count >= Manager.max_overall:
                logger.info(
                    f"User {interaction.user.display_name} has joined {overall_count} total modules, more than the limit of {Manager.max_overall}"
                )
                await interaction.response.send_message(
                    f"You are already in {overall_count} total groups/sessions. You can't join more.",
                    ephemeral=True,
                )
                return

            # If checks pass, proceed to the function
            logger.info(f"User {interaction.user.display_name} can this module of {class_name}")
            return await func(cog_instance, interaction, *args, **kwargs)

        return wrapper

    async def get_permission_level(
        self,
        guild_id: Optional[int],
        user_id: int,
        member: Optional[discord.Member] = None,
    ) -> PermissionLevel:
        if user_id == self.bot.bot_developer_id:
            logger.debug(f"User {user_id} identified as bot developer")
            return PermissionLevel.BOT_DEVELOPER

        guild = self.bot.get_guild(guild_id) if guild_id else None
        if not member and guild:
            member = guild.get_member(user_id)
        if member and (member.id != user_id or member.guild.id != guild_id):
            member = None

        native_level = PermissionLevel.REGULAR_USER
        if member and member.guild and member.guild.owner_id == user_id:
            logger.debug(f"User {user_id} identified as server owner (Admin)")
            native_level = PermissionLevel.ADMIN
        elif guild and guild.owner_id == user_id:
            logger.debug(f"User {user_id} identified as server owner (Admin)")
            native_level = PermissionLevel.ADMIN

        if member:
            perms = member.guild_permissions
            if perms.administrator or perms.manage_guild:
                logger.debug(f"User {user_id} identified as admin via administrator permission")
                native_level = PermissionLevel.ADMIN
            elif (
                perms.manage_guild
                or perms.manage_channels
                or perms.manage_roles
                or perms.moderate_members
                or perms.kick_members
                or perms.ban_members
            ):
                logger.debug(f"User {user_id} identified as moderator via permissions")
                native_level = max(native_level, PermissionLevel.MODERATOR)

        manager = await self.bot.db.get_manager(user_id, guild_id)
        if isinstance(manager, (dict, sqlite3.Row)):
            if dict(manager).get("grant_source") == "server_sync":
                return native_level
            permission_level = manager["permission_level"]
            grant_guild_id = manager["guild_id"]
            if grant_guild_id != guild_id and not (grant_guild_id is None and permission_level == 4):
                return native_level
            logger.debug(f"User {user_id} has permission level {permission_level}")
            try:
                return max(native_level, PermissionLevel(permission_level))
            except ValueError:
                return native_level
        return native_level

    async def sync_guild_managers(self, guild: discord.Guild) -> List[discord.Member]:
        """Auto-detect server owner, administrators, and moderators, registering them into the database."""
        synced_members: List[discord.Member] = []
        grants: Dict[int, int] = {guild.owner_id: int(PermissionLevel.ADMIN)} if guild.owner_id else {}
        try:
            owner = guild.owner
            if not owner and guild.owner_id:
                try:
                    owner = await guild.fetch_member(guild.owner_id)
                except Exception:
                    owner = guild.get_member(guild.owner_id)

            if owner:
                grants[owner.id] = int(PermissionLevel.ADMIN)
                synced_members.append(owner)
                logger.info(f"Auto-synced server owner {owner.display_name} ({owner.id}) as ADMIN for guild {guild.id}")

            for member in guild.members:
                if member.bot or (owner and member.id == owner.id):
                    continue
                perms = member.guild_permissions
                if perms.administrator or perms.manage_guild:
                    grants[member.id] = int(PermissionLevel.ADMIN)
                    synced_members.append(member)
                    logger.info(
                        f"Auto-synced administrator {member.display_name} ({member.id}) as ADMIN for guild {guild.id}"
                    )
                elif (
                    perms.manage_guild
                    or perms.manage_channels
                    or perms.manage_roles
                    or perms.moderate_members
                    or perms.kick_members
                    or perms.ban_members
                ):
                    grants[member.id] = int(PermissionLevel.MODERATOR)
                    synced_members.append(member)
                    logger.info(
                        f"Auto-synced moderator {member.display_name} ({member.id}) as MODERATOR for guild {guild.id}"
                    )

            await self.bot.db.sync_guild_manager_grants(guild.id, grants)

        except Exception as e:
            logger.error(f"Error in sync_guild_managers for guild {guild.id}: {e}")

        return synced_members

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            try:
                await self.sync_guild_managers(guild)
                category_id = await self.bot.db.get_group_category(guild.id)
                category = guild.get_channel(category_id) if isinstance(category_id, int) else None
                if isinstance(category, discord.CategoryChannel):
                    await sync_staff_roles(self.bot, guild, category)
            except Exception as e:
                logger.warning(f"Could not sync managers for guild {guild.id}: {e}")

    @app_commands.command(
        name="setup",
        description="View or configure server settings for study groups (Mods/Admin only)",
    )
    @app_commands.describe(
        max_members="Default maximum members per study group (1-50)",
        category="Category where new study group channels will be placed",
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        max_members: Optional[app_commands.Range[int, 1, 50]] = None,
        category: Optional[discord.CategoryChannel] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        if interaction.guild is None or interaction.guild_id is None:
            await interaction.followup.send("Set up this bot inside a server.", ephemeral=True)
            return
        level = await self.get_permission_level(
            interaction.guild_id,
            interaction.user.id,
            member=(interaction.user if isinstance(interaction.user, discord.Member) else None),
        )
        if level < PermissionLevel.MODERATOR:
            await interaction.followup.send(
                "You must be server staff (Level 3) or a Bot Developer to use this command.",
                ephemeral=True,
            )
            return

        if category is not None and (
            not isinstance(category, discord.CategoryChannel) or category.guild.id != interaction.guild_id
        ):
            await interaction.followup.send("Choose a category in this server.", ephemeral=True)
            return

        async with self._setup_locks.setdefault(interaction.guild_id, asyncio.Lock()):
            current_cat_id = await self.bot.db.get_group_category(interaction.guild_id)
            current_channel_id = await self.bot.db.get_commands_channel(interaction.guild_id)
            current_log_channel_id = await self.bot.db.get_mod_log_channel(interaction.guild_id)
            current_max = await self.bot.db.get_default_max_members(interaction.guild_id)
            current_group_duration = await self.bot.db.get_default_group_duration(interaction.guild_id)
            current_pomodoro_duration = await self.bot.db.get_default_pomodoro_duration(interaction.guild_id)
            current_default_vc_id = await self.bot.db.get_default_vc(interaction.guild_id)
            view = SetupView(
                self,
                interaction.guild,
                interaction.user.id,
                category.id if category is not None else current_cat_id,
                current_channel_id,
                max_members if max_members is not None else current_max,
                current_log_channel_id,
                current_group_duration,
                current_pomodoro_duration,
                current_default_vc_id,
            )
            view.snapshot = (
                current_cat_id,
                current_channel_id,
                current_log_channel_id,
                current_max,
                current_group_duration,
                current_pomodoro_duration,
                current_default_vc_id,
            )
            prior = self._setup_views.get(interaction.guild_id)
            if prior:
                prior.stop()
            self._setup_views[interaction.guild_id] = view
        view.message = await interaction.followup.send(embed=view.render(), view=view, ephemeral=True, wait=True)

    @app_commands.command(
        name="sync_commands",
        description="Synchronize application slash commands with Discord (Admin only)",
    )
    @app_commands.describe(guild_only="If true, syncs only to this server. If false, syncs globally.")
    async def sync_commands(self, interaction: discord.Interaction, guild_only: bool = False):
        await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        if not interaction.guild and guild_only:
            await send_response(interaction, "Guild-only sync can only be used inside a server.", ephemeral=True)
            return

        level = await self.get_permission_level(
            interaction.guild_id,
            interaction.user.id,
            member=(interaction.user if isinstance(interaction.user, discord.Member) else None),
        )
        if level < PermissionLevel.ADMIN:
            await send_response(
                interaction,
                "You must be an Administrator or Bot Developer to sync commands.",
                ephemeral=True,
            )
            return

        try:
            if guild_only and interaction.guild:
                self.bot.tree.copy_global_to(guild=interaction.guild)
                synced = await self.bot.tree.sync(guild=interaction.guild)
                await send_response(
                    interaction,
                    f"Successfully synced **{len(synced)}** command(s) to server **{interaction.guild.name}**.",
                    ephemeral=ephemeral,
                )
            else:
                synced = await self.bot.tree.sync()
                await send_response(
                    interaction,
                    f"Successfully synced **{len(synced)}** command(s) globally across all servers.",
                    ephemeral=ephemeral,
                )
            logger.info(f"Slash commands synced by {interaction.user.display_name} (guild_only={guild_only})")
        except Exception as e:
            logger.exception(f"Error syncing commands: {e}")
            await send_response(interaction, f"Failed to sync commands: {e}", ephemeral=True)

    @app_commands.command(
        name="user_level",
        description="Check a member’s server or study-group authorization level",
    )
    @app_commands.describe(user="The member to inspect (defaults to yourself)")
    async def user_level(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        await acknowledge_interaction(interaction)
        target_member = user or (interaction.user if isinstance(interaction.user, discord.Member) else None)
        if interaction.guild is None or target_member is None or target_member.guild.id != interaction.guild.id:
            await send_response(interaction, "Choose a member of this server.")
            return
        level = await self.get_permission_level(interaction.guild_id, target_member.id, member=target_member)
        label = "Server Member"
        if level == PermissionLevel.BOT_DEVELOPER:
            label = "Bot Developer"
        elif level >= PermissionLevel.ADMIN:
            record = await self.bot.db.get_manager(target_member.id, interaction.guild_id)
            explicit = (
                isinstance(record, (dict, sqlite3.Row)) and dict(record).get("grant_source", "explicit") == "explicit"
            )
            if explicit:
                label = "Manager"
            elif (
                target_member.id == interaction.guild.owner_id
                or target_member.guild_permissions.administrator
                or target_member.guild_permissions.manage_guild
            ):
                label = "Admin"
            else:
                label = "Mod"
        else:
            group = await self.bot.db.get_study_group_by_channel(interaction.channel_id)
            if isinstance(group, dict) and group.get("guild_id") == interaction.guild.id and group.get("active", 1):
                if target_member.id == group.get("owner_id"):
                    level = PermissionLevel.GROUP_OWNER
                    label = f"{group['name']} Owner"
                elif target_member.id in await self.bot.db.fetch_members_of_group(
                    group.get("group_id") or group.get("id")
                ):
                    level = PermissionLevel.GROUP_MEMBER
                    label = f"{group['name']} Group Member"
                else:
                    level = PermissionLevel.SERVER_MEMBER
            else:
                level = PermissionLevel.SERVER_MEMBER
        color = discord.Color.gold() if level >= PermissionLevel.ADMIN else discord.Color.blue()
        embed = discord.Embed(title="User Authorization Level", color=color)
        embed.add_field(name="Member", value=target_member.mention, inline=False)
        embed.add_field(name="User Level Tier", value=label, inline=True)
        embed.add_field(name="Permission Level", value=f"Level {int(level)}", inline=True)
        embed.set_footer(text=f"User ID: {target_member.id}")
        await send_response(interaction, embed=embed, ephemeral=await should_use_ephemeral(interaction, self.bot.db))

    @app_commands.command(
        name="sync_managers",
        description="Automatically detect server owner and moderators and grant manager roles (Admin only)",
    )
    async def sync_managers(self, interaction: discord.Interaction):
        await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        if not interaction.guild:
            await send_response(interaction, "This command can only be used in a server.", ephemeral=True)
            return

        level = await self.get_permission_level(
            interaction.guild_id,
            interaction.user.id,
            member=(interaction.user if isinstance(interaction.user, discord.Member) else None),
        )
        if level < PermissionLevel.ADMIN:
            await send_response(interaction, "You don't have permission to use this command.", ephemeral=True)
            return

        synced = await self.sync_guild_managers(interaction.guild)
        role_warnings = await self._sync_staff_access(interaction)
        names = ", ".join(m.display_name for m in synced[:15])
        if len(synced) > 15:
            names += f" and {len(synced) - 15} others"

        await send_response(
            interaction,
            f"Successfully synced **{len(synced)}** server owner & moderator members in the database:\n{names or 'None detected'}"
            + role_warnings,
            ephemeral=ephemeral,
        )

    @app_commands.command(name="add_bot_developer", description="Add a bot developer (Bot Developer only)")
    @app_commands.describe(user="The user to add as a bot developer")
    async def add_bot_developer(self, interaction: discord.Interaction, user: discord.User):
        await acknowledge_interaction(interaction)
        if await self.get_permission_level(interaction.guild_id, interaction.user.id) != PermissionLevel.BOT_DEVELOPER:
            await send_response(interaction, "You don't have permission to use this command.")
            return
        await self.bot.db.add_manager(user.id, None, PermissionLevel.BOT_DEVELOPER)
        role_warnings = await self._sync_staff_access(interaction, global_scope=True)
        logger.info(
            "Bot developer added guild_id=%s actor_id=%s user_id=%s", interaction.guild_id, interaction.user.id, user.id
        )
        await send_response(
            interaction,
            f"{user.name} has been added as a bot developer." + role_warnings,
            ephemeral=await should_use_ephemeral(interaction, self.bot.db),
        )

    @app_commands.command(name="add_guild_manager", description="Add a guild manager (Admin only)")
    @app_commands.describe(user="The user to add as a guild manager")
    async def add_guild_manager(self, interaction: discord.Interaction, user: discord.User):
        await acknowledge_interaction(interaction)
        if interaction.guild is None:
            await send_response(interaction, "This command can only be used in a server.")
            return
        if await self.get_permission_level(interaction.guild_id, interaction.user.id) < PermissionLevel.ADMIN:
            await send_response(interaction, "You don't have permission to use this command.")
            return
        await self.bot.db.add_manager(user.id, interaction.guild_id, PermissionLevel.ADMIN)
        role_warnings = await self._sync_staff_access(interaction)
        logger.info(
            "Guild manager added guild_id=%s actor_id=%s user_id=%s", interaction.guild_id, interaction.user.id, user.id
        )
        await send_response(
            interaction,
            f"{user.name} has been added as a guild manager for this server." + role_warnings,
            ephemeral=await should_use_ephemeral(interaction, self.bot.db),
        )

    @app_commands.command(name="remove_guild_manager", description="Remove a guild manager (Admin only)")
    @app_commands.describe(user="The user to remove as a guild manager")
    async def remove_guild_manager(self, interaction: discord.Interaction, user: discord.User):
        await acknowledge_interaction(interaction)
        if interaction.guild is None:
            await send_response(interaction, "This command can only be used in a server.")
            return
        logger.info(f"Attempt to remove guild manager: {user.id} by user: {interaction.user.id}")
        if await self.get_permission_level(interaction.guild_id, interaction.user.id) < PermissionLevel.ADMIN:
            logger.warning(f"User {interaction.user.id} attempted to remove guild manager without permission")
            await send_response(interaction, "You don't have permission to use this command.")
            return

        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        await self.bot.db.remove_manager(user.id, interaction.guild_id)
        role_warnings = await self._sync_staff_access(interaction)
        logger.info(f"Removed {user.id} as guild manager for guild {interaction.guild_id}")
        await send_response(
            interaction,
            f"{user.name} has been removed as a guild manager for this server." + role_warnings,
            ephemeral=ephemeral,
        )

    @app_commands.command(name="list_managers", description="List all managers and staff for this server")
    async def list_managers(self, interaction: discord.Interaction):
        await acknowledge_interaction(interaction)
        if interaction.guild is None:
            await send_response(interaction, "This command can only be used in a server.")
            return
        if await self.get_permission_level(interaction.guild_id, interaction.user.id) < PermissionLevel.MODERATOR:
            await send_response(interaction, "You don't have permission to use this command.")
            return
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        records = await self.bot.db.get_all_managers(interaction.guild_id)
        levels: Dict[int, int] = {}
        sources: Dict[int, str] = {}
        for record in records:
            if record["guild_id"] != interaction.guild_id and not (
                record["guild_id"] is None and record["permission_level"] == PermissionLevel.BOT_DEVELOPER
            ):
                continue
            user_id = record["user_id"]
            if user_id not in levels or record["permission_level"] > levels[user_id]:
                levels[user_id] = record["permission_level"]
                sources[user_id] = dict(record).get("grant_source", "explicit")
        developer_id = self.bot.bot_developer_id
        if isinstance(developer_id, int):
            levels[developer_id] = PermissionLevel.BOT_DEVELOPER

        categories: Dict[str, List[str]] = {
            "Bot Developer": [],
            "Manager": [],
            "Admin": [],
            "Mod": [],
            "Other Levels": [],
        }
        for user_id, level in sorted(levels.items(), key=lambda item: (-item[1], item[0])):
            user = interaction.guild.get_member(user_id) or self.bot.get_user(user_id)
            label = f"{user.display_name[:80]} (<@{user_id}>)" if user else f"<@{user_id}>"
            if level >= PermissionLevel.BOT_DEVELOPER:
                categories["Bot Developer"].append(label)
            elif level >= PermissionLevel.ADMIN:
                category = "Manager"
                if sources.get(user_id) == "server_sync":
                    member = interaction.guild.get_member(user_id)
                    category = (
                        "Admin"
                        if user_id == interaction.guild.owner_id
                        or (
                            member and (member.guild_permissions.administrator or member.guild_permissions.manage_guild)
                        )
                        else "Mod"
                    )
                categories[category].append(label)
            else:
                categories["Other Levels"].append(f"{label} (Level {level})")

        pages = [discord.Embed(title="Server Staff & Managers", color=discord.Color.blue())]
        for category, labels in categories.items():
            chunk = ""
            chunks = []
            for label in labels:
                if len(chunk) + len(label) + 1 > 1024:
                    chunks.append(chunk)
                    chunk = ""
                chunk = f"{chunk}\n{label}" if chunk else label
            if chunk:
                chunks.append(chunk)
            for value in chunks:
                page = pages[-1]
                if len(page.fields) >= 25 or len(page) + len(category) + len(value) > 5500:
                    page = discord.Embed(title="Server Staff & Managers", color=discord.Color.blue())
                    pages.append(page)
                page.add_field(name=category, value=value, inline=False)
        if not levels:
            pages[0].description = "No managers found. Add a manager or use `/sync_managers` to import server staff."
        for number, page in enumerate(pages, 1):
            page.set_footer(text=f"{len(levels)} people • Page {number} of {len(pages)}")
            await send_response(
                interaction, embed=page, ephemeral=ephemeral, allowed_mentions=discord.AllowedMentions.none()
            )
        logger.info(
            "Managers listed guild_id=%s user_id=%s count=%s", interaction.guild_id, interaction.user.id, len(levels)
        )

    @app_commands.command(
        name="set_permission_level",
        description="Set the permission level for a user (Bot Developer only)",
    )
    @app_commands.describe(
        user="The user to set permissions for",
        level="Server grant: 0 removes it, 3 grants Manager, 4 grants Bot Developer",
    )
    async def set_permission_level(self, interaction: discord.Interaction, user: discord.User, level: int):
        await acknowledge_interaction(interaction)
        logger.info(
            f"Attempt to set permission level for user {user.id} to level {level} by user {interaction.user.id}"
        )
        if await self.get_permission_level(interaction.guild_id, interaction.user.id) != PermissionLevel.BOT_DEVELOPER:
            logger.warning(
                f"User {interaction.user.id} attempted to set permission level without being a Bot Developer"
            )
            await send_response(interaction, "You don't have permission to use this command.")
            return

        if level not in [0, 3, 4]:
            logger.warning(f"Invalid permission level {level} specified")
            await send_response(
                interaction,
                "Invalid permission level. Use 0 (Server Member), 3 (Manager), or 4 (Bot Developer). Group membership and ownership come from group commands.",
            )
            return

        if interaction.guild is None and level != PermissionLevel.BOT_DEVELOPER:
            await send_response(interaction, "Server grants can only be changed inside a server.")
            return

        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        if level == PermissionLevel.REGULAR_USER:
            await self.bot.db.remove_manager(user.id, interaction.guild_id)
            logger.info(f"Removed all permissions for user {user.id}")
        else:
            guild_id = None if level == PermissionLevel.BOT_DEVELOPER else interaction.guild_id
            await self.bot.db.add_manager(user.id, guild_id, level)
            logger.info(f"Set permission level {level} for user {user.id} in guild {guild_id}")

        permission_names = {
            PermissionLevel.REGULAR_USER: "Server Member",
            PermissionLevel.GROUP_MEMBER: "Group Member",
            PermissionLevel.GROUP_OWNER: "Group Owner",
            PermissionLevel.ADMIN: "Manager",
            PermissionLevel.BOT_DEVELOPER: "Bot Developer",
        }
        name_str = permission_names.get(PermissionLevel(level), str(level))
        role_warnings = await self._sync_staff_access(interaction, global_scope=level == PermissionLevel.BOT_DEVELOPER)
        await send_response(
            interaction, f"Set {user.name}'s permission level to {name_str}." + role_warnings, ephemeral=ephemeral
        )


async def setup(bot):
    await bot.add_cog(Manager(bot))
    logger.info("Manager cog loaded")
