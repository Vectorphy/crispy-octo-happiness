from typing import Any
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from bot import on_app_command_error
from cogs.checkin import CheckinCog, CheckinGuildSettings, CheckinSession
from cogs.pomodoro import Pomodoro
from cogs.productivity_tracker import ProductivityTracker
from cogs.tasklist import TaskList
from cogs.voice_channels import VoiceChannels
from utils import acknowledge_interaction, send_response, should_use_ephemeral


class InteractionHarness:
    def __init__(self, channel_id: int = 20, guild_id: int | None = 1):
        self.interaction = MagicMock(spec=discord.Interaction)
        self.interaction.guild_id = guild_id
        self.interaction.channel_id = channel_id
        self.interaction.guild = MagicMock(spec=discord.Guild) if guild_id is not None else None
        if self.interaction.guild is not None:
            self.interaction.guild.id = guild_id
        self.interaction.channel = MagicMock(spec=discord.TextChannel)
        self.interaction.channel.id = channel_id
        self.interaction.user = MagicMock(spec=discord.Member)
        self.interaction.user.id = 5
        self.interaction.user.display_name = "Tester"
        self.interaction.user.mention = "<@5>"
        self.interaction.extras = {}
        self.messages: list[dict[str, Any]] = []
        self.responded = False
        self.deferred = False
        self.original_ephemeral = False
        self.followup_count = 0
        self.delete_error: Exception | None = None

        response = MagicMock()
        response.is_done.side_effect = lambda: self.responded
        response.send_message = AsyncMock(side_effect=self._send_initial)
        response.defer = AsyncMock(side_effect=self._defer)
        self.interaction.response = response

        followup = MagicMock()
        followup.send = AsyncMock(side_effect=self._send_followup)
        self.interaction.followup = followup
        self.interaction.delete_original_response = AsyncMock(side_effect=self._delete_original)

    async def _send_initial(self, *args: Any, **kwargs: Any) -> None:
        if self.responded:
            raise discord.InteractionResponded(self.interaction)
        self.responded = True
        self.original_ephemeral = kwargs.get("ephemeral", False)
        self.messages.append({"args": args, "kwargs": kwargs, "ephemeral": self.original_ephemeral, "deleted": False})

    async def _defer(self, *args: Any, **kwargs: Any) -> None:
        if self.responded:
            raise discord.InteractionResponded(self.interaction)
        self.responded = True
        self.deferred = True
        self.original_ephemeral = kwargs.get("ephemeral", False)

    async def _send_followup(self, *args: Any, **kwargs: Any) -> MagicMock:
        if not self.responded:
            raise RuntimeError("Interaction has not been acknowledged")
        effective_ephemeral = (
            self.original_ephemeral if self.deferred and self.followup_count == 0 else kwargs.get("ephemeral", False)
        )
        self.followup_count += 1
        self.messages.append({"args": args, "kwargs": kwargs, "ephemeral": effective_ephemeral, "deleted": False})
        message = MagicMock(spec=discord.Message)
        message.edit = AsyncMock()
        return message

    async def _delete_original(self) -> None:
        if self.delete_error:
            raise self.delete_error
        self.messages[0]["deleted"] = True

    def visible_messages(self) -> list[dict[str, Any]]:
        return [message for message in self.messages if not message["deleted"]]


def make_bot(commands_channel_id: int | None = 20) -> MagicMock:
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_commands_channel.return_value = commands_channel_id
    bot.db.get_study_group_by_channel.return_value = None
    bot.db.get_study_group.return_value = None
    bot.db.add_task.return_value = 7
    return bot


@pytest.mark.asyncio
async def test_deferred_first_followup_inherits_initial_visibility():
    harness = InteractionHarness()
    await harness.interaction.response.defer(ephemeral=True)
    await harness.interaction.followup.send("Done", ephemeral=False)
    assert harness.visible_messages()[0]["ephemeral"] is True
    with pytest.raises(discord.InteractionResponded):
        await harness.interaction.response.send_message("A second acknowledgement")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("channel_id", "guild_id", "configured_id", "private"),
    [
        (20, 1, 20, False),
        (21, 1, 20, True),
        (20, None, 20, True),
        (20, 1, None, True),
    ],
)
async def test_visibility_uses_exact_configured_channel(
    channel_id: int, guild_id: int | None, configured_id: int | None, private: bool
):
    harness = InteractionHarness(channel_id, guild_id)
    bot = make_bot(configured_id)
    assert await should_use_ephemeral(harness.interaction, bot.db) is private


@pytest.mark.asyncio
async def test_thread_and_lookup_failure_stay_private():
    harness = InteractionHarness()
    harness.interaction.channel = MagicMock(spec=discord.Thread)
    bot = make_bot()
    assert await should_use_ephemeral(harness.interaction, bot.db) is True
    bot.db.get_commands_channel.assert_not_awaited()

    harness.interaction.channel = MagicMock(spec=discord.TextChannel)
    bot.db.get_commands_channel.side_effect = RuntimeError("database offline")
    assert await should_use_ephemeral(harness.interaction, bot.db) is True


@pytest.mark.asyncio
async def test_acknowledgement_cleanup_failure_does_not_hide_result():
    harness = InteractionHarness()
    harness.delete_error = discord.HTTPException(MagicMock(status=403, reason="Forbidden"), "denied")
    await acknowledge_interaction(harness.interaction)
    await send_response(harness.interaction, "Done", ephemeral=False)
    assert harness.visible_messages()[-1]["args"] == ("Done",)
    assert harness.visible_messages()[-1]["ephemeral"] is False
    harness.interaction.delete_original_response.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(("channel_id", "private"), [(20, False), (21, True)])
