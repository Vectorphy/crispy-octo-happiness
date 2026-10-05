import asyncio
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import discord

from cogs._staff_roles import StaffRoleSyncError, log_overwrites, sync_staff_roles
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
                "Resources were already created. Retry Save, click 'Recover' to clean them up, or 'Cancel'.",
                ephemeral=True,
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
                "Resources were already created. Retry Save, click 'Recover' to clean them up, or 'Cancel'.",
                ephemeral=True,
            )
            return
        guild = interaction.guild
        selected = guild.get_channel(self.values[0].id) if guild and self.values else None
        if self.values and not isinstance(selected, discord.VoiceChannel):
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
                "Resources were already created. Retry Save, click 'Recover' to clean them up, or 'Cancel'.",
                ephemeral=True,
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


class DefaultRoleSelect(discord.ui.RoleSelect):
    def __init__(self, view: "SetupView"):
        role = view.guild.get_role(view.default_role_id) if view.default_role_id else None
        super().__init__(
            placeholder="Optional role required to use CPO (clear for unrestricted)",
            default_values=[role] if role else [],
            min_values=0,
            max_values=1,
            row=3,
        )
        self.setup_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.setup_view
        if not await view.allowed(interaction):
            return
        if view.saving or view.has_pending_resources():
            await interaction.response.send_message("Finish Save or Recover before changing the role.", ephemeral=True)
            return
        role = view.guild.get_role(self.values[0].id) if self.values else None
        if self.values and (not isinstance(role, discord.Role) or role.guild.id != view.guild.id or role.is_default()):
            await interaction.response.send_message(
                "Choose a role in this server other than @everyone.", ephemeral=True
            )
            return
        view.default_role_id = role.id if role else None
        view.new_role_name = None
        await interaction.response.edit_message(embed=view.render(), view=view)


