"""Move a noncompliant study member to the saved default voice destination."""

import logging
import sqlite3

import discord

logger = logging.getLogger(__name__)


async def relocate_to_default_vc(member: discord.Member, db, source_id: int, group_id: str) -> bool:
    guild = member.guild
    try:
        destination_id = await db.get_default_vc(guild.id)
        destination = guild.get_channel(destination_id) if destination_id else None
        me = guild.me
        error = None
        if not isinstance(destination, discord.VoiceChannel) or destination.id == source_id:
            error = "The default voice channel is missing. Ask staff to save /setup again."
        elif destination.guild.id != guild.id:
            error = "The default voice channel does not belong to this server. Ask staff to save /setup again."
        elif (
            me is None
            or not destination.permissions_for(me).connect
            or not destination.permissions_for(me).move_members
            or not member.voice
            or not member.voice.channel
            or not member.voice.channel.permissions_for(me).move_members
        ):
            error = "The bot needs Connect and Move Members permission in the default voice channel."
        elif destination.user_limit and len(destination.members) >= destination.user_limit:
            error = "The default voice channel is full. Ask staff to make space."
        if error:
            logger.warning(
                "Voice relocation unavailable guild_id=%s group_id=%s user_id=%s reason=%s",
                guild.id,
                group_id,
                member.id,
                error,
            )
            try:
                await member.send(error)
            except discord.HTTPException:
                logger.warning("Could not send relocation failure guild_id=%s user_id=%s", guild.id, member.id)
            return False
        if not member.voice or not member.voice.channel or member.voice.channel.id != source_id:
            return False
        assert isinstance(destination, discord.VoiceChannel)  # narrowed by isinstance guard above
        await member.move_to(destination, reason=f"Video required in study group {group_id}")
        logger.info(
            "Voice member relocated guild_id=%s group_id=%s user_id=%s destination_id=%s",
            guild.id,
            group_id,
            member.id,
            destination_id,
        )
        return True
    except (discord.HTTPException, sqlite3.Error, OSError, RuntimeError, ValueError):
        logger.exception("Voice relocation failed guild_id=%s group_id=%s user_id=%s", guild.id, group_id, member.id)
        try:
            await member.send(
                "I could not move you to the default voice channel. Ask staff to check Move Members and channel access."
            )
        except discord.HTTPException:
            logger.warning("Could not send relocation failure guild_id=%s user_id=%s", guild.id, member.id)
        return False
