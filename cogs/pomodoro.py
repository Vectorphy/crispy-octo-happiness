import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set, Tuple

import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs._session_controls import request_session_end
from utils import (
    acknowledge_interaction,
    check_manager,
    is_guild_manager,
    send_response,
    should_use_ephemeral,
)

MIN_STAGE_MINUTES = 2
MAX_STAGE_MINUTES = 240
DEFAULT_SESSION_DURATION = 86400
RENEWAL_NOTICE_SECONDS = 3600

# Set up logging
logger = logging.getLogger(__name__)

FOCUS_END_SHORT_BREAK_MESSAGES = [
    "🎉 Focus block conquered! Step away, stretch your limbs, and take a well-deserved {m}-minute breather.",
    "🔔 Ding ding ding! Focus sprint complete. Give your brain a break for {m} minutes!",
    "🧠 Brain recharge initiated! Step away from the screen, grab some water, and relax for {m} minutes.",
    "⚡ Incredible momentum! Hit pause, uncurl your spine, and enjoy a {m}-minute rest.",
    "🚀 Sprint done! Shake out the fidgets, look at something far away, and chill for {m} minutes.",
    "🌟 Dopamine checkpoint reached! Time to pause and bask in your accomplishment for {m} minutes.",
    "☕ Kettle time! Step away from your workspace and enjoy a nice {m}-minute pause.",
    "🧘 Deep breath in... and out. You're doing amazing! Enjoy your {m}-minute breather.",
    "🎯 Focus time checked off! No work allowed for the next {m} minutes. You've earned this!",
    "✨ Sprint complete! Stand up, stretch those shoulders, and enjoy {m} minutes of freedom.",
    "🌈 Pause button pressed! Give those eyes a rest and vibe for {m} minutes.",
    "🛋️ Step back and unwind! Your brain just worked hard, let it coast for {m} minutes.",
    "💧 Hydration alert & break time! Drink some water, stroll around, and relax for {m} minutes.",
    "🌱 Unplug for {m} minutes! Reset your mental tabs before the next round.",
    "🎮 Quick intermission! Step away, stretch, and let your mind wander for {m} minutes.",
]

FOCUS_END_LONG_BREAK_MESSAGES = [
    "🏆 4 full focus cycles completed! That is legendary stamina. Enjoy a glorious {m}-minute long break!",
    "🎉 Major milestone unlocked: 4 rounds done! Time to disconnect completely and recharge for {m} minutes.",
    "🥳 Huge win! You powered through 4 cycles! Go grab a snack, take a walk, or vibe for {m} minutes.",
    "🌟 You're unstoppable today! 4 Pomodoro cycles in the bag. Enjoy your well-earned {m}-minute retreat.",
    "🍕 Legendary focus unlocked! Four sprints conquered. Step completely away from your desk for {m} minutes.",
    "👑 Peak productivity achieved! Treat yourself to a proper {m}-minute break. Hydrate, snack, relax!",
    "🚀 Incredible endurance! You just finished a full 4-cycle loop. Rest and rejuvenate for {m} minutes.",
    "🎈 4 cycles down! That's a massive achievement. Relax your mind and recharge for {m} minutes.",
]

