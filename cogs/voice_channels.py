import logging
import sqlite3
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils import acknowledge_interaction, get_context_group, is_group_creator, send_response, should_use_ephemeral

logger = logging.getLogger(__name__)


class VoiceChannels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("VoiceChannels cog initialized")

    @app_commands.command(name="create_vc", description="Create a voice channel for the study group")
    @app_commands.describe(name="Name of the voice channel (optional)")
    @is_group_creator()
    async def create_vc(self, interaction: discord.Interaction, name: Optional[str] = None):
        logger.info(f"create_vc command invoked by {interaction.user}")
        await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        if not interaction.guild:
            await send_response(interaction, "This command can only be used in a server.", ephemeral=True)
            return

        group = await get_context_group(interaction, self.bot.db)
        if not group:
            logger.warning(f"No study group exists in server {interaction.guild_id}")
            await send_response(interaction, "No study group exists in this server.", ephemeral=True)
            return

        group_id = group.get("group_id") or group.get("id")
        group_vc_id = group.get("vc_id")
        group_name = group.get("name")

        if group_vc_id:
            logger.warning(f"Voice channel already exists for group {group_id}")
            await send_response(interaction, "A voice channel already exists for this group.", ephemeral=True)
            return

        channel_name = name or f"{group_name} VC"
        logger.debug(f"Creating voice channel '{channel_name}'")
        text_id = group.get("text_id")
        source = interaction.guild.get_channel(text_id) if isinstance(text_id, int) else None
        category = getattr(source, "category", None)
        if not isinstance(category, discord.CategoryChannel):
            category_id = await self.bot.db.get_group_category(interaction.guild.id)
            category = interaction.guild.get_channel(category_id) if category_id else None
        if not isinstance(category, discord.CategoryChannel):
            await send_response(interaction, "Choose a study category in /setup first.")
            return
        me = interaction.guild.me
        if me is None or not category.permissions_for(me).manage_channels:
            await send_response(interaction, "I need Manage Channels in the study category.")
            return

        channel = None
        try:
            channel = await interaction.guild.create_voice_channel(
                channel_name, category=category, reason="Study group voice channel"
            )
            await self.bot.db.update_voice_channel(group_id, channel.id)
        except (discord.HTTPException, sqlite3.Error, RuntimeError, OSError):
            logger.exception("Voice channel creation failed guild_id=%s group_id=%s", interaction.guild.id, group_id)
            retained = ""
            if channel is not None:
                try:
                    await channel.delete(reason="Study group voice channel persistence failed")
                except discord.HTTPException:
                    logger.exception(
                        "Voice channel rollback failed guild_id=%s group_id=%s channel_id=%s",
                        interaction.guild.id,
                        group_id,
                        channel.id,
                    )
                    retained = f" Channel ID {channel.id} remains and needs moderator cleanup."
            await send_response(interaction, "Failed to create the voice channel. Please try again later." + retained)
            return

        group_cog = self.bot.get_cog("StudyGroupCog")
        groups = getattr(group_cog, "active_study_groups", None)
        if isinstance(groups, dict):
            live_group = groups.get(str(group_id))
            if live_group is not None:
                live_group.vc_id = channel.id
        logger.info(
            "Voice channel created guild_id=%s group_id=%s channel_id=%s",
            interaction.guild.id,
            group_id,
            channel.id,
        )
        await send_response(
            interaction, f"Voice channel {channel.mention} created for the study group.", ephemeral=ephemeral
        )

    @app_commands.command(name="delete_vc", description="Delete the selected VC from the Server")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(voice_channel="Select the VC to delete")
    @is_group_creator()
    async def delete_vc(self, interaction: discord.Interaction, voice_channel: discord.VoiceChannel):
        await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        if not interaction.guild:
            await send_response(interaction, "This command can only be used in a server.", ephemeral=True)
            return
        logger.info(f"delete_vc command invoked by {interaction.user.display_name} in guild {interaction.guild.name}")

        group = await get_context_group(interaction, self.bot.db)
        if not group:
            logger.warning(f"No study group found in server {interaction.guild_id}")
            await send_response(interaction, "No study group exists for this server.", ephemeral=True)
            return

        group_id = group.get("group_id") or group.get("id")
        group_vc_id = group.get("vc_id")

        if voice_channel.id != group_vc_id:
            logger.warning(f"Voice channel {voice_channel.id} is not associated with the study group {group_id}")
            await send_response(
                interaction,
                "This voice channel is not associated with the current study group.",
                ephemeral=True,
            )
            return

        try:
            await voice_channel.delete(reason="Voice channel deleted by group creator")
            await self.bot.db.update_voice_channel(group_id, None)
            logger.info(f"Voice channel {voice_channel.id} deleted for group {group_id}")
            if interaction.response.is_done():
                await send_response(interaction, "Voice channel deleted successfully.", ephemeral=ephemeral)
            else:
                await send_response(interaction, "Voice channel deleted successfully.", ephemeral=ephemeral)
        except discord.HTTPException as e:
            logger.error(f"Failed to delete voice channel {voice_channel.id}: {str(e)}")
            if interaction.response.is_done():
                await send_response(
                    interaction,
                    "Failed to delete the voice channel. Please try again later.",
                    ephemeral=True,
                )
            else:
                await send_response(
                    interaction,
                    "Failed to delete the voice channel. Please try again later.",
                    ephemeral=True,
                )

    @app_commands.command(name="delete_role", description="Delete the selected role for the study group")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(role="Select the Role to delete")
    @is_group_creator()
    async def delete_role(self, interaction: discord.Interaction, role: discord.Role):
        await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        if not interaction.guild:
            await send_response(interaction, "This command can only be used in a server.", ephemeral=True)
            return
        logger.info(f"delete_role command invoked by {interaction.user.display_name} in guild {interaction.guild.name}")

        group = await get_context_group(interaction, self.bot.db)
        if not group:
            logger.warning(f"No study group found in server {interaction.guild_id}")
            await send_response(interaction, "No study group exists for this server.", ephemeral=True)
            return

        group_id = group.get("group_id") or group.get("id")
        group_role_id = group.get("group_role_id")

        if role.id != group_role_id:
            logger.warning(f"Role {role.id} is not associated with the study group {group_id}")
            await send_response(
                interaction,
                "This role is not associated with the current study group.",
                ephemeral=True,
            )
            return

        try:
            await role.delete(reason="Role deleted by group creator")
            await self.bot.db.update_group_roles(group_id, None, None)
            logger.info(f"Role {role.id} deleted for group {group_id}")
            if interaction.response.is_done():
                await send_response(interaction, "Role deleted successfully.", ephemeral=ephemeral)
            else:
                await send_response(interaction, "Role deleted successfully.", ephemeral=ephemeral)
        except discord.HTTPException as e:
            logger.error(f"Failed to delete role {role.id}: {str(e)}")
            if interaction.response.is_done():
                await send_response(interaction, "Failed to delete the role. Please try again later.", ephemeral=True)
            else:
                await send_response(interaction, "Failed to delete the role. Please try again later.", ephemeral=True)

    @app_commands.command(
        name="delete_text_channel",
        description="Delete the selected text channel for the study group",
    )
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(text_channel="Select the Text Channel to delete")
    @is_group_creator()
    async def delete_text_channel(self, interaction: discord.Interaction, text_channel: discord.TextChannel):
        await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        if not interaction.guild:
            await send_response(interaction, "This command can only be used in a server.", ephemeral=True)
            return
        logger.info(
            f"delete_text_channel command invoked by {interaction.user.display_name} in guild {interaction.guild.name}"
        )

        group = await get_context_group(interaction, self.bot.db)
        if not group:
            logger.warning(f"No study group found in server {interaction.guild_id}")
            await send_response(interaction, "No study group exists for this server.", ephemeral=True)
            return

        group_id = group.get("group_id") or group.get("id")
        group_text_id = group.get("text_id")

        if text_channel.id != group_text_id:
            logger.warning(f"Text channel {text_channel.id} is not associated with the study group {group_id}")
            await send_response(
                interaction,
                "This text channel is not associated with the current study group.",
                ephemeral=True,
            )
            return

        try:
            await text_channel.delete(reason="Text channel deleted by group creator")
            if "group_id" in group.keys():
                await self.bot.db.update_study_group_by_id({"group_id": group["group_id"], "text_id": 0})
            logger.info(f"Text channel {text_channel.id} deleted for group {group_id}")
            if interaction.response.is_done():
                await send_response(interaction, "Text channel deleted successfully.", ephemeral=ephemeral)
            else:
                await send_response(interaction, "Text channel deleted successfully.", ephemeral=ephemeral)
        except discord.HTTPException as e:
            logger.error(f"Failed to delete text channel {text_channel.id}: {str(e)}")
            if interaction.response.is_done():
                await send_response(
                    interaction,
                    "Failed to delete the text channel. Please try again later.",
                    ephemeral=True,
                )
            else:
                await send_response(
                    interaction,
                    "Failed to delete the text channel. Please try again later.",
                    ephemeral=True,
                )


async def setup(bot):
    cog = VoiceChannels(bot)
    await bot.add_cog(cog)
    for command in cog.get_app_commands():
        bot.tree.remove_command(command.name)
    logger.info("VoiceChannels maintenance helpers loaded without public slash commands")
