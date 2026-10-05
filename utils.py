import asyncio
import inspect
import logging
import re
import sqlite3
from typing import Any, Coroutine, List, Optional, Set, TypeVar

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

MIN_STAGE_MINUTES = 2
MAX_STAGE_MINUTES = 240
DEFAULT_SESSION_DURATION = 24 * 60 * 60
T = TypeVar("T")


def guild_operation_locks(bot: Any) -> dict[int, asyncio.Lock]:
    """Share setup recovery, configuration and allocation locks across cogs."""
    return bot.__dict__.setdefault("_guild_operation_locks", {})


async def complete_operation(operation: Coroutine[Any, Any, T]) -> T:
    """Keep a committed database change and its memory update together on cancellation."""
    task = asyncio.create_task(operation)
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            cancelled = True
            if task.done():
                break
        except Exception:
            if cancelled:
                logger.exception("Cancelled operation failed while completing its state update")
                raise asyncio.CancelledError from None
            raise
    if cancelled:
        if not task.cancelled() and (error := task.exception()) is not None:
            logger.error("Cancelled operation failed while completing its state update", exc_info=error)
        raise asyncio.CancelledError
    return result


async def should_use_ephemeral(interaction: discord.Interaction, db) -> bool:
    """Allow ordinary replies in active group channels and the commands channel."""
    guild = getattr(interaction, "guild", None)
    if guild is None:
        return True
    channel = getattr(interaction, "channel", None)
    if isinstance(channel, discord.Thread):
        return True
    channel_id = getattr(interaction, "channel_id", None)
    if not isinstance(channel_id, int):
        channel_id = getattr(channel, "id", None)
    if not isinstance(channel_id, int):
        return True
    get_group = getattr(db, "get_study_group_by_channel", None)
    if callable(get_group):
        try:
            group = await get_group(channel_id)
        except (sqlite3.Error, RuntimeError, OSError):
            logger.exception("Group visibility lookup failed guild_id=%s channel_id=%s", guild.id, channel_id)
            return True
        if isinstance(group, dict) and group.get("guild_id") == guild.id and group.get("active", 1):
            return False
    get_channel = getattr(db, "get_commands_channel", None)
    if not callable(get_channel):
        return True
    try:
        configured_channel_id = await get_channel(guild.id)
    except (sqlite3.Error, RuntimeError, OSError):
        logger.exception("Response visibility lookup failed guild_id=%s channel_id=%s", guild.id, channel_id)
        return True
    return not isinstance(configured_channel_id, int) or channel_id != configured_channel_id


async def acknowledge_interaction(interaction: discord.Interaction) -> None:
    # An immediate private response allows later public success and private errors
    # without inheriting a deferred message's visibility on the first followup.
    if hasattr(interaction, "response"):
        try:
            res = interaction.response.send_message("Processing your request…", ephemeral=True)
            if inspect.isawaitable(res):
                await res
        except discord.InteractionResponded:
            pass
    extras = getattr(interaction, "extras", None)
    if isinstance(extras, dict):
        extras["cpo_acknowledged"] = True


async def send_response(interaction: discord.Interaction, *args, ephemeral: bool = True, **kwargs):
    res = interaction.followup.send(*args, ephemeral=ephemeral, **kwargs)
    message = await res if inspect.isawaitable(res) else res
    extras = getattr(interaction, "extras", None)
    if isinstance(extras, dict) and extras.pop("cpo_acknowledged", False):
        try:
            del_res = interaction.delete_original_response()
            if inspect.isawaitable(del_res):
                await del_res
        except discord.HTTPException:
            logger.exception(
                "Could not remove command acknowledgement guild_id=%s user_id=%s",
                interaction.guild_id,
                interaction.user.id,
            )
    return message


### Parsing Time Functions


def parse_seconds_to_hms(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds_left = divmod(remainder, 60)
    parts: List[str] = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if seconds_left > 0 or len(parts) == 0:  # Always show seconds if it's the only component
        parts.append(f"{seconds_left} second{'s' if seconds_left > 1 or seconds_left == 0 else ''}")
    result = " ".join(parts)
    logger.debug(f"Parsed {seconds} seconds to {result}")
    return result


def parse_duration(duration_str: str) -> Optional[int]:
    pattern = r"\s*(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d)\s*"
    position = 0
    total = 0
    while position < len(duration_str):
        match = re.match(pattern, duration_str[position:], re.IGNORECASE)
        if match is None:
            return None
        value, unit = match.groups()
        total += int(value) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit[0].lower()]
        position += match.end()
    return total if position else None


