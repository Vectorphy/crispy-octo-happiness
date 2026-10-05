"""Persist identity-only audit metadata and send private moderator logs."""

import inspect
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


async def audit_action(
    bot: Any, guild_id: int, actor_id: int, action: str, outcome: str, target_ids: list[int | str]
) -> None:
    guild = bot.get_guild(guild_id) if hasattr(bot, "get_guild") else None
    manager = bot.get_cog("Manager") if hasattr(bot, "get_cog") else None
    member = guild.get_member(actor_id) if guild and hasattr(guild, "get_member") else None
    tier = 0
    if manager is not None and hasattr(manager, "get_permission_level"):
        try:
            res = manager.get_permission_level(guild_id, actor_id, member=member)
            res = await res if inspect.isawaitable(res) else res
            tier = int(res) if isinstance(res, (int, float)) else 0
        except Exception:
            tier = 0
    if hasattr(bot, "db") and hasattr(bot.db, "record_command_audit"):
        try:
            res = bot.db.record_command_audit(guild_id, actor_id, tier, action, outcome, target_ids, time.time())
            if inspect.isawaitable(res):
                await res
        except Exception:
            logger.exception("Failed to record command audit in db")
    group_cog = bot.get_cog("StudyGroupCog") if hasattr(bot, "get_cog") else None
    if guild is not None and group_cog is not None and hasattr(group_cog, "log_mod_action"):
        try:
            res = group_cog.log_mod_action(
                guild, f"{action}: {outcome}", ",".join(map(str, target_ids)), "CPO action", actor_id
            )
            if inspect.isawaitable(res):
                await res
        except Exception:
            logger.exception("Failed to log mod action in group cog")
