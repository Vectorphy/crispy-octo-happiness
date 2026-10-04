import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from cogs.tasklist import TaskList
from database import DBHandler
from utils import ProductivityService


class TestTaskListCog(unittest.TestCase):
    def setUp(self):
        self.mock_bot = MagicMock()
        self.mock_db = AsyncMock()
        self.mock_bot.db = self.mock_db
        self.cog = TaskList(self.mock_bot)

    def test_add_task_command(self):
        async def run_test():
            self.mock_db.add_task.return_value = 42
            interaction = AsyncMock()
            interaction.user.id = 12345

            await self.cog.add_task.callback(self.cog, interaction, description="Complete math assignment")

            self.mock_db.add_task.assert_called_once_with(12345, "Complete math assignment")
            interaction.response.send_message.assert_called_once_with("Processing your request…", ephemeral=True)
            interaction.followup.send.assert_called_once_with("Task added successfully. Task ID: 42", ephemeral=True)

        asyncio.run(run_test())

    def test_add_task_command_in_commands_channel(self):
        async def run_test():
            self.mock_db.add_task.return_value = 42
            self.mock_db.get_commands_channel.return_value = 999
            self.mock_db.get_study_group_by_channel.return_value = None
            interaction = AsyncMock()
            interaction.user.id = 12345
            interaction.guild.id = 10
            interaction.channel.category_id = 20
            interaction.channel_id = 999

            await self.cog.add_task.callback(self.cog, interaction, description="Complete math assignment")

            self.mock_db.add_task.assert_called_once_with(12345, "Complete math assignment", guild_id=10)
            interaction.response.send_message.assert_called_once_with("Processing your request…", ephemeral=True)
            interaction.followup.send.assert_called_once_with("Task added successfully. Task ID: 42", ephemeral=False)

        asyncio.run(run_test())

    def test_complete_task_command(self):
        async def run_test():
            self.mock_db.complete_task.return_value = True
            interaction = AsyncMock()
            interaction.user.id = 12345

            await self.cog.complete_task.callback(self.cog, interaction, task_ids="42")

            self.mock_db.complete_task.assert_called_once_with(12345, "42")
            interaction.response.send_message.assert_called_once_with("Processing your request…", ephemeral=True)
            interaction.followup.send.assert_called_once_with("Tasks marked as complete: 42", ephemeral=True)

        asyncio.run(run_test())

    def test_complete_task_command_in_commands_channel(self):
        async def run_test():
            self.mock_db.complete_task.return_value = True
            self.mock_db.get_commands_channel.return_value = 999
            self.mock_db.get_study_group_by_channel.return_value = None
            interaction = AsyncMock()
            interaction.user.id = 12345
            interaction.guild.id = 10
            interaction.channel.category_id = 20
            interaction.channel_id = 999

            await self.cog.complete_task.callback(self.cog, interaction, task_ids="42")

            self.mock_db.complete_task.assert_called_once_with(12345, "42")
            interaction.response.send_message.assert_called_once_with("Processing your request…", ephemeral=True)
            interaction.followup.send.assert_called_once_with("Tasks marked as complete: 42", ephemeral=False)

        asyncio.run(run_test())

    def test_list_tasks_in_commands_channel_is_public(self):
        async def run_test():
            self.mock_db.get_commands_channel.return_value = 999
            self.mock_db.get_study_group_by_channel.return_value = None
            self.mock_db.get_user_tasks.return_value = [
                {"id": 1, "description": "Task 1", "completed": 0, "group_id": None}
            ]
            interaction = AsyncMock()
            interaction.user.id = 12345
            interaction.user.display_name = "TestUser"
            interaction.guild.id = 10
            interaction.channel.category_id = 20
            interaction.channel_id = 999

            await self.cog.list_tasks.callback(self.cog, interaction, all_groups=False)

            interaction.response.send_message.assert_called_once_with("Processing your request…", ephemeral=True)
            interaction.followup.send.assert_called_once()
            self.assertFalse(interaction.followup.send.call_args.kwargs.get("ephemeral"))

        asyncio.run(run_test())

    def test_list_tasks_in_other_channel_is_ephemeral(self):
        async def run_test():
            self.mock_db.get_commands_channel.return_value = 999
            self.mock_db.get_study_group_by_channel.return_value = None
            self.mock_db.get_user_tasks.return_value = [
                {"id": 1, "description": "Task 1", "completed": 0, "group_id": None}
            ]
            interaction = AsyncMock()
            interaction.user.id = 12345
            interaction.user.display_name = "TestUser"
            interaction.guild.id = 10
            interaction.channel.category_id = 999  # Different category
            interaction.channel_id = 123

            await self.cog.list_tasks.callback(self.cog, interaction, all_groups=False)

            interaction.response.send_message.assert_called_once_with("Processing your request…", ephemeral=True)
            interaction.followup.send.assert_called_once()
            self.assertTrue(interaction.followup.send.call_args.kwargs.get("ephemeral"))

        asyncio.run(run_test())