### Mentions Function
def parse_mentions(interaction: discord.Interaction, mentions: str) -> List[int]:
    logger.info(f"Parsing mentions: {mentions}")
    logger.info(f"Interaction User: {interaction.user} and Interaction Guild: {interaction.guild}")
    if not interaction.guild:
        return [interaction.user.id]

    member_ids: set[int] = set()

    # Extract all role mentions <@&ROLE_ID>
    role_ids = re.findall(r"<@&(\d+)>", mentions)
    for r_id_str in role_ids:
        role_id = int(r_id_str)
        role = interaction.guild.get_role(role_id)
        if role:
            for member in role.members:
                member_ids.add(member.id)

    # Extract all user mentions <@USER_ID> or <@!USER_ID>
    user_ids = re.findall(r"<@!?(\d+)>", mentions)
    for u_id_str in user_ids:
        member_ids.add(int(u_id_str))

    # Also extract any standalone numeric IDs
    for word in mentions.split():
        clean_word = word.strip(",;()[]")
        if clean_word.isdigit() and len(clean_word) >= 17:
            member_ids.add(int(clean_word))

    # Always include interaction author
    if interaction.user:
        member_ids.add(interaction.user.id)

    result = list(member_ids)
    logger.info(f"Parsed mention user IDs: {result}")
    return result


### Validation Functions
async def validate_parameters(
    interaction: discord.Interaction,
    name: Optional[str] = None,
    member_ids: Optional[List[int]] = None,
    category: Optional[discord.CategoryChannel] = None,
    duration: Optional[str] = None,
    min_duration: Optional[int] = None,
    max_members: Optional[int] = None,
) -> Optional[bool]:
    """
    A unified parameter validation function for all modules (Checkin, Study Group).
    Parameters are optional, and validation will only be performed for those passed.
    Parameters:
    - name: Name - Study Group
    - member_ids: List of Member IDs - Checkin, Study Group
    - category: Category of Study Group
    Minimums and Maximum Values:
    - min_duration: The minimum duration of Checkin reminder
    - max_members: The maximum number of members - Checkin, Study Group
    """
    try:
        # 1. Validate the group name if provided
        if name is not None:
            if not name or len(name) > 100:
                await send_response(
                    interaction,
                    "Invalid group name. The name must be non-empty and less than 100 characters.",
                    ephemeral=True,
                )
                logger.warning(f"Invalid group name provided: {name} by user {interaction.user}")
                return False

        # 2. Check if the max_members given is a positive number
        if max_members is not None and max_members < 0:
            await send_response(interaction, "The maximum number of members must be non-negative.", ephemeral=True)
            logger.warning(f"Invalid max_members provided: {max_members} by user {interaction.user}")
            return False

        # 3. Validate member_ids if provided (fetching Members by IDs)
        if member_ids is not None:
            guild = interaction.guild
            if not guild:
                return False
            members = []
            for member_id in member_ids:
                member = guild.get_member(member_id)
                if member is None:
                    try:
                        member = await guild.fetch_member(member_id)
                    except (discord.NotFound, discord.HTTPException):
                        member = None
                members.append(member)

            if not all(members):
                await send_response(
                    interaction,
                    "One or more members couldn't be found. Please mention valid users.",
                    ephemeral=True,
                )
                logger.warning(
                    f"Some members in the mentions couldn't be found. User {interaction.user} provided mentions: {member_ids}"
                )
                return False

            if max_members is not None and len(members) > max_members:
                await send_response(
                    interaction,
                    f"Too many members specified. Max allowed: {max_members}.",
                    ephemeral=True,
                )
                logger.warning(
                    f"Too many members ({len(members)}) compared to max_members: {max_members}. User {interaction.user}"
                )
                return False

        # 4. Validate category if provided
        if category is not None:
            if not interaction.guild or category.id not in [c.id for c in interaction.guild.categories]:
                await send_response(
                    interaction,
                    "No valid category specified. Please provide a valid category.",
                    ephemeral=True,
                )
                logger.warning(f"Invalid category provided: {category}. User {interaction.user}")
                return False

        # 5. Validate duration if provided (for check-in)
        if duration is not None:
            duration_seconds = parse_duration(duration)
            if duration_seconds is None:
                await send_response(
                    interaction,
                    "Wrong duration format used. Please provide a valid duration like '2d 14h 25m 30s'.",
                    ephemeral=True,
                )
                logger.warning(f"Wrong duration format entered by user {interaction.user}: {duration}")
                return False
            if min_duration is not None and duration_seconds < min_duration:
                await send_response(
                    interaction,
                    f"Duration must be at least {parse_seconds_to_hms(min_duration)}.",
                    ephemeral=True,
                )
                logger.warning(
                    f"Attempted to start a session with insufficient duration by user {interaction.user}. Entered duration: {duration_seconds} (minimum: {min_duration} seconds)."
                )
                return False

        return True

    except discord.Forbidden as forbidden_e:
        logger.error(f"Permission error during validation by user {interaction.user}: {forbidden_e}")
        await send_response(
            interaction,
            f"Permission error occurred during validation: {forbidden_e}",
            ephemeral=True,
        )
        return False

    except discord.HTTPException as http_e:
        logger.error(f"HTTP error during validation by user {interaction.user}: {http_e}")
        await send_response(interaction, f"HTTP error occurred during validation: {http_e}", ephemeral=True)
        return False

    except Exception as e:
        logger.critical(f"Unexpected error during validation by user {interaction.user}: {e}")
        await send_response(interaction, f"An unexpected error occurred during validation: {e}", ephemeral=True)
        return False


