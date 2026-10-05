"""Persist identity-only audit metadata and send private moderator logs."""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


async def audit_action(
    bot: Any, guild_id: int, actor_id: int, action: str, outcome: str, target_ids: list[int | str]
) -> None:
    guild = bot.get_guild(guild_id)
    manager = bot.get_cog("Manager")
    member = guild.get_member(actor_id) if guild else None
    tier = int(await manager.get_permission_level(guild_id, actor_id, member=member)) if manager is not None else 0
    await bot.db.record_command_audit(guild_id, actor_id, tier, action, outcome, target_ids, time.time())
    group_cog = bot.get_cog("StudyGroupCog")
    if guild is not None and group_cog is not None:
        await group_cog.log_mod_action(
            guild, f"{action}: {outcome}", ",".join(map(str, target_ids)), "CPO action", actor_id
        )