@pytest.fixture
async def task_store():
    db = DBHandler(":memory:")
    await db.connect()
    try:
        await db.save_setup(99, 20, 600, 10)
        await db.save_setup(101, 21, 700, 10)
        for group_id, guild_id, channel_id in (("group-a", 99, 610), ("group-b", 99, 620), ("foreign", 101, 710)):
            await db.save_study_group(
                {"group_id": group_id, "guild_id": guild_id, "name": group_id, "creator_id": 123, "text_id": channel_id}
            )
        await db.add_task(123, "DM personal")
        await db.add_task(123, "Server personal", guild_id=99)
        await db.add_task(123, "Foreign personal", guild_id=101)
        await db.add_task(123, "Group A", group_id="group-a")
        await db.add_task(123, "Group B", group_id="group-b")
        await db.add_task(123, "Foreign group", group_id="foreign")
        await db.add_task(456, "Other owner", guild_id=99)
        yield db
    finally:
        await db.close()


def task_interaction(guild_id, channel_id):
    request = MagicMock(spec=discord.Interaction)
    request.guild = MagicMock(spec=discord.Guild, id=guild_id) if guild_id is not None else None
    request.guild_id, request.channel_id = guild_id, channel_id
    request.channel = MagicMock(spec=discord.TextChannel, id=channel_id)
    request.user = MagicMock(id=123, display_name="Reader")
    request.response = AsyncMock()
    request.response.is_done = MagicMock(return_value=False)
    request.followup = AsyncMock()
    request.extras = {}
    return request


TASK_CONTEXTS = [
    (99, 600, "Server personal", False),
    (99, 610, "Group A", False),
    (101, 700, "Foreign personal", False),
    (None, None, "DM personal", True),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("guild_id,channel_id,description,ephemeral", TASK_CONTEXTS)
async def test_default_task_list_separates_personal_and_group_tasks(
    task_store, guild_id, channel_id, description, ephemeral
):
    cog = TaskList(MagicMock(db=task_store))
    request = task_interaction(guild_id, channel_id)
    await cog.list_tasks.callback(cog, request)
    result = request.followup.send.call_args.kwargs
    assert [task["description"] for task in result["view"].tasks] == [description]
    assert result["ephemeral"] is ephemeral
    result["view"].stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("channel_id", [600, 610])
async def test_explicit_all_groups_lists_all_owned_tasks_privately(task_store, channel_id):
    cog = TaskList(MagicMock(db=task_store))
    request = task_interaction(99, channel_id)
    await cog.list_tasks.callback(cog, request, all_groups=True)
    result = request.followup.send.call_args.kwargs
    assert {task["description"] for task in result["view"].tasks} == {
        "DM personal",
        "Server personal",
        "Foreign personal",
        "Group A",
        "Group B",
        "Foreign group",
    }
    assert result["ephemeral"] is True
    result["view"].stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["complete", "delete"])
@pytest.mark.parametrize("guild_id,channel_id,description", [context[:3] for context in TASK_CONTEXTS])
async def test_task_menu_uses_same_context_scope(task_store, action, guild_id, channel_id, description):
    cog = TaskList(MagicMock(db=task_store))
    request = task_interaction(guild_id, channel_id)
    command = cog.complete_task if action == "complete" else cog.delete_task
    await command.callback(cog, request)
    result = request.followup.send.call_args.kwargs
    select = result["view"].children[0]
    assert [option.label.split(" - ", 1)[1] for option in select.options] == [description]
    assert result["ephemeral"] is True
    result["view"].stop()


@pytest.mark.asyncio
async def test_completed_task_analytics_retains_all_owned_scopes(task_store):
    for task in await task_store.get_user_tasks(123):
        if task["description"] in {"DM personal", "Server personal", "Foreign group"}:
            await task_store.apply_task_action(123, task["id"], task["group_id"], "complete")
    assert await ProductivityService(task_store).get_tasks_completed(123) == 3


if __name__ == "__main__":
    unittest.main()
