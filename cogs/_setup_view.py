import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord

from cogs._staff_roles import StaffRoleSyncError, sync_staff_roles
from utils import DEFAULT_SESSION_DURATION, parse_duration, parse_seconds_to_hms

if TYPE_CHECKING:
    from cogs.manager import Manager

logger = logging.getLogger(__name__)


class CategorySelect(discord.ui.ChannelSelect):
    def __init__(self, view: "SetupView", category: discord.CategoryChannel | None):
        defaults = [category] if category else []
        super().__init__(
            placeholder="Choose a category for study groups",
            channel_types=[discord.ChannelType.category],
            default_values=defaults,
            min_values=1,
            max_values=1,
            row=0,
        )
        self.setup_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.setup_view.saving:
            await interaction.response.send_message("Save is in progress.", ephemeral=True)
            return
        if self.setup_view.has_pending_resources():
            await interaction.response.send_message(
                "Resources were already created. Retry Save or cancel and review the retained IDs.", ephemeral=True
            )
            return
        guild = interaction.guild
        selected = guild.get_channel(self.values[0].id) if guild and self.values else None
        if not isinstance(selected, discord.CategoryChannel):
            await interaction.response.send_message("Choose a category in this server.", ephemeral=True)
            return
        self.setup_view.category_id = selected.id
        self.setup_view.new_category_name = None
        await interaction.response.edit_message(embed=self.setup_view.render(), view=self.setup_view)


class VoiceSelect(discord.ui.ChannelSelect):
    def __init__(self, view: "SetupView", voice: discord.VoiceChannel | None):
        defaults = [voice] if voice else []
        super().__init__(
            placeholder="Choose a default voice channel (optional)",
            channel_types=[discord.ChannelType.voice],
            default_values=defaults,
            min_values=0,
            max_values=1,
            row=2,
        )
        self.setup_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.setup_view.saving:
            await interaction.response.send_message("Save is in progress.", ephemeral=True)
            return
        if self.setup_view.has_pending_resources():
            await interaction.response.send_message(
                "Resources were already created. Retry Save or cancel and review the retained IDs.", ephemeral=True
            )
            return
        guild = interaction.guild
        selected = guild.get_channel(self.values[0].id) if guild and self.values else None
        if selected is not None and not isinstance(selected, discord.VoiceChannel):
            await interaction.response.send_message("Choose a voice channel in this server.", ephemeral=True)
            return
        self.setup_view.default_vc_id = selected.id if selected is not None else None
        await interaction.response.edit_message(embed=self.setup_view.render(), view=self.setup_view)


class NewCategoryModal(discord.ui.Modal, title="Create a study group category"):
    def __init__(self, view: "SetupView"):
        super().__init__()
        self.setup_view = view
        self.name: discord.ui.TextInput[NewCategoryModal] = discord.ui.TextInput(
            label="Category name", default="CPO", max_length=100
        )
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not await self.setup_view.allowed(interaction):
            return
        if self.setup_view.saving:
            await interaction.response.send_message("Save is in progress.", ephemeral=True)
            return
        if self.setup_view.has_pending_resources():
            await interaction.response.send_message(
                "Resources were already created. Retry Save or cancel and review the retained IDs.", ephemeral=True
            )
            return
        name = str(self.name.value).strip()
        if not name:
            await interaction.response.send_message("Enter a category name.", ephemeral=True)
            return
        self.setup_view.new_category_name = name
        self.setup_view.category_id = None
        await interaction.response.defer(ephemeral=True)
        if self.setup_view.message:
            await self.setup_view.message.edit(embed=self.setup_view.render(), view=self.setup_view)
        await interaction.followup.send("Category staged. Save to create it.", ephemeral=True)