RESUME_GROUP_MESSAGES = [
    "Let's go team, pomodoro is back on! Jump in!",
    "The focus train is moving again! Hop on!",
    "Time to lock in! Pomodoro resumed.",
    "Let's get back to work! Pomodoro is active.",
    "Pomodoro resumed! Come join the productivity!",
    "We are back in action! Let's focus!",
    "Focus time has returned! Jump into the VC!",
    "Pomodoro is running again! Let's get those tasks done!",
    "Back to the grind! Pomodoro resumed!",
    "The break is officially over! Pomodoro is active.",
    "Let's go team, pomodoro is back on! Jump in!",
    "The focus train is moving again! Hop on!",
    "Time to lock in! Pomodoro resumed.",
    "Let's get back to work! Pomodoro is active.",
    "Pomodoro resumed! Come join the productivity!",
    "We are back in action! Let's focus!",
    "Focus time has returned! Jump into the VC!",
    "Pomodoro is running again! Let's get those tasks done!",
    "Back to the grind! Pomodoro resumed!",
    "The break is officially over! Pomodoro is active.",
    "Let's go team, pomodoro is back on! Jump in!",
    "The focus train is moving again! Hop on!",
    "Time to lock in! Pomodoro resumed.",
    "Let's get back to work! Pomodoro is active.",
    "Pomodoro resumed! Come join the productivity!",
    "We are back in action! Let's focus!",
    "Focus time has returned! Jump into the VC!",
    "Pomodoro is running again! Let's get those tasks done!",
    "Back to the grind! Pomodoro resumed!",
    "The break is officially over! Pomodoro is active.",
    "Let's go team, pomodoro is back on! Jump in!",
    "The focus train is moving again! Hop on!",
    "Time to lock in! Pomodoro resumed.",
    "Let's get back to work! Pomodoro is active.",
    "Pomodoro resumed! Come join the productivity!",
    "We are back in action! Let's focus!",
    "Focus time has returned! Jump into the VC!",
    "Pomodoro is running again! Let's get those tasks done!",
    "Back to the grind! Pomodoro resumed!",
    "The break is officially over! Pomodoro is active.",
    "Let's go team, pomodoro is back on! Jump in!",
    "The focus train is moving again! Hop on!",
    "Time to lock in! Pomodoro resumed.",
    "Let's get back to work! Pomodoro is active.",
    "Pomodoro resumed! Come join the productivity!",
    "We are back in action! Let's focus!",
    "Focus time has returned! Jump into the VC!",
    "Pomodoro is running again! Let's get those tasks done!",
    "Back to the grind! Pomodoro resumed!",
    "The break is officially over! Pomodoro is active.",
    "Let's go team, pomodoro is back on! Jump in!",
    "The focus train is moving again! Hop on!",
    "Time to lock in! Pomodoro resumed.",
    "Let's get back to work! Pomodoro is active.",
    "Pomodoro resumed! Come join the productivity!",
    "We are back in action! Let's focus!",
    "Focus time has returned! Jump into the VC!",
    "Pomodoro is running again! Let's get those tasks done!",
    "Back to the grind! Pomodoro resumed!",
    "The break is officially over! Pomodoro is active.",
    "Let's go team, pomodoro is back on! Jump in!",
    "The focus train is moving again! Hop on!",
    "Time to lock in! Pomodoro resumed.",
    "Let's get back to work! Pomodoro is active.",
    "Pomodoro resumed! Come join the productivity!",
    "We are back in action! Let's focus!",
    "Focus time has returned! Jump into the VC!",
    "Pomodoro is running again! Let's get those tasks done!",
    "Back to the grind! Pomodoro resumed!",
    "The break is officially over! Pomodoro is active.",
    "Let's go team, pomodoro is back on! Jump in!",
    "The focus train is moving again! Hop on!",
    "Time to lock in! Pomodoro resumed.",
    "Let's get back to work! Pomodoro is active.",
    "Pomodoro resumed! Come join the productivity!",
    "We are back in action! Let's focus!",
    "Focus time has returned! Jump into the VC!",
    "Pomodoro is running again! Let's get those tasks done!",
    "Back to the grind! Pomodoro resumed!",
    "The break is officially over! Pomodoro is active.",
    "Let's go team, pomodoro is back on! Jump in!",
    "The focus train is moving again! Hop on!",
    "Time to lock in! Pomodoro resumed.",
    "Let's get back to work! Pomodoro is active.",
    "Pomodoro resumed! Come join the productivity!",
    "We are back in action! Let's focus!",
    "Focus time has returned! Jump into the VC!",
    "Pomodoro is running again! Let's get those tasks done!",
    "Back to the grind! Pomodoro resumed!",
    "The break is officially over! Pomodoro is active.",
    "Let's go team, pomodoro is back on! Jump in!",
    "The focus train is moving again! Hop on!",
    "Time to lock in! Pomodoro resumed.",
    "Let's get back to work! Pomodoro is active.",
    "Pomodoro resumed! Come join the productivity!",
    "We are back in action! Let's focus!",
    "Focus time has returned! Jump into the VC!",
    "Pomodoro is running again! Let's get those tasks done!",
    "Back to the grind! Pomodoro resumed!",
    "The break is officially over! Pomodoro is active.",
]

BREAK_END_FOCUS_MESSAGES = [
    "🎯 Break's over! Let's lock in and tackle the next {m} minutes of focus together.",
    "⚡ Back in the zone! Clear those open tabs, take a deep breath, and let's conquer the next {m} minutes.",
    "🚀 Time to build momentum! Pick your next micro-task and let's dive into {m} minutes of focus.",
    "🔥 Ready to roll? Reset your focus, hydrate, and let's crush the next {m} minutes!",
    "🧠 Dopamine aligned! Pick one small step to start with and let's knock out this {m}-minute sprint.",
    "🌟 Fresh sprint starting! Jump back in and let's make progress for the next {m} minutes.",
    "🛠️ Back to the craft! Settle into your workspace and let's focus for {m} minutes.",
    "📚 Time to lock in! Set your goal for this block and let's crush {m} minutes.",
    "✨ Ready, set, focus! Put on your favorite focus tracks and let's work for {m} minutes.",
    "🦾 Powering up the focus engine! Take a deep breath and let's do this for {m} minutes.",
]


