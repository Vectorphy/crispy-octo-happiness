import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from cogs.tasklist import TaskList


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
            interaction.response.defer.assert_called_once_with(ephemeral=True)
            interaction.followup.send.assert_called_once_with("Task added successfully. Task ID: 42", ephemeral=True)

        asyncio.run(run_test())

    def test_add_task_command_in_configured_category(self):
        async def run_test():
            self.mock_db.add_task.return_value = 42
            self.mock_db.get_group_category.return_value = 20
            self.mock_db.get_study_group_by_channel.return_value = None
            interaction = AsyncMock()
            interaction.user.id = 12345
            interaction.guild.id = 10
            interaction.channel.category_id = 20
            interaction.channel_id = 999

            await self.cog.add_task.callback(self.cog, interaction, description="Complete math assignment")

            self.mock_db.add_task.assert_called_once_with(12345, "Complete math assignment", guild_id=10)
            interaction.response.defer.assert_called_once_with(ephemeral=False)
            interaction.followup.send.assert_called_once_with("Task added successfully. Task ID: 42", ephemeral=False)

        asyncio.run(run_test())

    def test_complete_task_command(self):
        async def run_test():
            self.mock_db.complete_task.return_value = True
            interaction = AsyncMock()
            interaction.user.id = 12345

            await self.cog.complete_task.callback(self.cog, interaction, task_ids="42")

            self.mock_db.complete_task.assert_called_once_with(12345, "42")
            interaction.response.defer.assert_called_once_with(ephemeral=True)
            interaction.followup.send.assert_called_once_with("Tasks marked as complete: 42", ephemeral=True)

        asyncio.run(run_test())

    def test_complete_task_command_in_configured_category(self):
        async def run_test():
            self.mock_db.complete_task.return_value = True
            self.mock_db.get_group_category.return_value = 20
            self.mock_db.get_study_group_by_channel.return_value = None
            interaction = AsyncMock()
            interaction.user.id = 12345
            interaction.guild.id = 10
            interaction.channel.category_id = 20
            interaction.channel_id = 999

            await self.cog.complete_task.callback(self.cog, interaction, task_ids="42")

            self.mock_db.complete_task.assert_called_once_with(12345, "42")
            interaction.response.defer.assert_called_once_with(ephemeral=False)
            interaction.followup.send.assert_called_once_with("Tasks marked as complete: 42", ephemeral=False)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