class DurationModal(discord.ui.Modal, title="Default session lifetimes"):
    def __init__(self, view: "SetupView"):
        super().__init__()
        self.setup_view = view
        self.group_duration: discord.ui.TextInput[DurationModal] = discord.ui.TextInput(
            label="Study group lifetime", default=parse_seconds_to_hms(view.group_duration), max_length=100
        )
        self.pomodoro_duration: discord.ui.TextInput[DurationModal] = discord.ui.TextInput(
            label="Pomodoro lifetime", default=parse_seconds_to_hms(view.pomodoro_duration), max_length=100
        )
        self.add_item(self.group_duration)
        self.add_item(self.pomodoro_duration)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not await self.setup_view.allowed(interaction):
            return
        if self.setup_view.saving:
            await interaction.response.send_message("Save is in progress.", ephemeral=True)
            return
        group_duration = parse_duration(str(self.group_duration.value).strip())
        pomodoro_duration = parse_duration(str(self.pomodoro_duration.value).strip())
        if not group_duration or not pomodoro_duration or max(group_duration, pomodoro_duration) > 2**63 - 1:
            await interaction.response.send_message("Enter positive lifetimes such as 24h or 1d 12h.", ephemeral=True)
            return
        try:
            now = datetime.now(timezone.utc)
            now + timedelta(seconds=group_duration)
            now + timedelta(seconds=pomodoro_duration)
        except OverflowError:
            await interaction.response.send_message(
                "Those lifetimes are too large. Enter a shorter duration.", ephemeral=True
            )
            return
        self.setup_view.group_duration = group_duration
        self.setup_view.pomodoro_duration = pomodoro_duration
        await interaction.response.defer(ephemeral=True)
        if self.setup_view.message:
            await self.setup_view.message.edit(embed=self.setup_view.render(), view=self.setup_view)
        await interaction.followup.send("Lifetimes staged. Save to apply them to new sessions.", ephemeral=True)


