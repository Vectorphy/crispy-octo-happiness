"""Durable recipient invitations with absolute warning and acceptance deadlines."""

import asyncio
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from types import SimpleNamespace

import discord

from cogs._audit import audit_action
from utils import acknowledge_interaction, send_response

logger = logging.getLogger(__name__)
EXPIRY_NOTICE = "This invitation expired. Ask the session owner to send you a new invitation."


async def eligible_recipient(bot: Any, guild_id: int, user_id: int) -> discord.Member | None:
    guild = bot.get_guild(guild_id)
    if guild is None or guild.id != guild_id:
        return None
    role_id = await bot.db.get_default_role(guild_id)
    try:
        member = await guild.fetch_member(user_id)
    except discord.NotFound:
        return None
    if not isinstance(member, discord.Member) or member.id != user_id or member.guild.id != guild_id or member.bot:
        return None
    if role_id is not None and (
        type(role_id) is not int
        or guild.get_role(role_id) is None
        or not any(role.id == role_id for role in member.roles)
    ):
        return None
    return member


def service_for(bot: Any) -> "InvitationService":
    service = getattr(bot, "_invitation_service", None)
    if not isinstance(service, InvitationService):
        service = InvitationService(bot)
        bot._invitation_service = service
    return service


def initialize_invitation(view: Any, bot: Any, kind: str, session: Any, recipient_id: int) -> None:
    view.timeout = None
    view.invitation_id = str(uuid.uuid4())
    view.invitation_kind = kind
    view.invitation_bot = bot
    view.invitation_session = session
    view.invitation_recipient = recipient_id
    view.invitation_created_at = time.time()
    view.invitation_row = None
    view.guild_id = session.guild_id
    for item in view.children:
        if not isinstance(item, discord.ui.Button):
            continue
        action = "join" if item.label == "Join" else "decline"
        item.custom_id = f"cpo:invitation:{view.invitation_id}:{action}"
        original = item.callback

        async def callback(interaction, original=original, action=action):
            await service_for(bot).act(view, interaction, action, original)

        item.callback = callback  # type: ignore[method-assign]