async def test_task_add_effective_visibility(channel_id: int, private: bool):
    harness = InteractionHarness(channel_id)
    bot = make_bot()
    cog = TaskList(bot)
    await getattr(cog.add_task, "callback")(cog, harness.interaction, description="Review notes")
    assert harness.responded
    assert harness.visible_messages()[-1]["ephemeral"] is private
    assert "Task added successfully" in harness.visible_messages()[-1]["args"][0]
    assert len(harness.visible_messages()) == 1


@pytest.mark.asyncio
async def test_task_add_acknowledges_before_settings_lookup():
    harness = InteractionHarness()
    bot = make_bot()

    async def get_commands_channel(guild_id: int) -> int:
        assert guild_id == 1
        assert harness.responded
        return 20

    bot.db.get_commands_channel.side_effect = get_commands_channel
    cog = TaskList(bot)
    await getattr(cog.add_task, "callback")(cog, harness.interaction, description="Review notes")
    assert harness.visible_messages()[-1]["ephemeral"] is False


@pytest.mark.asyncio
async def test_voice_channel_success_is_public_and_missing_group_error_is_private():
    bot = make_bot()
    bot.db.get_study_group.return_value = {"group_id": "group-1", "vc_id": None, "name": "Study"}
    bot.db.get_group_roles.return_value = (None, None)
    harness = InteractionHarness()
    channel = MagicMock(spec=discord.VoiceChannel)
    channel.id = 91
    channel.mention = "<#91>"
    harness.interaction.guild.create_voice_channel = AsyncMock(return_value=channel)
    harness.interaction.guild.get_role.return_value = None
    cog = VoiceChannels(bot)
    await cog.create_vc.callback(cog, harness.interaction, name="Study VC")
    assert harness.visible_messages()[-1]["ephemeral"] is False
    assert "created" in harness.visible_messages()[-1]["args"][0]

    bot.db.get_study_group.return_value = None
    missing = InteractionHarness()
    await cog.create_vc.callback(cog, missing.interaction, name=None)
    assert missing.visible_messages()[-1]["ephemeral"] is True
    assert "No study group" in missing.visible_messages()[-1]["args"][0]


@pytest.mark.asyncio
async def test_pomodoro_missing_group_is_private_in_commands_channel():
    bot = make_bot()
    bot.db.get_user_group.return_value = None
    harness = InteractionHarness()
    cog = Pomodoro(bot)
    await cog.start_pomodoro.callback(cog, harness.interaction, require_vc=False)
    assert harness.responded
    assert harness.visible_messages()[-1]["ephemeral"] is True
    assert "not in any study group" in harness.visible_messages()[-1]["args"][0]


@pytest.mark.asyncio
async def test_productivity_result_is_public_in_commands_channel():
    bot = make_bot()
    harness = InteractionHarness()
    cog = ProductivityTracker(bot)
    cog.productivity_service.get_productivity_metrics = AsyncMock(
        return_value={"tasks_completed": 2, "time_spent": 1, "efficiency_score": 2}
    )
    await cog.productivity.callback(cog, harness.interaction)
    assert harness.visible_messages()[-1]["ephemeral"] is False
    assert harness.visible_messages()[-1]["kwargs"]["embed"].title == "Tester's Productivity Metrics"


@pytest.mark.asyncio
async def test_checkin_invalid_duration_is_private_in_commands_channel():
    bot = make_bot()
    harness = InteractionHarness()
    cog = CheckinCog(bot)
    await cog.start_checkin.callback(cog, harness.interaction, name="Standup", duration="invalid")
    assert harness.responded
    assert harness.visible_messages()[-1]["ephemeral"] is True
    assert harness.visible_messages()[-1]["args"] == ("Invalid duration format.",)


@pytest.mark.asyncio
async def test_checkin_owner_menu_uses_private_followup():
    bot = make_bot()
    harness = InteractionHarness()
    harness.interaction.channel.send = AsyncMock()
    member = MagicMock(spec=discord.Member)
    member.display_name = "Teammate"
    harness.interaction.guild.get_member.return_value = member
    cog = CheckinCog(bot)
    settings = CheckinGuildSettings(harness.interaction)
    session = CheckinSession(bot.db, cog, harness.interaction, "Standup", [5, 6], 60, settings)

    await session.change_owner_callback(harness.interaction)

    assert harness.responded
    assert harness.visible_messages()[-1]["ephemeral"] is True
    assert "select the new owner" in harness.visible_messages()[-1]["args"][0]
    harness.interaction.channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_global_error_handler_acknowledges_privately():
    harness = InteractionHarness()
    await on_app_command_error(harness.interaction, discord.app_commands.CheckFailure("Denied"))
    assert harness.responded
    assert harness.visible_messages()[-1]["ephemeral"] is True
    assert harness.visible_messages()[-1]["args"] == ("Denied",)


@pytest.mark.asyncio
async def test_global_error_handler_after_acknowledgement_stays_private():
    harness = InteractionHarness()
    await acknowledge_interaction(harness.interaction)
    await on_app_command_error(harness.interaction, discord.app_commands.CheckFailure("Denied"))
    assert harness.visible_messages() == [
        {"args": ("Denied",), "kwargs": {"ephemeral": True}, "ephemeral": True, "deleted": False}
    ]
