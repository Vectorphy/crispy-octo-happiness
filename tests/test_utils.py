import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils import ProductivityService, parse_duration, parse_seconds_to_hms, should_use_ephemeral


class TestUtils(unittest.TestCase):
    def test_response_visibility_matches_configured_category(self):
        async def run_test():
            db = AsyncMock()
            db.get_group_category.return_value = 42
            public_interaction = SimpleNamespace(
                guild=SimpleNamespace(id=7),
                channel=SimpleNamespace(category_id=42),
            )
            outside_interaction = SimpleNamespace(
                guild=SimpleNamespace(id=7),
                channel=SimpleNamespace(category_id=99),
            )

            self.assertFalse(await should_use_ephemeral(public_interaction, db))
            self.assertTrue(await should_use_ephemeral(outside_interaction, db))
            db.get_group_category.assert_awaited()

        import asyncio

        asyncio.run(run_test())

    def test_response_visibility_is_ephemeral_without_guild_or_category(self):
        async def run_test():
            db = AsyncMock()
            no_guild = SimpleNamespace(guild=None, channel=None)
            no_category = SimpleNamespace(guild=SimpleNamespace(id=7), channel=SimpleNamespace(category_id=None))

            self.assertTrue(await should_use_ephemeral(no_guild, db))
            self.assertTrue(await should_use_ephemeral(no_category, db))
            db.get_group_category.assert_not_awaited()

        import asyncio

        asyncio.run(run_test())

    def test_parse_duration(self):
        self.assertEqual(parse_duration("30s"), 30)
        self.assertEqual(parse_duration("15m"), 900)
        self.assertEqual(parse_duration("2h"), 7200)
        self.assertEqual(parse_duration("1d"), 86400)
        self.assertEqual(parse_duration("45 mins"), 2700)
        self.assertEqual(parse_duration("3 hours"), 10800)
        self.assertIsNone(parse_duration("invalid_string"))

    def test_parse_seconds_to_hms(self):
        self.assertEqual(parse_seconds_to_hms(45), "45 seconds")
        self.assertEqual(parse_seconds_to_hms(125), "2 minutes 5 seconds")
        self.assertEqual(parse_seconds_to_hms(3665), "1 hour 1 minute 5 seconds")
        self.assertEqual(parse_seconds_to_hms(7200), "2 hours")

    def test_productivity_efficiency_calculation(self):
        service = ProductivityService(db_handler=None)
        self.assertEqual(service.calculate_efficiency(10, 2), 5.0)
        self.assertEqual(service.calculate_efficiency(0, 5), 0.0)
        self.assertEqual(service.calculate_efficiency(10, 0), 0.0)
        self.assertEqual(service.calculate_efficiency(7, 3), 2.33)


if __name__ == "__main__":
    unittest.main()