class SetupView(discord.ui.View):
    def __init__(
        self,
        manager: "Manager",
        guild: discord.Guild,
        owner_id: int,
        category_id: int | None,
        commands_channel_id: int | None,
        max_members: int,
        log_channel_id: int | None = None,
        group_duration: int = DEFAULT_SESSION_DURATION,
        pomodoro_duration: int = DEFAULT_SESSION_DURATION,
        default_vc_id: int | None = None,
    ) -> None:
        super().__init__(timeout=300)
        self.manager = manager
        self.guild = guild
        self.owner_id = owner_id
        self.snapshot = (
            category_id,
            commands_channel_id,
            log_channel_id,
            max_members,
            group_duration,
            pomodoro_duration,
            default_vc_id,
        )
        self.default_vc_id = default_vc_id
        self.created_vc_id: int | None = None
        self.moved_vc_id: int | None = None
        self.previous_vc_category_id: int | None = None
        self.group_duration = group_duration
        self.pomodoro_duration = pomodoro_duration
        self.category_id = category_id
        self.new_category_name: str | None = None
        self.max_members = max_members
        self.commands_channel_id = commands_channel_id
        self.log_channel_id = log_channel_id
        self.created_category_id: int | None = None
        self.created_channel_id: int | None = None
        self.created_log_channel_id: int | None = None
        self.moved_channel_id: int | None = None
        self.previous_category_id: int | None = None
        self.moved_log_channel_id: int | None = None
        self.previous_log_category_id: int | None = None
        self.message: discord.WebhookMessage | None = None
        self.saving = False
        category = guild.get_channel(category_id) if category_id is not None else None
        self.add_item(CategorySelect(self, category if isinstance(category, discord.CategoryChannel) else None))
        voice = guild.get_channel(default_vc_id) if default_vc_id is not None else None
        self.add_item(VoiceSelect(self, voice if isinstance(voice, discord.VoiceChannel) else None))

    def render(self) -> discord.Embed:
        if self.new_category_name:
            category = f"Create **{self.new_category_name}** when saved"
        elif self.category_id:
            category = f"<#{self.category_id}>"
        else:
            category = "Choose a category or create one"
        channel = f"<#{self.commands_channel_id}>" if self.commands_channel_id else "Create **#cpo-commands**"
        logs = f"<#{self.log_channel_id}>" if self.log_channel_id else "Create **#cpo-logs**"
        embed = discord.Embed(
            title="Server setup",
            description="Choose the category, review channels and defaults, then save. All channels inherit the category permissions.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Study group category", value=category, inline=False)
        embed.add_field(name="Commands channel", value=channel, inline=False)
        embed.add_field(name="Moderator logs", value=logs, inline=False)
        embed.add_field(
            name="Default voice channel",
            value=f"<#{self.default_vc_id}>" if self.default_vc_id else "Create **CPO Lobby**",
            inline=False,
        )
        embed.add_field(name="Default group size", value=str(self.max_members), inline=True)
        embed.add_field(name="Group lifetime", value=parse_seconds_to_hms(self.group_duration), inline=True)
        embed.add_field(name="Pomodoro lifetime", value=parse_seconds_to_hms(self.pomodoro_duration), inline=True)
        embed.add_field(
            name="Who sees your replies?",
            value="Normal replies are visible in active study-group channels and the bot commands channel. Replies elsewhere, help, errors, and private task menus are visible only to you to avoid cluttering the server. Report malicious or unintended bot behavior to server staff immediately.",
            inline=False,
        )
        if self.commands_channel_id and self.category_id:
            channel_obj = self.guild.get_channel(self.commands_channel_id)
            if isinstance(channel_obj, discord.TextChannel) and channel_obj.category_id != self.category_id:
                embed.add_field(
                    name="On save",
                    value="Move the recorded commands channel into the selected category. Its permissions will sync to the category.",
                    inline=False,
                )
        if self.log_channel_id and self.category_id:
            log_channel = self.guild.get_channel(self.log_channel_id)
            if isinstance(log_channel, discord.TextChannel) and log_channel.category_id != self.category_id:
                embed.add_field(
                    name="Log channel move",
                    value="Move the recorded log channel into the selected category, syncing its permissions to the category.",
                    inline=False,
                )
        if self.default_vc_id and self.category_id:
            vc_channel = self.guild.get_channel(self.default_vc_id)
            if isinstance(vc_channel, discord.VoiceChannel) and vc_channel.category_id != self.category_id:
                embed.add_field(
                    name="Default VC move",
                    value="Move the recorded default voice channel into the selected category, syncing its permissions to the category.",
                    inline=False,
                )
        if self.new_category_name and (self.commands_channel_id or self.log_channel_id or self.default_vc_id):
            embed.add_field(
                name="On save",
                value="Move the recorded channels into the new category, syncing their permissions to the category.",
                inline=False,
            )
        embed.set_footer(text="Nothing changes until Save. This wizard expires in five minutes.")
        if self.retained_resources():
            embed.add_field(name="Pending Discord changes", value=self.retained_resources(), inline=False)
        return embed

    def disable_controls(self) -> None:
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.ChannelSelect)):
                item.disabled = True

    def has_pending_resources(self) -> bool:
        return any(
            value is not None
            for value in (
                self.created_category_id,
                self.created_channel_id,
                self.created_log_channel_id,
                self.moved_channel_id,
                self.moved_log_channel_id,
                self.created_vc_id,
                self.moved_vc_id,
            )
        )

    async def allowed(self, interaction: discord.Interaction) -> bool:
        if interaction.guild_id != self.guild.id or interaction.user.id != self.owner_id:
            await interaction.response.send_message("This setup session belongs to another user.", ephemeral=True)
            return False
        if self.manager._setup_views.get(self.guild.id) is not self:
            await interaction.response.send_message("A newer setup session is open. Run /setup again.", ephemeral=True)
            return False
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        try:
            level = await self.manager.get_permission_level(self.guild.id, interaction.user.id, member=member)
        except (discord.HTTPException, sqlite3.Error, OSError, RuntimeError, ValueError):
            logger.exception(
                "Could not check setup permission guild_id=%s user_id=%s", self.guild.id, interaction.user.id
            )
            await interaction.response.send_message("Could not verify permissions. Try again.", ephemeral=True)
            return False
        if level < 3:
            await interaction.response.send_message(
                "You no longer have permission to configure this server.", ephemeral=True
            )
            return False
        return True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.allowed(interaction)

    @discord.ui.button(label="Create category", style=discord.ButtonStyle.secondary, row=1)
    async def create_category(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.saving:
            await interaction.response.send_message("Save is in progress.", ephemeral=True)
            return
        if self.has_pending_resources():
            await interaction.response.send_message(
                "Resources were already created. Retry Save or cancel and review the retained IDs.", ephemeral=True
            )
            return
        await interaction.response.send_modal(NewCategoryModal(self))

    @discord.ui.button(label="Edit lifetimes", style=discord.ButtonStyle.secondary, row=1)
    async def edit_lifetimes(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.saving:
            await interaction.response.send_message("Save is in progress.", ephemeral=True)
            return
        await interaction.response.send_modal(DurationModal(self))

    @discord.ui.button(label="Save", style=discord.ButtonStyle.primary, row=1)
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.saving:
            await interaction.response.send_message("Save is in progress.", ephemeral=True)
            return
        self.saving = True
        try:
            await self._save_locked(interaction)
        finally:
            self.saving = False

    async def _save_locked(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        async with self.manager._setup_locks.setdefault(self.guild.id, asyncio.Lock()):
            if self.manager._setup_views.get(self.guild.id) is not self:
                await interaction.followup.send("A newer setup session is open. Run /setup again.", ephemeral=True)
                return
            db = self.manager.bot.db
            try:
                current = (
                    await db.get_group_category(self.guild.id),
                    await db.get_commands_channel(self.guild.id),
                    await db.get_mod_log_channel(self.guild.id),
                    await db.get_default_max_members(self.guild.id),
                    await db.get_default_group_duration(self.guild.id),
                    await db.get_default_pomodoro_duration(self.guild.id),
                    await db.get_default_vc(self.guild.id),
                )
            except (discord.HTTPException, sqlite3.Error, OSError, RuntimeError, ValueError):
                logger.exception("Could not read setup settings guild_id=%s", self.guild.id)
                await interaction.followup.send("Could not read server settings. Retry Save.", ephemeral=True)
                return
            if current != self.snapshot:
                await interaction.followup.send(
                    "Server settings changed. Run /setup to review them again.", ephemeral=True
                )
                return
            me = self.guild.me
            if me is None or not all(
                (
                    me.guild_permissions.manage_channels,
                    me.guild_permissions.view_channel,
                    me.guild_permissions.send_messages,
                    me.guild_permissions.embed_links,
                )
            ):
                await interaction.followup.send(
                    "I need Manage Channels, View Channel, Send Messages, and Embed Links to save this setup.",
                    ephemeral=True,
                )
                return
            category = self.guild.get_channel(self.category_id) if self.category_id is not None else None
            if not isinstance(category, discord.CategoryChannel) and not self.new_category_name:
                await interaction.followup.send("Choose a valid category in this server.", ephemeral=True)
                return
            try:
                if self.new_category_name:
                    category = (
                        self.guild.get_channel(self.created_category_id)
                        if self.created_category_id is not None
                        else None
                    )
                    if not isinstance(category, discord.CategoryChannel):
                        category = await self.guild.create_category(self.new_category_name, reason="CPO server setup")
                        self.created_category_id = category.id
                    self.category_id = category.id
                assert isinstance(category, discord.CategoryChannel)
                category_perms = category.permissions_for(me)
                if not all(
                    (
                        category_perms.manage_channels,
                        category_perms.view_channel,
                        category_perms.send_messages,
                        category_perms.embed_links,
                    )
                ):
                    await interaction.followup.send(
                        "I need Manage Channels, View Channel, Send Messages, and Embed Links in that category."
                        + self.retained_resources(),
                        ephemeral=True,
                    )
                    return

                category = await sync_staff_roles(self.manager.bot, self.guild, category)

                channel_id = self.created_channel_id or self.commands_channel_id
                channel = self.guild.get_channel(channel_id) if channel_id is not None else None
                if not isinstance(channel, discord.TextChannel):
                    channel = await self.guild.create_text_channel(
                        "cpo-commands", category=category, reason="CPO server setup"
                    )
                    self.created_channel_id = channel.id
                elif channel.category_id != category.id or not channel.permissions_synced:
                    previous_category_id = channel.category_id
                    edited_channel = await channel.edit(
                        category=category, sync_permissions=True, reason="CPO server setup"
                    )
                    self.moved_channel_id = channel.id
                    self.previous_category_id = previous_category_id
                    if edited_channel is not None:
                        channel = edited_channel
                channel_perms = channel.permissions_for(me)
                if not all((channel_perms.view_channel, channel_perms.send_messages, channel_perms.embed_links)):
                    await interaction.followup.send(
                        "I need View Channel, Send Messages, and Embed Links in the commands channel."
                        + self.retained_resources(),
                        ephemeral=True,
                    )
                    return
                log_channel_id = self.created_log_channel_id or self.log_channel_id
                log_channel = self.guild.get_channel(log_channel_id) if log_channel_id is not None else None
                if not isinstance(log_channel, discord.TextChannel):
                    log_channel = await self.guild.create_text_channel(
                        "cpo-logs",
                        category=category,
                        overwrites=category.overwrites,
                        reason="CPO server setup",
                    )
                    self.created_log_channel_id = log_channel.id
                elif log_channel.category_id != category.id or not log_channel.permissions_synced:
                    previous_log_category_id = log_channel.category_id
                    edited_log = await log_channel.edit(
                        category=category, sync_permissions=True, reason="CPO server setup"
                    )
                    self.moved_log_channel_id = log_channel.id
                    self.previous_log_category_id = previous_log_category_id
                    if edited_log is not None:
                        log_channel = edited_log
                log_perms = log_channel.permissions_for(me)
                if not all((log_perms.view_channel, log_perms.send_messages, log_perms.embed_links)):
                    await interaction.followup.send(
                        "I need View Channel, Send Messages, and Embed Links in the log channel."
                        + self.retained_resources(),
                        ephemeral=True,
                    )
                    return
                voice_id = self.created_vc_id or self.default_vc_id
                voice = self.guild.get_channel(voice_id) if voice_id is not None else None
                if not isinstance(voice, discord.VoiceChannel):
                    voice = await self.guild.create_voice_channel(
                        "CPO Lobby",
                        category=category,
                        overwrites=category.overwrites,
                        reason="CPO default voice destination",
                    )
                    self.created_vc_id = voice.id
                elif voice.category_id != category.id or not voice.permissions_synced:
                    self.previous_vc_category_id = voice.category_id
                    self.moved_vc_id = voice.id
                    updated_voice = await voice.edit(
                        category=category, sync_permissions=True, reason="CPO default voice destination"
                    )
                    if updated_voice is not None:
                        voice = updated_voice
                voice_perms = voice.permissions_for(me)
                if not all((voice_perms.view_channel, voice_perms.connect, voice_perms.move_members)):
                    await interaction.followup.send(
                        "I need View Channel, Connect, and Move Members permissions in the default voice channel."
                        + self.retained_resources(),
                        ephemeral=True,
                    )
                    return
                await db.save_setup(
                    self.guild.id,
                    category.id,
                    channel.id,
                    self.max_members,
                    log_channel.id,
                    default_group_duration=self.group_duration,
                    default_pomodoro_duration=self.pomodoro_duration,
                    default_vc_id=voice.id,
                )
            except StaffRoleSyncError as error:
                logger.exception("Setup staff-role sync failed guild_id=%s", self.guild.id)
                await interaction.followup.send(str(error) + self.retained_resources(), ephemeral=True)
                return
            except (discord.HTTPException, sqlite3.Error, OSError, RuntimeError, ValueError):
                logger.exception("Setup save failed for guild_id=%s user_id=%s", self.guild.id, self.owner_id)
                await interaction.followup.send(
                    "Setup could not be saved. Retry Save." + self.retained_resources(), ephemeral=True
                )
                return

            self.category_id = category.id
            self.commands_channel_id = channel.id
            self.log_channel_id = log_channel.id
            self.default_vc_id = voice.id
            self.created_vc_id = None
            self.moved_vc_id = None
            self.previous_vc_category_id = None
            self.new_category_name = None
            self.created_category_id = None
            self.created_channel_id = None
            self.created_log_channel_id = None
            self.moved_channel_id = None
            self.previous_category_id = None
            self.moved_log_channel_id = None
            self.previous_log_category_id = None
            self.disable_controls()
            self.stop()
            self.manager._setup_views.pop(self.guild.id, None)
            if self.message:
                try:
                    await self.message.edit(embed=self.render(), view=self)
                except discord.HTTPException:
                    logger.warning("Could not close saved setup view guild_id=%s", self.guild.id)
            await interaction.followup.send(
                f"Setup saved. Study groups: <#{category.id}>. Commands: <#{channel.id}>."
                f" Logs: <#{log_channel.id}>. Default VC: <#{voice.id}>. Default group size: {self.max_members}.",
                ephemeral=True,
            )
            logger.info(
                "Setup saved guild_id=%s user_id=%s category_id=%s channel_id=%s log_channel_id=%s",
                self.guild.id,
                self.owner_id,
                category.id,
                channel.id,
                log_channel.id,
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.saving:
            await interaction.response.send_message("Save is in progress.", ephemeral=True)
            return
        self.disable_controls()
        self.stop()
        self.manager._setup_views.pop(self.guild.id, None)
        retained = self.retained_resources()
        await interaction.response.edit_message(
            content=f"Setup cancelled. No settings changed.{retained}", embed=None, view=self
        )

    async def on_timeout(self) -> None:
        async with self.manager._setup_locks.setdefault(self.guild.id, asyncio.Lock()):
            if self.manager._setup_views.get(self.guild.id) is not self:
                return
            self.disable_controls()
            self.manager._setup_views.pop(self.guild.id, None)
            if self.message:
                try:
                    await self.message.edit(
                        content=f"Setup expired. Run /setup to start again.{self.retained_resources()}",
                        embed=None,
                        view=self,
                    )
                except discord.HTTPException:
                    logger.warning("Could not update expired setup view guild_id=%s", self.guild.id)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item["SetupView"]
    ) -> None:
        logger.error(
            "Setup interaction failed guild_id=%s user_id=%s",
            self.guild.id,
            interaction.user.id,
            exc_info=error,
        )
        message = "Setup could not complete that action. Retry or run /setup again."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            logger.exception("Could not report setup error guild_id=%s", self.guild.id)

    def retained_resources(self) -> str:
        if (
            self.created_category_id is None
            and self.created_channel_id is None
            and self.created_log_channel_id is None
            and self.moved_channel_id is None
            and self.moved_log_channel_id is None
            and self.created_vc_id is None
            and self.moved_vc_id is None
        ):
            return ""
        details = ""
        if (
            self.created_category_id is not None
            or self.created_channel_id is not None
            or self.created_log_channel_id is not None
        ):
            details = (
                " Created Discord resources remain for review:"
                f" category ID {self.created_category_id}, commands channel ID {self.created_channel_id},"
                f" log channel ID {self.created_log_channel_id}."
            )
        if self.moved_channel_id is not None:
            details += (
                f" Channel ID {self.moved_channel_id} was moved from category"
                f" ID {self.previous_category_id}; Save will finish recording the change."
            )
        if self.moved_log_channel_id is not None:
            details += (
                f" Log channel ID {self.moved_log_channel_id} was moved from category"
                f" ID {self.previous_log_category_id}; Save will finish recording the change."
            )
        if self.created_vc_id is not None:
            details += f" Default VC ID {self.created_vc_id} remains for review; retry Save to record it."
        if self.moved_vc_id is not None:
            details += f" Default VC ID {self.moved_vc_id} was moved from category ID {self.previous_vc_category_id}."
        return details