def calculate_pomodoro_ratio(
    focus: Optional[int] = None,
    short_break: Optional[int] = None,
    long_break: Optional[int] = None,
) -> Tuple[int, int, int]:
    """
    Auto-calculate Pomodoro timings using a 5:1:3 ratio (Focus : Short Break : Long Break).
    Default is 25:5:15 if none are specified.
    """
    provided = [x is not None for x in (focus, short_break, long_break)]

    if all(provided):
        return (max(2, focus), max(2, short_break), max(2, long_break))  # type: ignore

    if not any(provided):
        return (25, 5, 15)

    if focus is not None and short_break is None and long_break is None:
        f = max(2, focus)
        sb = max(2, f // 5)
        lb = max(2, f * 3 // 5)
        return (f, sb, lb)

    if short_break is not None and focus is None and long_break is None:
        sb = max(2, short_break)
        f = max(2, round(sb * 5 / 1))
        lb = max(2, round(sb * 3 / 1))
        return (f, sb, lb)

    if long_break is not None and focus is None and short_break is None:
        lb = max(2, long_break)
        f = max(2, round(lb * 5 / 3))
        sb = max(2, round(lb * 1 / 3))
        return (f, sb, lb)

    if focus is not None and short_break is not None and long_break is None:
        f = max(2, focus)
        sb = max(2, short_break)
        lb = max(2, f * 3 // 5)
        return (f, sb, lb)

    if focus is not None and long_break is not None and short_break is None:
        f = max(2, focus)
        lb = max(2, long_break)
        sb = max(2, f // 5)
        return (f, sb, lb)

    if short_break is not None and long_break is not None and focus is None:
        sb = max(2, short_break)
        lb = max(2, long_break)
        f = max(2, round(sb * 5 / 1))
        return (f, sb, lb)

    return (25, 5, 15)


class PomodoroSession:
    def __init__(
        self,
        group_id: Any,
        focus: int,
        short_break: int,
        long_break: int,
        guild_id: Optional[int] = None,
        text_id: Optional[int] = None,
        vc_id: Optional[int] = None,
        require_vc: bool = True,
        owner_id: Optional[int] = None,
        lifetime_seconds: int = DEFAULT_SESSION_DURATION,
    ):
        self.group_id = group_id
        self.guild_id = guild_id
        self.text_id = text_id
        self.vc_id = vc_id
        self.require_vc = require_vc
        self.owner_id = owner_id
        self.participants: Set[int] = {owner_id} if owner_id is not None else set()
        self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=lifetime_seconds)
        self.warned_deadline: Optional[datetime] = None
        self.renew_lock = asyncio.Lock()
        self.focus = focus
        self.short_break = short_break
        self.long_break = long_break
        self.current_stage = "focus"
        self.cycles = 0
        self.is_paused = False
        self.timer = focus * 60
        self.absent_counts: Dict[int, int] = {}
        self.dropped_out_members: Set[int] = set()
        self.current_session_marked: Set[int] = set()
        logger.info(
            f"Pomodoro session created for group {group_id} with focus: {focus}m, "
            f"short break: {short_break}m, long break: {long_break}m, require_vc={require_vc}"
        )


class PomodoroPresenceView(discord.ui.View):
    def __init__(self, cog, session):
        super().__init__(timeout=None)
        self.cog = cog
        self.session = session

    @discord.ui.button(label="Present", style=discord.ButtonStyle.green, custom_id="pomo_present")
    async def present_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.session.participants:
            await interaction.response.send_message(
                "Join this Pomodoro session before marking attendance.", ephemeral=True
            )
            return
        if interaction.user.id in self.session.dropped_out_members:
            await interaction.response.send_message(
                "You dropped out of this session. Use /resume_pomodoro to rejoin.",
                ephemeral=True,
            )
            return
        self.session.current_session_marked.add(interaction.user.id)
        self.session.absent_counts[interaction.user.id] = 0
        await interaction.response.send_message("You are marked as Present for this focus block!", ephemeral=True)

    @discord.ui.button(label="Absent", style=discord.ButtonStyle.red, custom_id="pomo_absent")
    async def absent_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.session.participants:
            await interaction.response.send_message(
                "Join this Pomodoro session before marking attendance.", ephemeral=True
            )
            return
        if interaction.user.id in self.session.dropped_out_members:
            await interaction.response.send_message("You have already dropped out.", ephemeral=True)
            return
        self.session.current_session_marked.add(interaction.user.id)
        count = self.session.absent_counts.get(interaction.user.id, 0) + 1
        self.session.absent_counts[interaction.user.id] = count
        if count > 3:
            self.session.dropped_out_members.add(interaction.user.id)
            await interaction.response.send_message(
                f"You have been marked Absent. ({count}/3 absences) You have exceeded 3 absences and dropped out of the Pomodoro session.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"You have been marked Absent. ({count}/3 absences)", ephemeral=True
            )


class PomodoroInvitationView(discord.ui.View):
    def __init__(self, cog: "Pomodoro", session: PomodoroSession, invitee_id: int):
        super().__init__(timeout=3600)
        self.cog = cog
        self.session = session
        self.invitee_id = invitee_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invitee_id:
            await interaction.response.send_message("This invitation is for someone else.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != self.invitee_id:
            await send_response(interaction, "This invitation is for someone else.", ephemeral=True)
            return
        session = self.session
        if (
            not any(existing is session for existing in self.cog.sessions.values())
            or datetime.now(timezone.utc) >= session.expires_at
        ):
            await send_response(interaction, "This Pomodoro session has ended.", ephemeral=True)
            return
        guild = self.cog.bot.get_guild(session.guild_id)
        if guild is None or guild.get_member(interaction.user.id) is None:
            await send_response(interaction, "You must still be a member of the server.", ephemeral=True)
            return
        if interaction.user.id in session.participants:
            await send_response(interaction, "You already joined this Pomodoro session.", ephemeral=True)
            return
        session.participants.add(interaction.user.id)
        member = guild.get_member(interaction.user.id)
        destination = guild.get_channel(session.vc_id) if session.vc_id else None
        if (
            session.require_vc
            and isinstance(member, discord.Member)
            and member.voice
            and isinstance(destination, discord.VoiceChannel)
        ):
            try:
                await member.move_to(destination)
            except discord.HTTPException:
                logger.warning(
                    "Could not move opted-in participant guild_id=%s group_id=%s user_id=%s",
                    session.guild_id,
                    session.group_id,
                    interaction.user.id,
                )
        await send_response(interaction, "You joined the Pomodoro session.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.grey)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.invitee_id:
            await interaction.response.send_message("This invitation is for someone else.", ephemeral=True)
            return
        await interaction.response.send_message("Invitation declined.", ephemeral=True)
        self.stop()


class PomodoroRenewView(discord.ui.View):
    def __init__(self, cog: "Pomodoro", session: PomodoroSession, deadline: datetime):
        super().__init__(timeout=3600)
        self.cog = cog
        self.session = session
        self.deadline = deadline

    @discord.ui.button(label="Renew for 24 hours", style=discord.ButtonStyle.green)
    async def renew(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        session = self.session
        async with session.renew_lock:
            if (
                not any(existing is session for existing in self.cog.sessions.values())
                or datetime.now(timezone.utc) >= session.expires_at
            ):
                await send_response(interaction, "This Pomodoro session has ended.", ephemeral=True)
                return
            if isinstance(interaction.guild_id, int) and interaction.guild_id != session.guild_id:
                await send_response(interaction, "This session belongs to another server.", ephemeral=True)
                return
            if interaction.user.id not in session.participants and not await is_guild_manager(interaction):
                await send_response(
                    interaction, "Only participants or server managers can renew this session.", ephemeral=True
                )
                return
            if session.expires_at != self.deadline:
                await send_response(interaction, "This renewal has already been used.", ephemeral=True)
                return
            session.expires_at += timedelta(hours=24)
            session.warned_deadline = None
        await send_response(interaction, "Pomodoro session renewed for 24 hours.", ephemeral=True)
        self.stop()


class Pomodoro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions: Dict[Any, PomodoroSession] = {}
        logger.info("Pomodoro cog initialized")

    def _remove_session(self, session: PomodoroSession) -> None:
        for key, existing in list(self.sessions.items()):
            if existing is session:
                self.sessions.pop(key, None)
        if not self.sessions and self.run_timer.is_running():
            self.run_timer.stop()

    async def set_paused(self, session: PomodoroSession, paused: bool) -> bool:
        """Change an active session's timer state for dashboard controls."""
        if not any(existing is session for existing in self.sessions.values()):
            return False
        if datetime.now(timezone.utc) >= session.expires_at:
            return False
        session.is_paused = paused
        await self._update_group_gui(session.group_id)
        return True

    async def finish_session(
        self, interaction: discord.Interaction, group: Dict[str, Any], session: PomodoroSession
    ) -> None:
        """End the resolved session and acknowledge a dashboard interaction."""
        await self._finish_pomodoro(interaction, group, session)

    async def _resolve_group(self, interaction: discord.Interaction) -> Optional[Dict[str, Any]]:
        """Resolve target study group for the interaction."""
        # 1. Check if user is a member of an active group
        group = await self.bot.db.get_user_group(interaction.user.id, interaction.channel_id)
        if group and group.get("guild_id", interaction.guild_id) == interaction.guild_id:
            return group

        # 2. Check if user is currently in a VC associated with an active study group
        if isinstance(interaction.user, discord.Member) and interaction.user.voice and interaction.user.voice.channel:
            vc_group = await self.bot.db.get_study_group_by_channel(interaction.user.voice.channel.id)
            if vc_group and vc_group.get("guild_id", interaction.guild_id) == interaction.guild_id:
                is_manager = await check_manager(interaction)
                members = await self.bot.db.fetch_members_of_group(vc_group.get("group_id") or str(vc_group.get("id")))
                if (
                    interaction.user.id in members
                    or interaction.user.id in (vc_group.get("creator_id"), vc_group.get("owner_id"))
                    or is_manager
                ):
                    return vc_group

        # 3. Check channel context (text channel or VC channel chat)
        if interaction.channel_id:
            channel_group = await self.bot.db.get_study_group_by_channel(interaction.channel_id)
            if channel_group and channel_group.get("guild_id", interaction.guild_id) == interaction.guild_id:
                is_manager = await check_manager(interaction)
                members = await self.bot.db.fetch_members_of_group(
                    channel_group.get("group_id") or str(channel_group.get("id"))
                )
                if (
                    interaction.user.id in members
                    or interaction.user.id in (channel_group.get("creator_id"), channel_group.get("owner_id"))
                    or is_manager
                ):
                    return channel_group

        # 4. If user is a server manager or server owner, fallback to the guild's active group
        if interaction.guild_id and await check_manager(interaction):
            guild_group = await self.bot.db.get_study_group(interaction.guild_id)
            if guild_group and guild_group.get("guild_id") == interaction.guild_id:
                return guild_group

        return None

    def _get_session(self, group: Any) -> Optional[PomodoroSession]:
        """Retrieve active Pomodoro session by group id or UUID."""
        if not group:
            return None
        gid = group.get("id") if isinstance(group, dict) else getattr(group, "id", None)
        uuid_str = group.get("group_id") if isinstance(group, dict) else getattr(group, "group_id", None)
        candidates = [
            c
            for c in [
                uuid_str,
                str(uuid_str) if uuid_str else None,
                gid,
                str(gid) if gid else None,
            ]
            if c is not None
        ]
        for key in candidates:
            if key in self.sessions:
                return self.sessions[key]
        return None

    async def _update_group_gui(self, group_id: Any):
        """Helper to trigger embed update on the study group cog if active."""
        try:
            sg_cog = self.bot.get_cog("StudyGroupCog")
            if sg_cog:
                target = sg_cog.active_study_groups.get(str(group_id))
                if not target:
                    for g in sg_cog.active_study_groups.values():
                        if str(g.group_id) == str(group_id):
                            target = g
                            break
                if target:
                    await target.group_info_embed(update=True)
        except Exception as e:
            logger.debug(f"Could not refresh study group GUI: {e}")

    @app_commands.command(
        name="start_pomodoro",
        description="Start a Pomodoro session for the study group",
    )
    @app_commands.describe(
        focus="Focus duration in minutes (auto-calculates breaks if omitted, default 25)",
        short_break="Short break duration in minutes (auto-calculates other timings if omitted)",
        long_break="Long break duration in minutes (auto-calculates other timings if omitted)",
        require_vc="Require members to join Voice Channel (default True, set False for text-only)",
    )
    async def start_pomodoro(
        self,
        interaction: discord.Interaction,
        focus: Optional[int] = None,
        short_break: Optional[int] = None,
        long_break: Optional[int] = None,
        require_vc: bool = True,
    ):
        if not interaction.response.is_done():
            await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)

        logger.info(f"Attempt to start Pomodoro session by user {interaction.user.id}")

        group = await self._resolve_group(interaction)
        if not group:
            logger.warning(f"User {interaction.user.id} tried to start Pomodoro without being in a group")
            msg = "You're not in any study group."
            if interaction.response.is_done():
                await send_response(interaction, msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        existing_session = self._get_session(group)
        if existing_session:
            logger.info(f"Pomodoro session already exists for group {group['id']}")
            msg = "A Pomodoro session is already in progress for this group."
            if interaction.response.is_done():
                await send_response(interaction, msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        if any(
            value is not None and not MIN_STAGE_MINUTES <= value <= MAX_STAGE_MINUTES
            for value in (focus, short_break, long_break)
        ):
            await send_response(
                interaction, "Focus and both breaks must each be between 2 minutes and 4 hours.", ephemeral=True
            )
            return

        # Auto-calculate timings using 5:1:3 ratio
        focus_calc, short_calc, long_calc = calculate_pomodoro_ratio(focus, short_break, long_break)
        if not all(MIN_STAGE_MINUTES <= value <= MAX_STAGE_MINUTES for value in (focus_calc, short_calc, long_calc)):
            await send_response(
                interaction, "Focus and both breaks must each be between 2 minutes and 4 hours.", ephemeral=True
            )
            return

        if not interaction.guild:
            msg = "This command can only be used in a server."
            if interaction.response.is_done():
                await send_response(interaction, msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        voice_channel: Optional[discord.VoiceChannel] = None
        if require_vc:
            voice_channel_id = group.get("vc_id")
            if not voice_channel_id:
                category_id = group.get("category_id") or await self.bot.db.get_group_category(interaction.guild.id)
                category = interaction.guild.get_channel(category_id) if category_id else None
                if not isinstance(category, discord.CategoryChannel):
                    await send_response(
                        interaction, "This group has no configured category for its voice channel.", ephemeral=True
                    )
                    return
                voice_channel = await category.create_voice_channel(
                    f"{group['name']} VC", overwrites=category.overwrites
                )
                await self.bot.db.update_voice_channel(group["id"], voice_channel.id)
                group["vc_id"] = voice_channel.id
                logger.info(f"Created new voice channel {voice_channel.id} for group {group['id']}")
            else:
                ch = interaction.guild.get_channel(voice_channel_id)
                if isinstance(ch, discord.VoiceChannel):
                    voice_channel = ch

            if not voice_channel:
                msg = "Could not locate or create a voice channel."
                if interaction.response.is_done():
                    await send_response(interaction, msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
                return

            if isinstance(interaction.user, discord.Member) and interaction.user.voice:
                try:
                    await interaction.user.move_to(voice_channel)
                    logger.info(f"Moved user {interaction.user.id} to voice channel {voice_channel.id}")
                except Exception as e:
                    logger.warning(f"Could not move user to voice channel: {e}")
            else:
                logger.warning(f"User {interaction.user.id} is not in a voice channel")
                msg = f"Please join the voice channel {voice_channel.mention} to start the Pomodoro session (or use `require_vc: False`)."
                if interaction.response.is_done():
                    await send_response(interaction, msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
                return

        duration_getter = getattr(self.bot.db, "get_default_pomodoro_duration", None)
        lifetime_seconds = await duration_getter(interaction.guild_id) if duration_getter else DEFAULT_SESSION_DURATION
        if not isinstance(lifetime_seconds, int) or lifetime_seconds <= 0:
            lifetime_seconds = DEFAULT_SESSION_DURATION
        session = PomodoroSession(
            group_id=group.get("group_id") or group["id"],
            focus=focus_calc,
            short_break=short_calc,
            long_break=long_calc,
            guild_id=interaction.guild_id,
            text_id=group.get("text_id"),
            vc_id=group.get("vc_id"),
            require_vc=require_vc,
            owner_id=interaction.user.id,
            lifetime_seconds=lifetime_seconds or DEFAULT_SESSION_DURATION,
        )

        gid = group.get("id")
        uuid_str = group.get("group_id")
        keys_to_set = [
            c
            for c in [
                uuid_str,
                str(uuid_str) if uuid_str else None,
                gid,
                str(gid) if gid else None,
            ]
            if c is not None
        ]
        for k in keys_to_set:
            self.sessions[k] = session

        if not self.run_timer.is_running():
            self.run_timer.start()

        logger.info(f"Started Pomodoro session for group {group['id']} (require_vc={require_vc})")
        mode_text = "🔊 Voice Channel Required" if require_vc else "💬 Text-Only Mode"
        response_msg = (
            f"🍅 **Pomodoro session started!**\n"
            f"• **Focus**: {focus_calc}m\n"
            f"• **Short Break**: {short_calc}m\n"
            f"• **Long Break**: {long_calc}m (every 4 cycles)\n"
            f"• **Mode**: {mode_text}"
        )
        if interaction.response.is_done():
            await send_response(interaction, response_msg, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(response_msg, ephemeral=ephemeral)

        await self.send_notification(
            interaction.guild_id,
            group.get("group_id") or group["id"],
            response_msg,
            send_ui=True,
            ping_group=False,
        )

        await self._update_group_gui(group.get("group_id") or group["id"])
        members = await self.bot.db.fetch_members_of_group(group.get("group_id") or group["id"])
        for member_id in members:
            if member_id == interaction.user.id:
                continue
            member = interaction.guild.get_member(member_id)
            if member is None:
                continue
            try:
                await member.send(
                    f"You are invited to join the Pomodoro session in **{group['name']}**. Joining is optional.",
                    view=PomodoroInvitationView(self, session, member_id),
                )
            except discord.HTTPException:
                logger.warning(
                    "Could not DM Pomodoro invitation guild_id=%s group_id=%s user_id=%s",
                    interaction.guild_id,
                    session.group_id,
                    member_id,
                )

    @app_commands.command(
        name="edit_pomodoro",
        description="Edit timings or VC settings for the active Pomodoro session",
    )
    @app_commands.describe(
        focus="New focus duration in minutes (auto-calculates breaks if others omitted)",
        short_break="New short break duration in minutes",
        long_break="New long break duration in minutes",
        require_vc="Toggle whether Voice Channel is required",
    )
    async def edit_pomodoro(
        self,
        interaction: discord.Interaction,
        focus: Optional[int] = None,
        short_break: Optional[int] = None,
        long_break: Optional[int] = None,
        require_vc: Optional[bool] = None,
    ):
        if not interaction.response.is_done():
            await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)

        group = await self._resolve_group(interaction)
        session = self._get_session(group)
        if not group or not session:
            msg = "No active Pomodoro session found for your group."
            if interaction.response.is_done():
                await send_response(interaction, msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        # Check permissions: owner, creator, or manager
        is_mgr = await check_manager(interaction)
        if interaction.user.id not in (group.get("creator_id"), group.get("owner_id")) and not is_mgr:
            msg = "Only the group owner or a server manager can edit Pomodoro settings."
            if interaction.response.is_done():
                await send_response(interaction, msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        # Handle timing changes
        if any(x is not None for x in (focus, short_break, long_break)):
            if any(
                value is not None and not MIN_STAGE_MINUTES <= value <= MAX_STAGE_MINUTES
                for value in (focus, short_break, long_break)
            ):
                await send_response(
                    interaction, "Focus and both breaks must each be between 2 minutes and 4 hours.", ephemeral=True
                )
                return
            # If only one was provided, auto-calculate with ratio
            f_calc, sb_calc, lb_calc = calculate_pomodoro_ratio(
                (
                    focus
                    if focus is not None
                    else (None if (short_break is not None or long_break is not None) else session.focus)
                ),
                short_break if short_break is not None else None,
                long_break if long_break is not None else None,
            )
            if not all(MIN_STAGE_MINUTES <= value <= MAX_STAGE_MINUTES for value in (f_calc, sb_calc, lb_calc)):
                await send_response(
                    interaction, "Focus and both breaks must each be between 2 minutes and 4 hours.", ephemeral=True
                )
                return
            session.focus = f_calc
            session.short_break = sb_calc
            session.long_break = lb_calc

            # Adjust timer cap if current stage duration shrank
            if session.current_stage == "focus" and session.timer > session.focus * 60:
                session.timer = session.focus * 60
            elif session.current_stage == "short_break" and session.timer > session.short_break * 60:
                session.timer = session.short_break * 60
            elif session.current_stage == "long_break" and session.timer > session.long_break * 60:
                session.timer = session.long_break * 60

        if require_vc is not None:
            session.require_vc = require_vc

        embed = discord.Embed(title="⚙️ Pomodoro Settings Updated", color=discord.Color.green())
        embed.add_field(name="Focus Duration", value=f"{session.focus} minutes", inline=True)
        embed.add_field(name="Short Break", value=f"{session.short_break} minutes", inline=True)
        embed.add_field(name="Long Break", value=f"{session.long_break} minutes", inline=True)
        embed.add_field(
            name="Mode",
            value=("🔊 Voice Channel Required" if session.require_vc else "💬 Text-Only Mode"),
            inline=False,
        )
        embed.add_field(
            name="Current Stage Timer",
            value=str(timedelta(seconds=max(0, session.timer))),
            inline=True,
        )

        if interaction.response.is_done():
            await send_response(interaction, embed=embed, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

        await self._update_group_gui(group.get("group_id") or group["id"])

    @app_commands.command(name="end_pomodoro", description="End the current Pomodoro session")
    async def end_pomodoro(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await acknowledge_interaction(interaction)
        logger.info(f"Attempt to end Pomodoro session by user {interaction.user.id}")
        group = await self._resolve_group(interaction)
        session = self._get_session(group)
        if not group or not session:
            logger.warning(f"No active Pomodoro session for user {interaction.user.id}")
            msg = "No active Pomodoro session for your group."
            if interaction.response.is_done():
                await send_response(interaction, msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        if interaction.user.id != session.owner_id and not await is_guild_manager(interaction):
            if interaction.user.id not in session.participants:
                await send_response(interaction, "Only participants can request to end this session.", ephemeral=True)
                return
            owner_id = session.owner_id
            if not isinstance(owner_id, int):
                await send_response(interaction, "The session owner is unavailable.", ephemeral=True)
                return
            await request_session_end(
                interaction,
                owner_id=owner_id,
                label="Pomodoro session",
                is_active=lambda: (
                    any(existing is session for existing in self.sessions.values()) and session.owner_id == owner_id
                ),
                on_confirm=lambda owner_interaction: self._finish_pomodoro(owner_interaction, group, session),
            )
            return
        await self._finish_pomodoro(interaction, group, session)

    async def _finish_pomodoro(
        self, interaction: discord.Interaction, group: Dict[str, Any], session: PomodoroSession
    ) -> None:
        if not any(existing is session for existing in self.sessions.values()):
            await send_response(interaction, "This Pomodoro session has already ended.", ephemeral=True)
            return
        self._remove_session(session)
        logger.info(f"Ended Pomodoro session for group {group['id']}")
        await send_response(interaction, "Pomodoro session ended.", ephemeral=True)

        await self._update_group_gui(group.get("group_id") or group["id"])

    @app_commands.command(name="pause_pomodoro", description="Pause the current Pomodoro session")
    async def pause_pomodoro(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)

        logger.info(f"Attempt to pause Pomodoro session by user {interaction.user.id}")
        group = await self._resolve_group(interaction)
        session = self._get_session(group)
        if not group or not session:
            logger.warning(f"No active Pomodoro session for user {interaction.user.id}")
            msg = "No active Pomodoro session for your group."
            if interaction.response.is_done():
                await send_response(interaction, msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        if session.is_paused:
            msg = "Session is already paused."
            if interaction.response.is_done():
                await send_response(interaction, msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        session.is_paused = True
        logger.info(f"Paused Pomodoro session for group {group['id']}")
        if interaction.response.is_done():
            await send_response(interaction, "Pomodoro session paused.", ephemeral=ephemeral)
        else:
            await interaction.response.send_message("Pomodoro session paused.", ephemeral=ephemeral)

        await self._update_group_gui(group.get("group_id") or group["id"])

    @app_commands.command(name="resume_pomodoro", description="Resume the paused Pomodoro session")
    async def resume_pomodoro(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)

        logger.info(f"Attempt to resume Pomodoro session by user {interaction.user.id}")
        group = await self._resolve_group(interaction)
        session = self._get_session(group)
        if not group or not session:
            logger.warning(f"No active Pomodoro session for user {interaction.user.id}")
            msg = "No active Pomodoro session for your group."
            if interaction.response.is_done():
                await send_response(interaction, msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        if not session.is_paused:
            msg = "Session is not paused."
            if interaction.response.is_done():
                await send_response(interaction, msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        session.is_paused = False
        # Remove the user who resumed from dropped_out_members
        if hasattr(session, "dropped_out_members") and interaction.user.id in session.dropped_out_members:
            session.dropped_out_members.remove(interaction.user.id)
            session.absent_counts[interaction.user.id] = 0

        logger.info(f"Resumed Pomodoro session for group {group['id']}")
        if interaction.response.is_done():
            await send_response(interaction, "Pomodoro session resumed.", ephemeral=ephemeral)
        else:
            await interaction.response.send_message("Pomodoro session resumed.", ephemeral=ephemeral)

        # Ping the group
        import random

        msg = random.choice(RESUME_GROUP_MESSAGES)
        await self.send_notification(
            session.guild_id,
            group["id"] if "id" in group else group["group_id"],
            msg,
            send_ui=False,
            ping_group=True,
        )

        await self._update_group_gui(group.get("group_id") or group["id"])

    @tasks.loop(seconds=1)
    async def run_timer(self):
        # Use set to avoid double-processing if keyed by both id and UUID
        seen_sessions = set()
        for group_id, session in list(self.sessions.items()):
            if id(session) in seen_sessions:
                continue
            seen_sessions.add(id(session))

            now = datetime.now(timezone.utc)
            if now >= session.expires_at:
                self._remove_session(session)
                await self.send_notification(session.guild_id, session.group_id, "Pomodoro session expired.")
                await self._update_group_gui(session.group_id)
                continue
            if (
                session.expires_at - now <= timedelta(seconds=RENEWAL_NOTICE_SECONDS)
                and session.warned_deadline != session.expires_at
            ):
                deadline = session.expires_at
                session.warned_deadline = deadline
                await self.send_notification(
                    session.guild_id,
                    session.group_id,
                    f"Pomodoro session ends <t:{int(deadline.timestamp())}:R>. Renew to add 24 hours.",
                    view=PomodoroRenewView(self, session, deadline),
                )

            if session.is_paused:
                continue

            if session.timer is None:
                session.timer = session.focus * 60

            session.timer -= 1

            if session.timer <= 0:
                guild_id = session.guild_id
                if session.current_stage == "focus":
                    # Process absences
                    group_members_all = session.participants
                    for m_id in group_members_all:
                        if m_id not in session.dropped_out_members and m_id not in session.current_session_marked:
                            count = session.absent_counts.get(m_id, 0) + 1
                            session.absent_counts[m_id] = count
                            if count > 3:
                                session.dropped_out_members.add(m_id)
                    session.current_session_marked.clear()

                    active = [m for m in group_members_all if m not in session.dropped_out_members]
                    if not active and group_members_all:
                        session.is_paused = True
                        msg = "All members have dropped out or are absent! Pomodoro session paused."
                        await self.send_notification(guild_id, group_id, msg, send_ui=False, ping_group=True)
                        await self._update_group_gui(session.group_id)
                        continue

                    session.cycles += 1
                    if session.cycles % 4 == 0:
                        session.current_stage = "long_break"
                        session.timer = session.long_break * 60
                        logger.info(f"Group {group_id} starting long break")
                        msg = random.choice(FOCUS_END_LONG_BREAK_MESSAGES).format(m=session.long_break)
                        msg = f"**Cycle {session.cycles} complete!**\n" + msg
                        await self.send_notification(guild_id, group_id, msg, send_ui=False)
                    else:
                        session.current_stage = "short_break"
                        session.timer = session.short_break * 60
                        logger.info(f"Group {group_id} starting short break")
                        msg = random.choice(FOCUS_END_SHORT_BREAK_MESSAGES).format(m=session.short_break)
                        msg = f"**Cycle {session.cycles} complete!**\n" + msg
                        await self.send_notification(guild_id, group_id, msg, send_ui=False)
                else:
                    session.current_stage = "focus"
                    session.timer = session.focus * 60
                    logger.info(f"Group {group_id} starting focus session")
                    msg = random.choice(BREAK_END_FOCUS_MESSAGES).format(m=session.focus)
                    msg = f"**Cycle {session.cycles + 1} starting!**\n" + msg
                    await self.send_notification(guild_id, group_id, msg, send_ui=True)

                await self._update_group_gui(session.group_id)

    async def send_notification(self, guild_id, group_id, message, send_ui=False, ping_group=False, view=None):
        """Strictly route Pomodoro notifications to the group's text or VC channel."""
        if not guild_id:
            return
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        session = self.sessions.get(group_id)
        text_id = getattr(session, "text_id", None)
        vc_id = getattr(session, "vc_id", None)
        require_vc = getattr(session, "require_vc", True)

        # Fallback to database lookup if IDs missing from session
        if not text_id or not vc_id:
            db_grp = await self.bot.db.fetch_study_group_by_id(group_id)
            if db_grp:
                text_id = text_id or db_grp.get("text_id")
                vc_id = vc_id or db_grp.get("vc_id")

        # Format ping mention
        role_mention = ""
        if session:
            active_members = [m for m in session.participants if m not in session.dropped_out_members]
            if active_members:
                role_mention = " ".join(f"<@{uid}>" for uid in active_members) + " "

        view = view or (PomodoroPresenceView(self, session) if send_ui and session else None)

        notification_sent = False

        full_msg = f"{role_mention}{message}" if role_mention else message

        # 1. Send to the group text channel so everyone in the study group sees it and can click UI buttons
        if text_id:
            text_channel = guild.get_channel(text_id)
            if text_channel and (
                isinstance(text_channel, (discord.TextChannel, discord.Thread)) or hasattr(text_channel, "send")
            ):
                try:
                    if view is not None:
                        await text_channel.send(full_msg, view=view)
                    else:
                        await text_channel.send(full_msg)
                    logger.info(f"Sent notification to group text channel {text_id} for group {group_id}")
                    notification_sent = True
                except Exception as e:
                    logger.error(f"Error sending notification to group text channel {text_id}: {e}")

        # 2. Also send to the voice channel if require_vc is enabled
        if require_vc and vc_id:
            voice_channel = guild.get_channel(vc_id)
            if voice_channel and (isinstance(voice_channel, discord.VoiceChannel) or hasattr(voice_channel, "send")):
                try:
                    vc_view = view if not notification_sent else None
                    if vc_view is not None:
                        await voice_channel.send(full_msg, view=vc_view)
                    else:
                        await voice_channel.send(full_msg)
                    logger.info(f"Sent notification to voice channel {vc_id} for group {group_id}")
                    notification_sent = True
                except Exception as e:
                    logger.warning(f"Could not send notification to VC {vc_id}: {e}")

        if not notification_sent:
            logger.warning(
                f"Could not route notification for group {group_id}: no valid group text or voice channel found."
            )

    @app_commands.command(
        name="pomodoro_status",
        description="Check the status of the current Pomodoro session",
    )
    async def pomodoro_status(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)

        logger.info(f"Pomodoro status check by user {interaction.user.id}")
        group = await self._resolve_group(interaction)
        session = self._get_session(group)

        if not group or not session:
            logger.warning(f"No active Pomodoro session for user {interaction.user.id}")
            msg = "No active Pomodoro session for your group."
            if interaction.response.is_done():
                await send_response(interaction, msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        timer_seconds = session.timer if session.timer is not None else session.focus * 60
        remaining_time = timedelta(seconds=max(0, timer_seconds))
        status = "Paused" if session.is_paused else "Running"
        stage_names = {
            "focus": "🎯 Focus",
            "short_break": "☕ Short Break",
            "long_break": "🌴 Long Break",
        }
        stage = stage_names.get(session.current_stage, session.current_stage.capitalize())

        embed = discord.Embed(title="Pomodoro Status", color=discord.Color.blue())
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Current Stage", value=stage, inline=True)
        embed.add_field(name="Time Remaining", value=str(remaining_time), inline=True)
        embed.add_field(name="Completed Cycles", value=str(session.cycles), inline=True)
        embed.add_field(
            name="Mode",
            value="🔊 Voice Required" if session.require_vc else "💬 Text-Only",
            inline=True,
        )

        logger.info(f"Sent Pomodoro status for group {group['id']}")
        if interaction.response.is_done():
            await send_response(interaction, embed=embed, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(Pomodoro(bot))
    logger.info("Pomodoro cog loaded")
