import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

# Add the root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cogs.productivity_tracker import ProductivityTracker
from utils import ProductivityService


class MockDBHandler:
    async def get_user_tasks(self, user_id):
        if user_id == 1:
            return [
                {"id": 1, "user_id": 1, "description": "Task 1", "completed": True},
                {"id": 2, "user_id": 1, "description": "Task 2", "completed": False},
                {"id": 3, "user_id": 1, "description": "Task 3", "completed": True},
            ]
        return []

    async def get_productivity_focus_seconds(self, user_id):
        return 3600.0 if user_id == 1 else 0.0


class TestProductivityService(unittest.TestCase):
    def setUp(self):
        self.db_handler = MockDBHandler()
        self.service = ProductivityService(self.db_handler)

    def test_calculate_efficiency(self):
        self.assertEqual(self.service.calculate_efficiency(10, 2), 5.0)
        self.assertEqual(self.service.calculate_efficiency(10, 0), 0.0)

    def test_metrics_use_attended_focus_and_zero_when_untracked(self):
        async def run_test():
            measured = await self.service.get_productivity_metrics(1)
            self.assertEqual(measured["tasks_completed"], 2)
            self.assertEqual(measured["time_spent"], 1.0)
            self.assertEqual(measured["efficiency_score"], 2.0)

            untracked = await self.service.get_productivity_metrics(2)
            self.assertEqual(untracked["time_spent"], 0.0)
            self.assertEqual(untracked["efficiency_score"], 0.0)

        asyncio.run(run_test())

    def test_efficiency_uses_unrounded_focus_hours(self):
        async def run_test():
            db = AsyncMock()
            db.get_user_tasks.return_value = [{"completed": True}]
            db.get_productivity_focus_seconds.return_value = 1.0
            metrics = await ProductivityService(db).get_productivity_metrics(1)
            self.assertEqual(metrics["time_spent"], 0.0003)
            self.assertEqual(metrics["efficiency_score"], 3600.0)

        asyncio.run(run_test())

    def test_get_tasks_completed(self):
        async def run_test():
            tasks = await self.service.get_tasks_completed(1)
            self.assertEqual(tasks, 2)
            tasks_zero = await self.service.get_tasks_completed(2)
            self.assertEqual(tasks_zero, 0)

        asyncio.run(run_test())


class TestProductivityTrackerCog(unittest.TestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.bot.db = MockDBHandler()
        self.cog = ProductivityTracker(self.bot)

    def test_productivity_command(self):
        async def run_test():
            mock_interaction = AsyncMock()
            mock_interaction.user.id = 1
            mock_interaction.user.display_name = "Test User"

            await self.cog.productivity.callback(self.cog, mock_interaction)

            mock_interaction.followup.send.assert_called_once()
            embed = mock_interaction.followup.send.call_args[1]["embed"]

            self.assertEqual(embed.title, "Test User's Productivity Metrics")
            self.assertEqual(len(embed.fields), 3)
            self.assertEqual(embed.fields[0].name, "Tasks Completed")
            self.assertEqual(embed.fields[0].value, "2")
            self.assertEqual(embed.fields[1].name, "Attended Focus Time (hours)")
            self.assertEqual(embed.fields[1].value, "1")
            self.assertEqual(embed.fields[2].value, "2.0")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