### Membership and Manager Functions


async def has_guild_permissions(user, guild, bot) -> bool:
    """Recognize server authority from permissions or explicit stored grants."""
    if guild is None:
        return False
    user_id = getattr(user, "id", None)
    if not isinstance(user_id, int):
        return False
    member_guild = getattr(user, "guild", None)
    if member_guild is not None and member_guild.id != guild.id:
        return False
    if user_id == getattr(bot, "bot_developer_id", None) or user_id == guild.owner_id:
        return True
    perms = getattr(user, "guild_permissions", None)
    permission_names = (
        "administrator",
        "manage_guild",
        "manage_channels",
        "manage_roles",
        "moderate_members",
        "kick_members",
        "ban_members",
    )
    if perms and any(getattr(perms, name, False) is True for name in permission_names):
        return True
    db = getattr(bot, "db", None)
    get_manager = getattr(db, "get_manager", None)
    if not callable(get_manager):
        return False
    try:
        manager = await get_manager(user_id, guild.id)
    except (sqlite3.Error, RuntimeError, OSError):
        logger.exception("Manager lookup failed guild_id=%s user_id=%s", guild.id, user_id)
        return False
    if isinstance(manager, (dict, sqlite3.Row)):
        if dict(manager).get("grant_source") == "server_sync":
            return False
        level = manager["permission_level"]
        grant_guild_id = manager["guild_id"]
        return isinstance(level, int) and 3 <= level <= 4 and grant_guild_id == guild.id
    return False


async def is_guild_manager(interaction: discord.Interaction) -> bool:
    return await has_guild_permissions(interaction.user, interaction.guild, interaction.client)


async def check_manager(ctx_or_interaction):
    if isinstance(ctx_or_interaction, discord.Interaction):
        bot = ctx_or_interaction.client
        guild = ctx_or_interaction.guild
        user = ctx_or_interaction.user
    elif isinstance(ctx_or_interaction, commands.Context):
        bot = ctx_or_interaction.bot
        guild = ctx_or_interaction.guild
        user = ctx_or_interaction.author
    else:
        logger.error(f"Unexpected context type in check_manager: {type(ctx_or_interaction)}")
        return False

    if not guild:
        logger.error("Guild is None in check_manager")
        return False

    return await has_guild_permissions(user, guild, bot)


def is_manager():
    async def predicate(ctx):
        return await check_manager(ctx)

    return commands.check(predicate)


def app_is_manager():
    async def predicate(interaction):
        return await check_manager(interaction)

    return app_commands.check(predicate)


def is_group_creator():
    async def predicate(interaction):
        logger.debug(f"Checking if user is group creator or manager: {interaction.user}")
        if getattr(interaction.client, "bot_developer_id", None) == interaction.user.id:
            return True
        if await check_manager(interaction):
            return True
        group = await get_context_group(interaction, interaction.client.db)
        if not group:
            return False
        creator_id = group["creator_id"] if "creator_id" in group.keys() else group[4]
        owner_id = group["owner_id"] if "owner_id" in group.keys() else group[5]
        is_creator_or_owner = bool(interaction.user.id in (creator_id, owner_id))
        logger.info(
            f"User {interaction.user.name} is {'authorized' if is_creator_or_owner else 'not authorized'} as group creator/owner"
        )
        return is_creator_or_owner

    return app_commands.check(predicate)


async def get_context_group(interaction: discord.Interaction, db) -> Optional[dict]:
    guild = interaction.guild
    if guild is None:
        return None
    group = await db.get_study_group_by_channel(interaction.channel_id)
    if not isinstance(group, dict):
        group = await db.get_user_group(interaction.user.id, interaction.channel_id)
    if not isinstance(group, dict) or group.get("guild_id") != guild.id or not group.get("active", 1):
        return None
    return group