class InvitationService:
    def __init__(self, bot: Any):
        self.bot = bot
        self.views: dict[str, Any] = {}
        self.tasks: dict[str, asyncio.Task[Any]] = {}
        self.actions: set[asyncio.Task[Any]] = set()
        self.locks: dict[str, asyncio.Lock] = {}
        self.recovery_lock = asyncio.Lock()
        self.closed_kinds: set[str] = set()

    def session_identity(self, view: Any) -> str:
        session = view.invitation_session
        return str(
            session.group_id
            if view.invitation_kind == "group"
            else session.session_id
            if view.invitation_kind == "checkin"
            else session.tracking_id
        )

    async def live(self, view: Any, row: dict[str, Any]) -> bool:
        session = view.invitation_session
        if (
            session.guild_id != row["guild_id"]
            or self.session_identity(view) != row["session_id"]
            or session.owner_id != row["owner_id"]
        ):
            return False
        if view.invitation_kind == "group":
            record = await self.bot.db.fetch_study_group_by_id(session.group_id)
            return bool(
                isinstance(record, dict)
                and record.get("active")
                and record.get("guild_id") == row["guild_id"]
                and record.get("owner_id") == row["owner_id"]
                and session.active
                and not session.ending
            )
        if view.invitation_kind == "checkin":
            record = await self.bot.db.fetch_checkin_session(session.session_id)
            return bool(
                isinstance(record, dict)
                and record.get("active")
                and record.get("guild_id") == row["guild_id"]
                and record.get("owner_id") == row["owner_id"]
                and not session.end_session_event.is_set()
                and session.cog.active_sessions.get(session.session_id) is session
            )
        record = await self.bot.db.fetch_study_group_by_id(session.group_id)
        return bool(
            isinstance(record, dict)
            and record.get("active")
            and record.get("guild_id") == row["guild_id"]
            any(value is session for value in view.cog.sessions.values())
            and datetime.now(timezone.utc) < session.expires_at
        )

    async def joined(self, view: Any) -> bool:
        session = view.invitation_session
        recipient = view.invitation_recipient
        if view.invitation_kind == "group":
            return recipient in await self.bot.db.fetch_members_of_group(session.group_id)
        if view.invitation_kind == "checkin":
            return any(
                record["member_id"] == recipient and record["status"] != "exited"
                for record in await self.bot.db.fetch_checkin_members(session.session_id)
            )
        records = await self.bot.db.get_active_pomodoro_runtime()
        return any(
            record["guild_id"] == session.guild_id
            and record["state"].get("tracking_id") == session.tracking_id
            and recipient in record["state"].get("participants", [])
            for record in records
        )

    async def send(
        self, view: Any, *, actor_id: int, content: str | None = None, embed: discord.Embed | None = None
    ) -> None:
        kind = view.invitation_kind
        if kind in self.closed_kinds:
            raise RuntimeError("Invitation service is unloading")
        recipient = await eligible_recipient(self.bot, view.guild_id, view.invitation_recipient)
        if recipient is None:
            await audit_action(
                self.bot,
                view.guild_id,
                actor_id,
                "invitation.send",
                "denied",
                [self.session_identity(view), view.invitation_recipient],
            )
            raise ValueError("The invitee must be a current server member with the configured CPO access role")
        session = view.invitation_session
        row = await self.bot.db.create_session_invitation(
            view.invitation_id,
            view.guild_id,
            kind,
            self.session_identity(view),
            recipient.id,
            session.owner_id,
            view.invitation_created_at,
        )
        view.invitation_row = row
        if not await self.live(view, row):
            await self.bot.db.transition_session_invitation(
                view.guild_id, view.invitation_id, "pending", "invalid", now=time.time()
            )
            raise ValueError("The invitation owner or session is no longer current")
        await audit_action(
            self.bot, view.guild_id, actor_id, "invitation.send", "invoked", [row["session_id"], recipient.id]
        )
        try:
            options: dict[str, Any] = {"view": view, "allowed_mentions": discord.AllowedMentions.none()}
            if embed is not None:
                options["embed"] = embed
            if content is not None:
                options["content"] = content
            message = await recipient.send(**options)
            if not await self.bot.db.bind_session_invitation_message(
                view.guild_id, view.invitation_id, message.channel.id, message.id
            ):
                raise RuntimeError("Invitation message could not be recorded")
            row["dm_channel_id"], row["dm_message_id"] = message.channel.id, message.id
            self.register(view)
            await audit_action(
                self.bot, view.guild_id, actor_id, "invitation.send", "succeeded", [row["session_id"], recipient.id]
            )
        except (discord.HTTPException, sqlite3.Error, RuntimeError, OSError):
            view.stop()
            await self.bot.db.transition_session_invitation(
                view.guild_id, view.invitation_id, "pending", "invalid", now=time.time()
            )
            await audit_action(
                self.bot, view.guild_id, actor_id, "invitation.send", "failed", [row["session_id"], recipient.id]
            )
            raise

    def register(self, view: Any) -> None:
        if view.invitation_id in self.views:
            return
        self.views[view.invitation_id] = view
        self.bot.add_view(view, message_id=view.invitation_row["dm_message_id"])
        self.tasks[view.invitation_id] = asyncio.create_task(self.monitor(view))

    async def act(self, view: Any, interaction: discord.Interaction, action: str, callback: Any) -> None:
        await acknowledge_interaction(interaction)
        task = asyncio.current_task()
        if task is not None:
            self.actions.add(task)
        try:
            async with self.locks.setdefault(view.invitation_id, asyncio.Lock()):
                row = await self.bot.db.get_session_invitation(view.guild_id, view.invitation_id)
                if (
                    not isinstance(row, dict)
                    or row["recipient_id"] != interaction.user.id
                    or row["guild_id"] != view.guild_id
                    or (interaction.guild_id is not None and interaction.guild_id != view.guild_id)
                ):
                    await send_response(interaction, "This invitation is for another member or server.", ephemeral=True)
                    await audit_action(
                        self.bot,
                        view.guild_id,
                        interaction.user.id,
                        "invitation." + action,
                        "denied",
                        [view.invitation_id],
                    )
                    return
                if row["status"] == "accepting":
                    await self.reconcile(view, row)
                    row = await self.bot.db.get_session_invitation(view.guild_id, view.invitation_id)
                if row["status"] != "pending" or time.time() >= row["expires_at"]:
                    await self.tick(view)
                    await send_response(
                        interaction,
                        EXPIRY_NOTICE
                        if row["status"] == "expired" or time.time() >= row["expires_at"]
                        else "This invitation is no longer pending.",
                        ephemeral=True,
                    )
                    return
                if (
                    view.invitation_kind in self.closed_kinds
                    or not await self.live(view, row)
                    or await eligible_recipient(self.bot, view.guild_id, interaction.user.id) is None
                ):
                    await self.bot.db.transition_session_invitation(
                        view.guild_id, view.invitation_id, "pending", "invalid", now=time.time()
                    )
                    await send_response(
                        interaction,
                        "The session ended, its owner changed, or your server membership/access role changed. Ask the owner for a new invitation.",
                        ephemeral=True,
                    )
                    await audit_action(
                        self.bot,
                        view.guild_id,
                        interaction.user.id,
                        "invitation." + action,
                        "denied",
                        [row["session_id"]],
                    )
                    self.finish(view)
                    return
                desired = "accepting" if action == "join" else "declined"
                if not await self.bot.db.transition_session_invitation(
                    view.guild_id, view.invitation_id, "pending", desired, now=time.time()
                ):
                    await send_response(interaction, EXPIRY_NOTICE, ephemeral=True)
                    return
                if action == "decline":
                    await audit_action(
                        self.bot,
                        view.guild_id,
                        interaction.user.id,
                        "invitation.decline",
                        "declined",
                        [row["session_id"]],
                    )
                    await send_response(interaction, "Invitation declined.", ephemeral=True)
                    self.finish(view)
                    return
                await callback(interaction)
                if await self.joined(view):
                    await self.bot.db.transition_session_invitation(
                        view.guild_id, view.invitation_id, "accepting", "accepted", now=time.time()
                    )
                    await audit_action(
                        self.bot,
                        view.guild_id,
                        interaction.user.id,
                        "invitation.join",
                        "succeeded",
                        [row["session_id"]],
                    )
                    self.finish(view)
                else:
                    await self.bot.db.transition_session_invitation(
                        view.guild_id, view.invitation_id, "accepting", "pending", now=time.time()
                    )
                    await audit_action(
                        self.bot, view.guild_id, interaction.user.id, "invitation.join", "failed", [row["session_id"]]
                    )
        except (discord.HTTPException, sqlite3.Error, RuntimeError, OSError, ValueError):
            logger.exception(
                "Invitation action retained for retry guild_id=%s invitation_id=%s", view.guild_id, view.invitation_id
            )
            await send_response(
                interaction, "This invitation could not complete. Retry while it is still valid.", ephemeral=True
            )
        finally:
            if task is not None:
                self.actions.discard(task)

    async def reconcile(self, view: Any, row: dict[str, Any]) -> None:
        if await self.joined(view):
            status = "accepted"
        elif not await self.live(view, row):
            status = "invalid"
        elif time.time() >= row["expires_at"]:
            status = "expired"
        else:
            status = "pending"
        await self.bot.db.transition_session_invitation(
            view.guild_id, view.invitation_id, "accepting", status, now=time.time()
        )

    async def notification(self, view: Any, row: dict[str, Any], *, expired: bool) -> None:
        recipient = await self.bot.fetch_user(row["recipient_id"])
        await recipient.send(
            EXPIRY_NOTICE
            if expired
            else "Your invitation is still pending and expires in 4 minutes. Ask the owner for a new invitation after it expires.",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        if row["dm_channel_id"] and row["dm_message_id"]:
            channel = await self.bot.fetch_channel(row["dm_channel_id"])
            message = await channel.fetch_message(row["dm_message_id"])
            if expired:
                for child in view.children:
                    child.disabled = True
                await message.edit(view=view)
        await self.bot.db.mark_invitation_notification(view.guild_id, view.invitation_id, expired=expired)

    async def tick(self, view: Any) -> bool:
        row = await self.bot.db.get_session_invitation(view.guild_id, view.invitation_id)
        if row is None:
            self.finish(view)
            return False
        if row["status"] == "accepting":
            await self.reconcile(view, row)
            row = await self.bot.db.get_session_invitation(view.guild_id, view.invitation_id)
        if row["status"] == "pending" and time.time() >= row["expires_at"]:
            await self.bot.db.transition_session_invitation(
                view.guild_id, view.invitation_id, "pending", "expired", now=time.time()
            )
            row = await self.bot.db.get_session_invitation(view.guild_id, view.invitation_id)
        if row["status"] == "expired":
            if not row["expiry_notified"]:
                await self.notification(view, row, expired=True)
                await audit_action(
                    self.bot, view.guild_id, row["recipient_id"], "invitation.expire", "expired", [row["session_id"]]
                )
            self.finish(view)
            return False
        if row["status"] != "pending":
            self.finish(view)
            return False
        if time.time() >= row["warn_at"] and not row["warned"]:
            await self.notification(view, row, expired=False)
        return True

    async def monitor(self, view: Any) -> None:
        try:
            while view.invitation_id in self.views:
                try:
                    async with self.locks.setdefault(view.invitation_id, asyncio.Lock()):
                        if not await self.tick(view):
                            return
                except (discord.HTTPException, sqlite3.Error, RuntimeError, OSError, ValueError):
                    logger.exception(
                        "Invitation monitor will retry guild_id=%s invitation_id=%s", view.guild_id, view.invitation_id
                    )
                await asyncio.sleep(1)
        finally:
            if self.tasks.get(view.invitation_id) is asyncio.current_task():
                self.tasks.pop(view.invitation_id, None)

    def finish(self, view: Any) -> None:
        view.stop()
        self.views.pop(view.invitation_id, None)
        task = self.tasks.get(view.invitation_id)
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    async def close_kind(self, kind: str) -> None:
        self.closed_kinds.add(kind)
        tasks = [
            task
            for identifier, task in self.tasks.items()
            if self.views.get(identifier) is not None and self.views[identifier].invitation_kind == kind
        ]
        for view in list(self.views.values()):
            if view.invitation_kind == kind:
                self.finish(view)
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(
            *(task for task in self.actions if task is not asyncio.current_task()), return_exceptions=True
        )
