import asyncio
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import DBHandler


class TestDBHandler(unittest.TestCase):
    def setUp(self):
        # Use an in-memory SQLite database for testing
        self.db = DBHandler(db_name=":memory:")

    def tearDown(self):
        async def cleanup():
            await self.db.close()

        asyncio.run(cleanup())

    def test_database_initialization_and_tasks(self):
        async def run_test():
            await self.db.connect()

            # Test adding task
            task_id = await self.db.add_task(user_id=123, description="Write documentation")
            self.assertIsNotNone(task_id)

            # Test getting tasks
            tasks = await self.db.get_user_tasks(user_id=123)
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["description"], "Write documentation")
            self.assertEqual(tasks[0]["completed"], 0)

            # Test completing task
            success = await self.db.complete_task(user_id=123, task_id=task_id)
            self.assertTrue(success)

            # Verify completed state
            tasks = await self.db.get_user_tasks(user_id=123)
            self.assertEqual(tasks[0]["completed"], 1)

        asyncio.run(run_test())

    def test_manager_permissions(self):
        async def run_test():
            await self.db.connect()

            # Add manager
            await self.db.add_manager(user_id=999, guild_id=100, permission_level=3)
            manager = await self.db.get_manager(user_id=999, guild_id=100)
            self.assertIsNotNone(manager)
            self.assertEqual(manager["permission_level"], 3)

            # Remove manager
            await self.db.remove_manager(user_id=999, guild_id=100)
            manager_after = await self.db.get_manager(user_id=999, guild_id=100)
            self.assertIsNone(manager_after)

        asyncio.run(run_test())

    def test_task_scope_can_be_global_only_or_all_groups(self):
        async def run_test():
            await self.db.connect()
            await self.db.add_task(123, "Global task")
            await self.db.add_task(123, "Group task", group_id="group-1")
            await self.db.add_task(123, "Server task", guild_id=99)

            global_tasks = await self.db.get_user_tasks(123, global_only=True)
            server_tasks = await self.db.get_user_tasks(123, guild_id=99)
            all_tasks = await self.db.get_user_tasks(123)

            self.assertEqual([task["description"] for task in global_tasks], ["Global task"])
            self.assertEqual([task["description"] for task in server_tasks], ["Server task"])
            self.assertEqual([task["description"] for task in all_tasks], ["Global task", "Group task", "Server task"])

        asyncio.run(run_test())

    def test_study_group_transfer_and_channel_lookup(self):
        async def run_test():
            await self.db.connect()

            # Save study group
            group_data = {
                "group_id": "sg-transfer-test",
                "guild_id": 885134,
                "name": "Physics Cohort",
                "creator_id": 111,
                "owner_id": 111,
                "category_id": 222,
                "group_role_id": 333,
                "vc_id": 444,
                "text_id": 555,
                "start_time": 1000.0,
                "duration": 3600,
                "end_time": 4600.0,
                "max_members": 5,
                "member_ids": [222, 333],
                "active": 1,
            }
            await self.db.save_study_group(group_data)

            # Lookup by channel
            by_channel = await self.db.get_study_group_by_channel(555)
            self.assertIsNotNone(by_channel)
            assert by_channel is not None
            self.assertIsInstance(by_channel, dict)
            self.assertEqual(by_channel["name"], "Physics Cohort")
            self.assertEqual(by_channel["owner_id"], 111)

            group_members = await self.db.fetch_members_of_group("sg-transfer-test")
            self.assertCountEqual(group_members, [111, 222, 333])
            member_group = await self.db.get_user_group(222, 555)
            self.assertIsInstance(member_group, dict)
            self.assertEqual(member_group["group_id"], "sg-transfer-test")

            guild_groups = await self.db.get_all_study_groups_of_guild(885134)
            self.assertIsInstance(guild_groups[0], dict)
            listed_members = await self.db.fetch_members_of_group(guild_groups[0]["group_id"])
            self.assertCountEqual(listed_members, [111, 222, 333])

            by_guild = await self.db.get_study_group(885134)
            self.assertIsInstance(by_guild, dict)
            self.assertEqual(by_guild["group_id"], "sg-transfer-test")

            # Transfer ownership
            await self.db.transfer_ownership_study_group_db("sg-transfer-test", 999)
            transferred = await self.db.fetch_study_group_by_id("sg-transfer-test")
            self.assertIsNotNone(transferred)
            assert transferred is not None
            self.assertEqual(transferred["owner_id"], 999)

        asyncio.run(run_test())

    def test_commands_channel_migration_preserves_legacy_settings_on_restart(self):
        async def run_test(db_path):
            db = DBHandler(db_name=str(db_path))
            await db.connect()
            self.assertIsNone(await db.get_commands_channel(101))
            self.assertIsNone(await db.get_commands_channel(999))
            self.assertEqual(await db.get_group_category(101), 201)
            self.assertEqual(await db.get_vc_cleanup_time(101), 900)
            await db.save_setup(101, 202, 303, 12, log_channel_id=601)
            await db.close()

            reopened = DBHandler(db_name=str(db_path))
            await reopened.connect()
            self.assertEqual(await reopened.get_commands_channel(101), 303)
            self.assertEqual(await reopened.get_group_category(101), 202)
            self.assertEqual(await reopened.get_default_max_members(101), 12)
            self.assertEqual(await reopened.get_vc_cleanup_time(101), 900)
            self.assertEqual(await reopened.get_vc_category(101), 501)
            self.assertEqual(await reopened.get_mod_log_channel(101), 601)
            await reopened.create_tables()
            self.assertEqual(await reopened.get_commands_channel(101), 303)
            await reopened.save_setup(101, 203, 304, 13)
            self.assertEqual(await reopened.get_mod_log_channel(101), 601)
            await reopened.close()

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy.sqlite"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute(
                    "CREATE TABLE guild_settings (guild_id INTEGER PRIMARY KEY, "
                    "vc_cleanup_time INTEGER DEFAULT 600, vc_category_id INTEGER, "
                    "group_category_id INTEGER)"
                )
                conn.execute(
                    "INSERT INTO guild_settings (guild_id, vc_cleanup_time, vc_category_id, "
                    "group_category_id) VALUES (?, ?, ?, ?)",
                    (101, 900, 501, 201),
                )
                conn.commit()
            asyncio.run(run_test(db_path))

    def test_setup_and_vc_setters_preserve_other_settings(self):
        async def run_test():
            await self.db.connect()
            await self.db.update_vc_cleanup_time(101, 900)
            await self.db.update_vc_category(101, 501)
            self.assertIsNone(await self.db.get_commands_channel(101))
            self.assertEqual(await self.db.get_default_max_members(101), 10)
            await self.db.set_mod_log_channel(101, 601)

            await self.db.save_setup(101, 201, 301, 15)
            self.assertEqual(await self.db.get_vc_cleanup_time(101), 900)
            self.assertEqual(await self.db.get_vc_category(101), 501)
            self.assertEqual(await self.db.get_mod_log_channel(101), 601)

            await self.db.update_vc_cleanup_time(101, 901)
            await self.db.update_vc_category(101, 502)
            self.assertEqual(await self.db.get_group_category(101), 201)
            self.assertEqual(await self.db.get_commands_channel(101), 301)
            self.assertEqual(await self.db.get_default_max_members(101), 15)
            self.assertEqual(await self.db.get_mod_log_channel(101), 601)

            await self.db.save_setup(101, 202, 302, 16, log_channel_id=602)
            self.assertEqual(await self.db.get_group_category(101), 202)
            self.assertEqual(await self.db.get_commands_channel(101), 302)
            self.assertEqual(await self.db.get_default_max_members(101), 16)
            self.assertEqual(await self.db.get_vc_cleanup_time(101), 901)
            self.assertEqual(await self.db.get_vc_category(101), 502)
            self.assertEqual(await self.db.get_mod_log_channel(101), 602)

            await self.db.save_setup(102, 203, 303, 17, log_channel_id=603)
            self.assertEqual(await self.db.get_mod_log_channel(102), 603)
            self.assertEqual(await self.db.get_vc_cleanup_time(102), 600)

        asyncio.run(run_test())

    def test_failed_setup_commit_rolls_back_before_retry(self):
        async def run_test():
            await self.db.connect()
            await self.db.save_setup(101, 201, 301, 15, log_channel_id=601)
            async with self.db.lock:
                self.db.conn.execute("PRAGMA foreign_keys = ON")
                self.db.conn.execute("CREATE TABLE allowed_setup (id INTEGER PRIMARY KEY)")
                self.db.conn.execute(
                    "CREATE TABLE setup_guard (parent_id INTEGER REFERENCES allowed_setup(id) "
                    "DEFERRABLE INITIALLY DEFERRED)"
                )
                self.db.conn.execute(
                    "CREATE TRIGGER reject_setup AFTER UPDATE OF group_category_id ON guild_settings "
                    "WHEN NEW.group_category_id = 999 BEGIN "
                    "INSERT INTO setup_guard (parent_id) VALUES (999); END"
                )

            with self.assertRaises(sqlite3.IntegrityError):
                await self.db.save_setup(101, 999, 302, 16, log_channel_id=602)

            self.assertFalse(self.db.conn.in_transaction)
            self.assertEqual(await self.db.get_group_category(101), 201)
            self.assertEqual(await self.db.get_commands_channel(101), 301)
            self.assertEqual(await self.db.get_default_max_members(101), 15)
            self.assertEqual(await self.db.get_mod_log_channel(101), 601)
            async with self.db.lock:
                self.assertEqual(self.db.conn.execute("SELECT COUNT(*) FROM setup_guard").fetchone()[0], 0)

            await self.db.save_setup(101, 202, 302, 16, log_channel_id=602)
            self.assertEqual(await self.db.get_group_category(101), 202)
            self.assertEqual(await self.db.get_commands_channel(101), 302)
            self.assertEqual(await self.db.get_default_max_members(101), 16)
            self.assertEqual(await self.db.get_mod_log_channel(101), 602)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