class ProductivityService:
    def __init__(self, db_handler):
        self.db = db_handler

    async def get_productivity_metrics(self, user_id, guild_id=None):
        tasks_completed = await self.get_tasks_completed(user_id)
        focus_seconds = await self.db.get_productivity_focus_seconds(user_id, guild_id)
        focus_hours = max(0.0, float(focus_seconds)) / 3600
        efficiency_score = self.calculate_efficiency(tasks_completed, focus_hours)

        return {
            "tasks_completed": tasks_completed,
            "time_spent": round(focus_hours, 4),
            "efficiency_score": efficiency_score,
        }

    async def get_tasks_completed(self, user_id):
        tasks = await self.db.get_user_tasks(user_id)
        completed_tasks = [task for task in tasks if task["completed"]]
        return len(completed_tasks)

    def calculate_efficiency(self, tasks, time):
        if time <= 0:
            return 0.0
        return round(tasks / time, 2)


KNOWN_BOT_DEV_PLACEHOLDERS: Set[str] = {
    "your_discord_user_id_here",
    "your_user_id_here",
    "your_id_here",
    "discord_user_id_here",
    "bot_developer_id_here",
    "your_bot_developer_id",
    "123456789012345678",
    "1234567890123456789",
    "placeholder",
    "changeme",
    "none",
    "null",
    "undefined",
    "todo",
}

DISCORD_SNOWFLAKE_MIN_DIGITS = 17
DISCORD_SNOWFLAKE_MAX_DIGITS = 20
DISCORD_SNOWFLAKE_MAX = (1 << 64) - 1


def validate_bot_developer_id(
    raw_id: Any,
    *,
    strict: bool = False,
    allow_mock: bool = False,
) -> Optional[int]:
    """
    Validate BOT_DEVELOPER_ID and reject placeholder or invalid values.

    Returns the validated integer ID, or None if missing or invalid (when strict=False).
    Raises ValueError when strict=True if the value is invalid or a placeholder.
    """
    if raw_id is None:
        if strict:
            raise ValueError("BOT_DEVELOPER_ID is not configured")
        return None

    if isinstance(raw_id, bool):
        msg = f"BOT_DEVELOPER_ID cannot be a boolean: {raw_id!r}"
        if strict:
            raise ValueError(msg)
        logger.warning(msg)
        return None

    if isinstance(raw_id, float):
        msg = f"BOT_DEVELOPER_ID cannot be a float: {raw_id!r}"
        if strict:
            raise ValueError(msg)
        logger.warning(msg)
        return None

    if isinstance(raw_id, int):
        if raw_id <= 0:
            msg = f"BOT_DEVELOPER_ID must be a positive integer, got: {raw_id}"
            if strict:
                raise ValueError(msg)
            logger.warning(msg)
            return None
        cleaned_str = str(raw_id)
    elif isinstance(raw_id, str):
        cleaned_str = raw_id.strip().strip("\"'")
        if cleaned_str.startswith("-"):
            msg = f"BOT_DEVELOPER_ID must be a positive integer, got: {raw_id!r}"
            if strict:
                raise ValueError(msg)
            logger.warning(msg)
            return None
    else:
        msg = f"BOT_DEVELOPER_ID has unsupported type: {type(raw_id).__name__}"
        if strict:
            raise ValueError(msg)
        logger.warning(msg)
        return None

    if not cleaned_str:
        if strict:
            raise ValueError("BOT_DEVELOPER_ID cannot be empty")
        return None

    if cleaned_str.lower() in KNOWN_BOT_DEV_PLACEHOLDERS:
        msg = f"BOT_DEVELOPER_ID is set to a placeholder value: {raw_id!r}"
        if strict:
            raise ValueError(msg)
        logger.warning(msg)
        return None

    if not cleaned_str.isdigit():
        msg = f"BOT_DEVELOPER_ID must contain only digits, got: {raw_id!r}"
        if strict:
            raise ValueError(msg)
        logger.warning(msg)
        return None

    if len(cleaned_str) >= 10 and len(set(cleaned_str)) == 1:
        msg = f"BOT_DEVELOPER_ID is a repetitive placeholder value: {raw_id!r}"
        if strict:
            raise ValueError(msg)
        logger.warning(msg)
        return None

    val = int(cleaned_str)
    if val <= 0:
        msg = f"BOT_DEVELOPER_ID must be a positive integer, got: {val}"
        if strict:
            raise ValueError(msg)
        logger.warning(msg)
        return None

    if val > DISCORD_SNOWFLAKE_MAX:
        msg = f"BOT_DEVELOPER_ID exceeds maximum 64-bit integer limit: {val}"
        if strict:
            raise ValueError(msg)
        logger.warning(msg)
        return None

    if not allow_mock and (
        len(cleaned_str) < DISCORD_SNOWFLAKE_MIN_DIGITS or len(cleaned_str) > DISCORD_SNOWFLAKE_MAX_DIGITS
    ):
        msg = f"BOT_DEVELOPER_ID must be a valid 17-20 digit Discord snowflake, got {len(cleaned_str)} digits: {val}"
        if strict:
            raise ValueError(msg)
        logger.warning(msg)
        return None

    return val