class NewDefaultRoleModal(discord.ui.Modal, title="Create an optional CPO access role"):
    def __init__(self, view: "SetupView"):
        super().__init__()
        self.setup_view = view
        self.name: discord.ui.TextInput[NewDefaultRoleModal] = discord.ui.TextInput(
            label="Role name", default="CPO Member", max_length=100
        )
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        view = self.setup_view
        if not await view.allowed(interaction):
            return
        if view.saving or view.has_pending_resources():
            await interaction.response.send_message("Finish Save or Recover before changing the role.", ephemeral=True)
            return
        name = str(self.name.value).strip()
        if not name:
            await interaction.response.send_message("Enter a role name.", ephemeral=True)
            return
        view.new_role_name = name
        view.default_role_id = None
        await interaction.response.defer(ephemeral=True)
        if view.message:
            await view.message.edit(embed=view.render(), view=view)
        await interaction.followup.send("Role staged. Save creates it without enrolling anyone.", ephemeral=True)


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
        default_role_id: int | None = None,
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
        self.default_role_id = default_role_id
        self.original_role_id = default_role_id
        self.created_role_id: int | None = None
        self.new_role_name: str | None = None
        self.created_vc_id: int | None = None
        self.moved_vc_id: int | None = None
        self.previous_vc_category_id: int | None = None
        self.previous_vc_overwrites: dict[Any, discord.PermissionOverwrite] | None = None
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
        self.previous_channel_overwrites: dict[Any, discord.PermissionOverwrite] | None = None
        self.moved_log_channel_id: int | None = None
        self.previous_log_category_id: int | None = None
        self.previous_log_overwrites: dict[Any, discord.PermissionOverwrite] | None = None
        self.message: discord.WebhookMessage | None = None
        self.saving = False
        self.operation_id: str | None = None
        self.journal_phase = "prepared"
        self.journal_state: dict[str, Any] | None = None
        category = guild.get_channel(category_id) if category_id is not None else None
        self.add_item(CategorySelect(self, category if isinstance(category, discord.CategoryChannel) else None))
        voice = guild.get_channel(default_vc_id) if default_vc_id is not None else None
        self.add_item(VoiceSelect(self, voice if isinstance(voice, discord.VoiceChannel) else None))
        self.add_item(DefaultRoleSelect(self))
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label == "Recover":
                child.disabled = not self.has_pending_resources()

    @staticmethod
    def encode_acl(overwrites) -> list[dict[str, Any]]:
        result = []
        for target, overwrite in overwrites.items():
            if not isinstance(target, (discord.Role, discord.Member)) or not isinstance(target.id, int):
                raise ValueError("Unknown permission overwrite target")
            allow, deny = overwrite.pair()
            result.append(
                {
                    "target_id": target.id,
                    "target_type": "role" if isinstance(target, discord.Role) else "member",
                    "allow": allow.value,
                    "deny": deny.value,
                }
            )
        return sorted(result, key=lambda value: (value["target_type"], value["target_id"]))

    async def decode_acl(self, entries) -> dict[Any, discord.PermissionOverwrite] | None:
        result = {}
        for entry in entries:
            target = (
                self.guild.get_role(entry["target_id"])
                if entry["target_type"] == "role"
                else self.guild.get_member(entry["target_id"])
            )
            if target is None and entry["target_type"] == "member":
                try:
                    target = await self.guild.fetch_member(entry["target_id"])
                except discord.HTTPException:
                    logger.warning(
                        "Recovery ACL member unavailable guild_id=%s user_id=%s", self.guild.id, entry["target_id"]
                    )
                    return None
            kind = discord.Role if entry["target_type"] == "role" else discord.Member
            if not isinstance(target, kind) or target.id != entry["target_id"] or target.guild.id != self.guild.id:
                return None
            result[target] = discord.PermissionOverwrite.from_pair(
                discord.Permissions(entry["allow"]), discord.Permissions(entry["deny"])
            )
        return result

    @classmethod
    async def from_journal(cls, manager: "Manager", guild: discord.Guild, row: dict[str, Any]) -> "SetupView":
        state = row["state"]
        if state.get("version") != 1 or not isinstance(state.get("mutations"), dict):
            raise ValueError("Unsupported setup recovery journal")
        original, desired = state["original"], state["desired"]
        if len(original) != 7 or len(desired) != 7:
            raise ValueError("Invalid setup recovery settings")
        view = cls(
            manager,
            guild,
            row["owner_id"],
            original[0],
            original[1],
            original[3],
            original[2],
            original[4],
            original[5],
            original[6],
        )
        view.snapshot = tuple(original)
        view.original_role_id = state.get("original_role_id")
        view.default_role_id = state.get("desired_role_id")
        view.operation_id, view.journal_phase, view.journal_state = row["operation_id"], row["phase"], state
        (
            view.category_id,
            view.commands_channel_id,
            view.log_channel_id,
            view.max_members,
            view.group_duration,
            view.pomodoro_duration,
            view.default_vc_id,
        ) = desired
        for key, entry in state["mutations"].items():
            if key not in ("category", "channel", "log_channel", "vc", "role") or entry["action"] not in (
                "create",
                "move",
            ):
                raise ValueError("Invalid setup recovery mutation")
            if entry["status"] == "recovered" or entry.get("id") is None:
                continue
            if entry["action"] == "create":
                setattr(view, "created_" + key + "_id", entry["id"])
            else:
                setattr(view, "moved_" + key + "_id", entry["id"])
                setattr(
                    view,
                    "previous_"
                    + (
                        "category_id" if key == "channel" else ("log" if key == "log_channel" else key) + "_category_id"
                    ),
                    entry["before_category"],
                )
                setattr(
                    view,
                    "previous_" + ("log" if key == "log_channel" else key) + "_overwrites",
                    await view.decode_acl(entry["before_acl"]),
                )
                if key == "channel":
                    view.previous_channel_overwrites = await view.decode_acl(entry["before_acl"])
        return view

    def desired_settings(self) -> list[Any]:
        return [
            self.category_id,
            self.commands_channel_id,
            self.log_channel_id,
            self.max_members,
            self.group_duration,
            self.pomodoro_duration,
            self.default_vc_id,
        ]

    async def write_journal(self) -> None:
        if self.operation_id is None or self.journal_state is None:
            raise RuntimeError("Setup journal is missing")
        await self.manager.bot.db.update_setup_recovery_journal(
            self.guild.id, self.operation_id, self.journal_state, phase=self.journal_phase
        )

    async def prepare_journal(self) -> None:
        db = self.manager.bot.db
        if self.operation_id is None:
            self.operation_id = str(uuid.uuid4())
            self.journal_state = {
                "version": 1,
                "original": list(self.snapshot),
                "desired": self.desired_settings(),
                "mutations": {},
                "original_role_id": self.original_role_id,
                "desired_role_id": self.default_role_id,
            }
        row = await db.get_setup_recovery_journal(self.guild.id)
        if isinstance(row, dict):
            if row["operation_id"] != self.operation_id or row["phase"] != "prepared":
                raise RuntimeError("Another setup operation needs recovery or staff synchronization")
            await self.write_journal()
        else:
            await db.create_setup_recovery_journal(self.guild.id, self.operation_id, self.owner_id, self.journal_state)

    async def recovery_intent(self, key: str) -> None:
        if self.journal_state is not None:
            self.journal_state["mutations"][key]["status"] = "rollback_intent"
            await self.write_journal()

    async def recovery_finished(self, key: str) -> None:
        if self.journal_state is not None:
            self.journal_state["mutations"][key]["status"] = "recovered"
            await self.write_journal()

    async def identify_created_intents(self) -> None:
        if self.journal_state is None:
            return
        for key, entry in self.journal_state["mutations"].items():
            if entry["action"] != "create" or entry.get("id") is not None or entry["status"] == "recovered":
                continue
            bot_user = self.manager.bot.user
            if bot_user is None:
                continue
            reason = f"CPO setup {self.operation_id} {key}"
            matches = []
            try:
                async for audit in self.guild.audit_logs(
                    limit=100,
                    action=discord.AuditLogAction.role_create
                    if key == "role"
                    else discord.AuditLogAction.channel_create,
                ):
                    if audit.reason == reason and audit.user and audit.user.id == bot_user.id and audit.target:
                        matches.append(audit.target.id)
            except discord.HTTPException:
                logger.warning(
                    "Recovery audit proof unavailable guild_id=%s operation_id=%s", self.guild.id, self.operation_id
                )
                continue
            if len(matches) == 1:
                entry["id"], entry["status"] = matches[0], "applied"
                setattr(self, "created_" + key + "_id", matches[0])
                await self.write_journal()

    async def provision_channel(self, key: str, channel_id: int | None, category, name: str):
        assert self.journal_state is not None
        kind = (
            discord.CategoryChannel
            if key == "category"
            else discord.VoiceChannel
            if key == "vc"
            else discord.TextChannel
        )
        created_id = getattr(self, "created_" + key + "_id")
        identifier = created_id or channel_id
        channel: Any = self.guild.get_channel(identifier) if isinstance(identifier, int) else None
        entry = self.journal_state["mutations"].get(key)
        if entry is not None and entry["status"] not in ("applied", "recovered"):
            raise RuntimeError("An uncertain Discord mutation needs recovery before Save")
        if isinstance(identifier, int) and channel is None:
            channel = await self.manager.bot.fetch_channel(identifier)
        if channel is not None and (not isinstance(channel, kind) or channel.guild.id != self.guild.id):
            raise ValueError("The selected setup resource has an unexpected type or guild")
        if entry is not None and entry["status"] == "applied":
            channel = await self.manager.bot.fetch_channel(entry["id"])
            if (
                not isinstance(channel, kind)
                or channel.guild.id != self.guild.id
                or getattr(channel, "category_id", None) != entry["after_category"]
                or self.encode_acl(channel.overwrites) != entry["after_acl"]
            ):
                raise RuntimeError("A retained resource changed; recover before Save")
            return channel
        if isinstance(channel, kind) and key == "category":
            return channel
        if (
            key != "log_channel"
            and isinstance(channel, kind)
            and channel.category_id == category.id
            and channel.permissions_synced
        ):
            return channel
        action = "move" if isinstance(channel, kind) else "create"
        overwrites = category.overwrites if category is not None else {}
        if key == "log_channel":
            overwrites = await log_overwrites(
                self.manager.bot, self.guild, channel.overwrites if isinstance(channel, kind) else overwrites
            )
        expected_acl = self.encode_acl(overwrites)
        entry = {
            "action": action,
            "status": "intent",
            "id": channel.id if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)) else None,
            "after_category": category.id if category is not None else None,
            "after_acl": expected_acl,
        }
        if action == "move":
            assert isinstance(channel, (discord.TextChannel, discord.VoiceChannel))
            entry["before_category"], entry["before_acl"] = channel.category_id, self.encode_acl(channel.overwrites)
            setattr(self, "moved_" + key + "_id", channel.id)
            setattr(
                self,
                "previous_"
                + ("category_id" if key == "channel" else ("log" if key == "log_channel" else key) + "_category_id"),
                channel.category_id,
            )
            setattr(
                self, "previous_" + ("log" if key == "log_channel" else key) + "_overwrites", channel.overwrites.copy()
            )
        self.journal_state["mutations"][key] = entry
        await self.write_journal()
        reason = f"CPO setup {self.operation_id} {key}"
        if action == "move":
            assert isinstance(channel, (discord.TextChannel, discord.VoiceChannel))
            channel = await channel.edit(category=category, overwrites=overwrites, reason=reason) or channel
        elif key == "category":
            channel = await self.guild.create_category(name, reason=reason)
        elif key == "vc":
            channel = await self.guild.create_voice_channel(
                name, category=category, overwrites=category.overwrites, reason=reason
            )
        else:
            channel = await self.guild.create_text_channel(
                name, category=category, overwrites=overwrites, reason=reason
            )
        if not isinstance(channel, kind) or channel.guild.id != self.guild.id:
            raise ValueError("Discord returned a channel in an unexpected guild or with an unexpected type")
        if action == "create":
            setattr(self, "created_" + key + "_id", channel.id)
        entry["id"], entry["status"] = channel.id, "applied"
        await self.write_journal()
        return channel

    async def provision_default_role(self) -> int | None:
        if not self.new_role_name and self.created_role_id is None:
            if self.default_role_id is not None:
                roles = await self.guild.fetch_roles()
                role = discord.utils.get(roles, id=self.default_role_id)
                if role is None or role.is_default():
                    raise ValueError("The selected access role is unavailable")
            return self.default_role_id
        assert self.journal_state is not None
        entry = self.journal_state["mutations"].get("role")
        if entry is not None:
            if entry["status"] != "applied" or not isinstance(entry.get("id"), int):
                raise RuntimeError("An uncertain role creation needs recovery before Save")
            role = discord.utils.get(await self.guild.fetch_roles(), id=entry["id"])
            if role is None or role.name != entry["role_name"] or role.permissions.value != 0 or role.mentionable:
                raise RuntimeError("The created access role changed; recover before Save")
            return role.id
        entry = {"action": "create", "status": "intent", "id": None, "role_name": self.new_role_name}
        self.journal_state["mutations"]["role"] = entry
        await self.write_journal()
        role = await self.guild.create_role(
            name=self.new_role_name or "CPO Member",
            permissions=discord.Permissions.none(),
            mentionable=False,
            reason=f"CPO setup {self.operation_id} role",
        )
        if not isinstance(role, discord.Role) or role.guild.id != self.guild.id:
            raise ValueError("Discord returned an unexpected access role")
        self.created_role_id = role.id
        entry.update(id=role.id, status="applied")
        await self.write_journal()
        return role.id

    def render(self) -> discord.Embed:
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label == "Recover":
                child.disabled = not self.has_pending_resources()
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
            description="Choose the category, review channels and defaults, then save. Moderator logs are private to server staff.",
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
        embed.add_field(
            name="Required access role",
            value=f"Create {self.new_role_name} on Save; nobody is enrolled automatically"
            if self.new_role_name
            else f"<@&{self.default_role_id}>"
            if self.default_role_id
            else "Unrestricted (no required role)",
            inline=False,
        )
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
            if isinstance(item, (discord.ui.Button, discord.ui.ChannelSelect, discord.ui.RoleSelect)):
                item.disabled = True

    def has_pending_resources(self) -> bool:
        if self.journal_phase != "prepared":
            return False
        if self.journal_state is not None and any(
            entry["status"] != "recovered" for entry in self.journal_state["mutations"].values()
        ):
            return True
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
                self.created_role_id,
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
                "Resources were already created. Retry Save, click 'Recover' to clean them up, or 'Cancel'.",
                ephemeral=True,
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

    @discord.ui.button(label="Create access role", style=discord.ButtonStyle.secondary, row=4)
    async def create_access_role(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.saving or self.has_pending_resources():
            await interaction.response.send_message("Finish Save or Recover before changing the role.", ephemeral=True)
            return
        await interaction.response.send_modal(NewDefaultRoleModal(self))

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
            if await db.get_default_role(self.guild.id) != self.original_role_id:
                await interaction.followup.send(
                    "The required role changed. Run /setup to review settings.", ephemeral=True
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
                await self.prepare_journal()
                self.default_role_id = await self.provision_default_role()
                category = await self.provision_channel(
                    "category", self.category_id, None, self.new_category_name or "CPO"
                )
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

                channel = await self.provision_channel("channel", self.commands_channel_id, category, "cpo-commands")
                channel_perms = channel.permissions_for(me)
                if not all((channel_perms.view_channel, channel_perms.send_messages, channel_perms.embed_links)):
                    await interaction.followup.send(
                        "I need View Channel, Send Messages, and Embed Links in the commands channel."
                        + self.retained_resources(),
                        ephemeral=True,
                    )
                    return
                log_channel = await self.provision_channel("log_channel", self.log_channel_id, category, "cpo-logs")
                log_perms = log_channel.permissions_for(me)
                if not all((log_perms.view_channel, log_perms.send_messages, log_perms.embed_links)):
                    await interaction.followup.send(
                        "I need View Channel, Send Messages, and Embed Links in the log channel."
                        + self.retained_resources(),
                        ephemeral=True,
                    )
                    return
                voice = await self.provision_channel("vc", self.default_vc_id, category, "CPO Lobby")
                voice_perms = voice.permissions_for(me)
                if not all((voice_perms.view_channel, voice_perms.connect, voice_perms.move_members)):
                    await interaction.followup.send(
                        "I need View Channel, Connect, and Move Members permissions in the default voice channel."
                        + self.retained_resources(),
                        ephemeral=True,
                    )
                    return
                assert self.journal_state is not None
                self.journal_state["desired"] = [
                    category.id,
                    channel.id,
                    log_channel.id,
                    self.max_members,
                    self.group_duration,
                    self.pomodoro_duration,
                    voice.id,
                ]
                self.journal_state["desired_role_id"] = self.default_role_id
                await self.write_journal()
                await db.save_setup(
                    self.guild.id,
                    category.id,
                    channel.id,
                    self.max_members,
                    log_channel.id,
                    default_group_duration=self.group_duration,
                    default_pomodoro_duration=self.pomodoro_duration,
                    default_vc_id=voice.id,
                    journal_operation_id=self.operation_id,
                    default_role_id=self.default_role_id,
                    update_default_role=True,
                )
                self.journal_phase = "committed"
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

            sync_pending = False
            try:
                await sync_staff_roles(self.manager.bot, self.guild, category)
                await db.delete_setup_recovery_journal(self.guild.id, self.operation_id, phase="committed")
                self.operation_id, self.journal_state = None, None
            except (StaffRoleSyncError, discord.HTTPException, sqlite3.Error, OSError, RuntimeError, ValueError):
                sync_pending = True
                logger.exception(
                    "Setup settings saved; staff synchronization pending guild_id=%s operation_id=%s",
                    self.guild.id,
                    self.operation_id,
                )
                self.journal_phase = "sync_pending"
                try:
                    await self.write_journal()
                except (sqlite3.Error, OSError, RuntimeError, ValueError):
                    logger.exception("Could not record pending staff sync guild_id=%s", self.guild.id)

            self.category_id = category.id
            self.commands_channel_id = channel.id
            self.log_channel_id = log_channel.id
            self.default_vc_id = voice.id
            self.created_role_id = None
            self.new_role_name = None
            self.created_vc_id = None
            self.moved_vc_id = None
            self.previous_vc_category_id = None
            self.previous_vc_overwrites = None
            self.new_category_name = None
            self.created_category_id = None
            self.created_channel_id = None
            self.created_log_channel_id = None
            self.moved_channel_id = None
            self.previous_category_id = None
            self.previous_channel_overwrites = None
            self.moved_log_channel_id = None
            self.previous_log_category_id = None
            self.previous_log_overwrites = None
            self.disable_controls()
            self.stop()
            if not self.has_pending_resources():
                self.manager._setup_views.pop(self.guild.id, None)
            if self.message:
                try:
                    await self.message.edit(embed=self.render(), view=self)
                except discord.HTTPException:
                    logger.warning("Could not close saved setup view guild_id=%s", self.guild.id)
            await interaction.followup.send(
                f"Setup saved. Study groups: <#{category.id}>. Commands: <#{channel.id}>."
                f" Logs: <#{log_channel.id}>. Default VC: <#{voice.id}>. Default group size: {self.max_members}."
                + (
                    " Staff synchronization is pending. Check bot permissions and retry /sync_managers or /setup."
                    if sync_pending
                    else ""
                ),
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

    @discord.ui.button(label="Recover", style=discord.ButtonStyle.danger, row=1)
    async def recover(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.saving:
            await interaction.response.send_message("Save is in progress.", ephemeral=True)
            return
        if not self.has_pending_resources():
            await interaction.response.send_message("No retained resources to recover.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        self.saving = True
        try:
            results = await self.recover_retained_resources(interaction=interaction)
        finally:
            self.saving = False
        summary = self.format_recovery_summary(results)
        if self.message:
            try:
                await self.message.edit(embed=self.render(), view=self)
            except discord.HTTPException:
                logger.warning("Could not update setup view after recovery guild_id=%s", self.guild.id)
        await interaction.followup.send(summary, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.saving:
            await interaction.response.send_message("Save is in progress.", ephemeral=True)
            return
        self.disable_controls()
        self.stop()
        if not self.has_pending_resources():
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
            if not self.has_pending_resources():
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

    async def recover_retained_resources(self, interaction: discord.Interaction | None = None) -> dict[str, Any]:
        async with self.manager._setup_locks.setdefault(self.guild.id, asyncio.Lock()):
            return await self._recover_retained_resources_locked(interaction)

    async def _recovery_ownership(self) -> tuple[tuple[Any, ...], set[int], set[int]]:
        db = self.manager.bot.db
        current = (
            await db.get_group_category(self.guild.id),
            await db.get_commands_channel(self.guild.id),
            await db.get_mod_log_channel(self.guild.id),
            await db.get_default_max_members(self.guild.id),
            await db.get_default_group_duration(self.guild.id),
            await db.get_default_pomodoro_duration(self.guild.id),
            await db.get_default_vc(self.guild.id),
        )
        if self.journal_state is not None and current != self.snapshot:
            raise RuntimeError("Setup settings changed during recovery")
        groups = await db.get_all_study_groups(self.guild.id)
        group_resources = {
            value
            for group in groups
            if group.get("active", 1) and str(group.get("guild_id")) == str(self.guild.id)
            for key in ("text_id", "vc_id", "category_id", "group_role_id")
            if isinstance(value := group.get(key), int)
        }
        settings = (current[0], current[1], current[2], current[6])
        protected = {value for value in settings if isinstance(value, int)} | group_resources
        return settings, protected, group_resources

    async def _may_recover_resource(self, channel_id: int, *, restoring: bool = False) -> bool:
        settings, protected, group_resources = await self._recovery_ownership()
        if restoring:
            original = (self.snapshot[0], self.snapshot[1], self.snapshot[2], self.snapshot[6])
            return channel_id not in group_resources and (channel_id not in protected or settings == original)
        return channel_id not in protected

    async def _recover_retained_resources_locked(
        self, interaction: discord.Interaction | None = None
    ) -> dict[str, Any]:
        failed = {"success": False, "deleted": [], "reverted": [], "skipped": []}
        if interaction is not None:
            if interaction.guild_id != self.guild.id:
                return {**failed, "error": "unauthorized"}
            member = interaction.user if isinstance(interaction.user, discord.Member) else None
            try:
                level = await self.manager.get_permission_level(self.guild.id, interaction.user.id, member=member)
            except (discord.HTTPException, sqlite3.Error, OSError, RuntimeError, ValueError):
                logger.exception(
                    "Recovery authority lookup failed guild_id=%s user_id=%s", self.guild.id, interaction.user.id
                )
                return failed
            if level < 3:
                return {**failed, "error": "unauthorized"}

        if self.journal_phase != "prepared":
            return {**failed, "error": "committed"}
        db = self.manager.bot.db
        try:
            await self.identify_created_intents()
            if self.journal_state is not None and "original_role_id" in self.journal_state:
                if await db.get_default_role(self.guild.id) != self.original_role_id:
                    return {**failed, "error": "settings_changed"}
            await self._recovery_ownership()
        except (sqlite3.Error, OSError, RuntimeError, ValueError, TypeError):
            logger.exception("Recovery ownership lookup failed guild_id=%s", self.guild.id)
            return failed

        deleted: list[int] = []
        reverted: list[int] = []
        skipped: list[int] = []
        if self.created_role_id is not None:
            role_id = self.created_role_id
            try:
                entry = self.journal_state["mutations"]["role"] if self.journal_state else None
                role = discord.utils.get(await self.guild.fetch_roles(), id=role_id)
                if role is None:
                    await self.recovery_finished("role")
                    self.created_role_id = None
                    deleted.append(role_id)
                elif (
                    await db.get_default_role(self.guild.id) == role_id
                    or entry is None
                    or role.permissions.value != 0
                    or role.mentionable
                    or role.name != entry["role_name"]
                    or role.managed
                ):
                    skipped.append(role_id)
                else:
                    members = [member async for member in self.guild.fetch_members(limit=None)]
                    if any(role in member.roles for member in members):
                        skipped.append(role_id)
                    else:
                        await self.recovery_intent("role")
                        _, protected_roles, _ = await self._recovery_ownership()
                        if role_id in protected_roles or await db.get_default_role(self.guild.id) == role_id:
                            raise RuntimeError("The access role is now in use")
                        await role.delete(reason="CPO setup rollback: uncommitted access role")
                        await self.recovery_finished("role")
                        self.created_role_id = None
                        deleted.append(role_id)
            except (discord.HTTPException, sqlite3.Error, OSError, RuntimeError, ValueError):
                logger.exception("Access role recovery retained guild_id=%s role_id=%s", self.guild.id, role_id)
                skipped.append(role_id)
        moved = (
            ("moved_channel_id", "previous_category_id", "previous_channel_overwrites", discord.TextChannel),
            ("moved_log_channel_id", "previous_log_category_id", "previous_log_overwrites", discord.TextChannel),
            ("moved_vc_id", "previous_vc_category_id", "previous_vc_overwrites", discord.VoiceChannel),
        )
        for id_attr, category_attr, acl_attr, channel_type in moved:
            key = id_attr.removeprefix("moved_").removesuffix("_id")
            channel_id = getattr(self, id_attr)
            if channel_id is None:
                continue
            channel = self.guild.get_channel(channel_id)
            if self.journal_state is not None:
                try:
                    channel = await self.manager.bot.fetch_channel(channel_id)
                except discord.NotFound:
                    await self.recovery_finished(key)
                    setattr(self, id_attr, None)
                    setattr(self, category_attr, None)
                    setattr(self, acl_attr, None)
                    reverted.append(channel_id)
                    continue
                except discord.HTTPException:
                    skipped.append(channel_id)
                    continue
            category_id = getattr(self, category_attr)
            category = self.guild.get_channel(category_id) if category_id is not None else None
            overwrites = getattr(self, acl_attr)
            if not isinstance(channel, channel_type) or channel.guild.id != self.guild.id or overwrites is None:
                skipped.append(channel_id)
                continue
            if category_id is not None and not isinstance(category, discord.CategoryChannel):
                skipped.append(channel_id)
                continue
            if self.journal_state is not None:
                entry = self.journal_state["mutations"][key]
                actual_acl = self.encode_acl(channel.overwrites)
                if channel.category_id == entry["before_category"] and actual_acl == entry["before_acl"]:
                    await self.recovery_finished(key)
                    setattr(self, id_attr, None)
                    setattr(self, category_attr, None)
                    setattr(self, acl_attr, None)
                    reverted.append(channel_id)
                    continue
                if channel.category_id != entry["after_category"] or actual_acl != entry["after_acl"]:
                    skipped.append(channel_id)
                    continue
            try:
                await self.recovery_intent(key)
                if not await self._may_recover_resource(channel_id, restoring=True):
                    skipped.append(channel_id)
                    continue
                await channel.edit(
                    category=category if isinstance(category, discord.CategoryChannel) else None,
                    overwrites=overwrites,
                    reason="CPO setup rollback",
                )
                await self.recovery_finished(key)
            except (discord.HTTPException, sqlite3.Error, OSError, RuntimeError, ValueError):
                logger.warning("Recovery restore failed guild_id=%s channel_id=%s", self.guild.id, channel_id)
                skipped.append(channel_id)
                continue
            reverted.append(channel_id)
            setattr(self, id_attr, None)
            setattr(self, category_attr, None)
            setattr(self, acl_attr, None)

        created = (
            ("created_channel_id", discord.TextChannel),
            ("created_log_channel_id", discord.TextChannel),
            ("created_vc_id", discord.VoiceChannel),
            ("created_category_id", discord.CategoryChannel),
        )
        for id_attr, created_type in created:
            key = id_attr.removeprefix("created_").removesuffix("_id")
            channel_id = getattr(self, id_attr)
            if channel_id is None:
                continue
            try:
                owner = await db.get_study_group_by_channel(channel_id)
                if isinstance(owner, dict) and owner.get("active", 1):
                    skipped.append(channel_id)
                    continue
                channel = self.guild.get_channel(channel_id)
                if channel is None or self.journal_state is not None:
                    try:
                        channel = await self.manager.bot.fetch_channel(channel_id)
                    except discord.NotFound:
                        await self.recovery_finished(key)
                        deleted.append(channel_id)
                        setattr(self, id_attr, None)
                        continue
                if not isinstance(channel, created_type) or channel.guild.id != self.guild.id:
                    skipped.append(channel_id)
                    continue
                if self.journal_state is not None:
                    entry = self.journal_state["mutations"][key]
                    actual_category = getattr(channel, "category_id", None)
                    if (
                        actual_category != entry["after_category"]
                        or self.encode_acl(channel.overwrites) != entry["after_acl"]
                    ):
                        skipped.append(channel_id)
                        continue
                if isinstance(channel, discord.CategoryChannel) and channel.channels:
                    skipped.append(channel_id)
                    continue
                await self.recovery_intent(key)
                if not await self._may_recover_resource(channel_id):
                    skipped.append(channel_id)
                    continue
                try:
                    await channel.delete(reason="CPO setup rollback: delete uncommitted resource")
                except discord.NotFound:
                    logger.info(
                        "Recovery resource already deleted guild_id=%s channel_id=%s", self.guild.id, channel_id
                    )
                await self.recovery_finished(key)
            except discord.NotFound:
                await self.recovery_finished(key)
                deleted.append(channel_id)
                setattr(self, id_attr, None)
                continue
            except (discord.HTTPException, sqlite3.Error, OSError, RuntimeError, ValueError, TypeError):
                logger.exception("Recovery deletion failed guild_id=%s channel_id=%s", self.guild.id, channel_id)
                skipped.append(channel_id)
                continue
            deleted.append(channel_id)
            setattr(self, id_attr, None)

        if not self.has_pending_resources():
            if self.operation_id is not None:
                await db.delete_setup_recovery_journal(self.guild.id, self.operation_id, phase="prepared")
                self.operation_id, self.journal_state = None, None
            self.new_category_name = None
            self.category_id, self.commands_channel_id, self.log_channel_id = self.snapshot[:3]
            self.default_vc_id = self.snapshot[6]
            self.default_role_id = self.original_role_id
            self.new_role_name = None
        logger.info(
            "Setup recovery guild_id=%s deleted=%s reverted=%s skipped=%s", self.guild.id, deleted, reverted, skipped
        )
        return {"success": True, "deleted": deleted, "reverted": reverted, "skipped": skipped}

    def format_recovery_summary(self, results: dict[str, Any]) -> str:
        if not results.get("success", False):
            if results.get("error") == "unauthorized":
                return "You do not have permission to recover or delete setup resources."
            return "Recovery could not be completed."
        parts: list[str] = []
        deleted: list[int] = results.get("deleted", [])
        reverted: list[int] = results.get("reverted", [])
        skipped: list[int] = results.get("skipped", [])
        if deleted:
            parts.append(f"Deleted {len(deleted)} uncommitted resource(s)")
        if reverted:
            parts.append(f"Restored {len(reverted)} moved channel(s)")
        if skipped:
            parts.append(f"Retained {len(skipped)} resource(s) due to active ownership or errors")
        if self.journal_state is not None and any(
            entry.get("id") is None and entry["status"] != "recovered"
            for entry in self.journal_state["mutations"].values()
        ):
            parts.append(
                f"Unconfirmed creation remains. Review the Discord audit log for CPO setup {self.operation_id}; no resource will be deleted without matching bot audit evidence"
            )
        if not parts:
            return "No retained resources required recovery."
        return "; ".join(parts) + "."

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
        uncertain = ""
        if (
            self.journal_phase == "prepared"
            and self.journal_state is not None
            and any(
                entry.get("id") is None and entry["status"] != "recovered"
                for entry in self.journal_state["mutations"].values()
            )
        ):
            uncertain = f" An unconfirmed Discord creation is retained for recovery (operation {self.operation_id}). Review the matching bot audit log; resources are never identified by name."
        if (
            self.created_category_id is None
            and self.created_channel_id is None
            and self.created_log_channel_id is None
            and self.moved_channel_id is None
            and self.moved_log_channel_id is None
            and self.created_vc_id is None
            and self.moved_vc_id is None
            and self.created_role_id is None
        ):
            return uncertain
        details = uncertain
        if self.created_role_id is not None:
            details += f" Access role ID {self.created_role_id} remains uncommitted; retry Save or Recover."
        if (
            self.created_category_id is not None
            or self.created_channel_id is not None
            or self.created_log_channel_id is not None
        ):
            details += (
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
