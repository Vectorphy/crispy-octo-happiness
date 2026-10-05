import asyncio
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from typing import Any

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

    def test_legacy_global_developers_remain_inert_and_guild_staff_distinct(self):
        async def run_test():
            await self.db.connect()
            await self.db.add_manager(123, 101, 3)
            await self.db.add_manager(123, None, 4)
            await self.db.add_manager(123, None, 4)
            await self.db.add_manager(456, 101, 2)
            await self.db.add_manager(789, 102, 3)

            guild_managers = await self.db.get_all_managers(101)
            self.assertEqual(
                {(row["user_id"], row["guild_id"], row["permission_level"]) for row in guild_managers},
                {(123, 101, 3), (456, 101, 3)},
            )
            self.assertEqual(len(guild_managers), 2)
            self.assertEqual((await self.db.get_manager(123, 101))["permission_level"], 3)
            self.assertIsNone(await self.db.get_manager(123, 102))
            self.assertIsNone(await self.db.get_manager(456, 102))

            await self.db.add_manager(456, 101, 3)
            await self.db.add_manager(123, None, 3)
            self.assertEqual((await self.db.get_manager(456, 101))["permission_level"], 3)
            self.assertEqual((await self.db.get_manager(123, 101))["permission_level"], 3)
            self.assertIsNone(await self.db.get_manager(123, 102))
            self.assertEqual(len(await self.db.get_all_managers(101)), 2)

            await self.db.remove_manager(123, None)
            self.assertEqual((await self.db.get_manager(123, 101))["permission_level"], 3)

        asyncio.run(run_test())

    def test_manager_grant_source_migrates_legacy_rows_and_survives_restart(self):
        async def run_test(db_path):
            db = DBHandler(str(db_path))
            await db.connect()
            row = await db.get_manager(123, 101)
            self.assertEqual((row["permission_level"], row["grant_source"]), (3, "explicit"))
            await db.create_tables()
            self.assertEqual((await db.get_manager(123, 101))["grant_source"], "explicit")
            await db.close()

            reopened = DBHandler(str(db_path))
            await reopened.connect()
            self.assertEqual((await reopened.get_manager(123, 101))["grant_source"], "explicit")
            await reopened.close()

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy.sqlite"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute(
                    "CREATE TABLE managers (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, "
                    "guild_id INTEGER, permission_level INTEGER NOT NULL)"
                )
                conn.execute(
                    "INSERT INTO managers (user_id, guild_id, permission_level) VALUES (?, ?, ?)",
                    (123, 101, 2),
                )
                conn.commit()
            asyncio.run(run_test(db_path))

    def test_native_staff_sync_preserves_explicit_and_other_guild_grants(self):
        async def run_test():
            await self.db.connect()
            await self.db.add_manager(10, None, 4)
            await self.db.add_manager(20, 101, 3)
            await self.db.add_manager(30, 102, 2, grant_source="server_sync")
            await self.db.add_manager(40, 101, 2, grant_source="server_sync")
            await self.db.sync_guild_manager_grants(101, {20: 2, 50: 3})
            self.assertIsNone(await self.db.get_manager(40, 101))
            self.assertEqual((await self.db.get_manager(20, 101))["permission_level"], 3)
            self.assertEqual((await self.db.get_manager(20, 101))["grant_source"], "explicit")
            self.assertEqual((await self.db.get_manager(50, 101))["grant_source"], "server_sync")
            self.assertEqual((await self.db.get_manager(30, 102))["grant_source"], "server_sync")
            self.assertIsNone(await self.db.get_manager(10, 102))

            await self.db.add_manager(50, 101, 2)
            await self.db.sync_guild_manager_grants(101, {})
            self.assertEqual((await self.db.get_manager(50, 101))["grant_source"], "explicit")
            self.assertEqual((await self.db.get_manager(50, 101))["permission_level"], 3)
            await self.db.add_manager(50, 101, 3, grant_source="server_sync")
            self.assertEqual((await self.db.get_manager(50, 101))["permission_level"], 3)

        asyncio.run(run_test())

    def test_native_staff_sync_invalid_level_does_not_change_grants(self):
        async def run_test():
            await self.db.connect()
            await self.db.sync_guild_manager_grants(101, {20: 2})
            with self.assertRaises(ValueError):
                await self.db.sync_guild_manager_grants(101, {30: 4})
            with self.assertRaises(ValueError):
                await self.db.add_manager(30, 101, 2, grant_source="unknown")
            self.assertEqual(
                [(r["user_id"], r["grant_source"]) for r in await self.db.get_all_managers(101)], [(20, "server_sync")]
            )

        asyncio.run(run_test())

    def test_native_staff_sync_rolls_back_cleanup_if_insert_fails(self):
        async def run_test():
            await self.db.connect()
            await self.db.sync_guild_manager_grants(101, {20: 2})
            async with self.db.lock:
                self.db.conn.execute(
                    "CREATE TRIGGER reject_native_staff BEFORE INSERT ON managers "
                    "WHEN NEW.user_id = 30 BEGIN SELECT RAISE(ABORT, 'sync failed'); END"
                )
                self.db.conn.commit()

            with self.assertRaises(sqlite3.IntegrityError):
                await self.db.sync_guild_manager_grants(101, {30: 3})
            self.assertEqual(
                [(r["user_id"], r["grant_source"]) for r in await self.db.get_all_managers(101)],
                [(20, "server_sync")],
            )

        asyncio.run(run_test())

    def test_task_scope_can_be_global_only_or_all_groups(self):
        async def run_test():
            await self.db.connect()
            await self.db.add_task(123, "Global task")
            await self.db.add_task(123, "Group task", group_id="group-1")
            await self.db.add_task(123, "Server task", guild_id=99)
            await self.db.add_task(123, "Server group task", group_id="group-2", guild_id=99)
            await self.db.add_task(123, "Foreign server task", guild_id=101)

            global_tasks = await self.db.get_user_tasks(123, global_only=True)
            server_tasks = await self.db.get_user_tasks(123, guild_id=99)
            server_personal_tasks = await self.db.get_user_tasks(123, global_only=True, guild_id=99)
            all_tasks = await self.db.get_user_tasks(123)

            self.assertEqual([task["description"] for task in global_tasks], ["Global task"])
            self.assertEqual([task["description"] for task in server_tasks], ["Server task", "Server group task"])
            self.assertEqual([task["description"] for task in server_personal_tasks], ["Server task"])
            self.assertEqual(
                [task["description"] for task in all_tasks],
                ["Global task", "Group task", "Server task", "Server group task", "Foreign server task"],
            )

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

    def test_group_names_include_retired_groups_but_only_requested_guild(self):
        async def run_test():
            await self.db.connect()
            for group_id, guild_id, name, active in (
                ("one", 101, "alex-studysession-1", 0),
                ("two", 101, "alex-studysession-2", 1),
                ("three", 102, "alex-studysession-3", 1),
            ):
                await self.db.save_study_group(
                    {
                        "group_id": group_id,
                        "guild_id": guild_id,
                        "name": name,
                        "creator_id": 123,
                        "active": active,
                    }
                )
            self.assertEqual(
                await self.db.get_guild_group_names(101),
                ["alex-studysession-1", "alex-studysession-2"],
            )
            self.assertEqual(await self.db.get_guild_group_names(103), [])

        asyncio.run(run_test())

    def test_commands_channel_migration_preserves_legacy_settings_on_restart(self):
        async def run_test(db_path):
            db = DBHandler(db_name=str(db_path))
            await db.connect()
            self.assertIsNone(await db.get_commands_channel(101))
            self.assertIsNone(await db.get_commands_channel(999))
            self.assertEqual(await db.get_default_group_duration(101), 86400)
            self.assertEqual(await db.get_default_pomodoro_duration(999), 86400)
            self.assertEqual(await db.get_group_category(101), 201)
            self.assertEqual(await db.get_vc_cleanup_time(101), 900)
            await db.save_setup(
                101,
                202,
                303,
                12,
                log_channel_id=601,
                default_group_duration=7200,
                default_pomodoro_duration=10800,
            )
            await db.close()

            reopened = DBHandler(db_name=str(db_path))
            await reopened.connect()
            self.assertEqual(await reopened.get_commands_channel(101), 303)
            self.assertEqual(await reopened.get_group_category(101), 202)
            self.assertEqual(await reopened.get_default_max_members(101), 12)
            self.assertEqual(await reopened.get_vc_cleanup_time(101), 900)
            self.assertEqual(await reopened.get_vc_category(101), 501)
            self.assertEqual(await reopened.get_mod_log_channel(101), 601)
            self.assertEqual(await reopened.get_default_group_duration(101), 7200)
            self.assertEqual(await reopened.get_default_pomodoro_duration(101), 10800)
            await reopened.create_tables()
            self.assertEqual(await reopened.get_commands_channel(101), 303)
            await reopened.save_setup(101, 203, 304, 13)
            self.assertEqual(await reopened.get_mod_log_channel(101), 601)
            self.assertEqual(await reopened.get_default_group_duration(101), 7200)
            self.assertEqual(await reopened.get_default_pomodoro_duration(101), 10800)
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
            self.assertEqual(await self.db.get_default_group_duration(102), 86400)
            self.assertEqual(await self.db.get_default_pomodoro_duration(102), 86400)
            await self.db.save_setup(
                101,
                204,
                304,
                18,
                default_group_duration=14400,
                default_pomodoro_duration=21600,
            )
            self.assertEqual(await self.db.get_default_group_duration(101), 14400)
            self.assertEqual(await self.db.get_default_pomodoro_duration(101), 21600)
            self.assertEqual(await self.db.get_default_group_duration(102), 86400)
            self.assertEqual(await self.db.get_default_pomodoro_duration(102), 86400)
            self.assertEqual(await self.db.get_vc_category(101), 502)
            self.assertEqual(await self.db.get_mod_log_channel(101), 602)

        asyncio.run(run_test())

    def test_failed_setup_commit_rolls_back_before_retry(self):
        async def run_test():
            await self.db.connect()
            await self.db.save_setup(
                101,
                201,
                301,
                15,
                log_channel_id=601,
                default_group_duration=7200,
                default_pomodoro_duration=10800,
            )
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
                await self.db.save_setup(
                    101,
                    999,
                    302,
                    16,
                    log_channel_id=602,
                    default_group_duration=14400,
                    default_pomodoro_duration=21600,
                )

            self.assertFalse(self.db.conn.in_transaction)
            self.assertEqual(await self.db.get_group_category(101), 201)
            self.assertEqual(await self.db.get_commands_channel(101), 301)
            self.assertEqual(await self.db.get_default_max_members(101), 15)
            self.assertEqual(await self.db.get_mod_log_channel(101), 601)
            self.assertEqual(await self.db.get_default_group_duration(101), 7200)
            self.assertEqual(await self.db.get_default_pomodoro_duration(101), 10800)
            async with self.db.lock:
                self.assertEqual(self.db.conn.execute("SELECT COUNT(*) FROM setup_guard").fetchone()[0], 0)

            await self.db.save_setup(
                101,
                202,
                302,
                16,
                log_channel_id=602,
                default_group_duration=14400,
                default_pomodoro_duration=21600,
            )
            self.assertEqual(await self.db.get_group_category(101), 202)
            self.assertEqual(await self.db.get_commands_channel(101), 302)
            self.assertEqual(await self.db.get_default_max_members(101), 16)
            self.assertEqual(await self.db.get_mod_log_channel(101), 602)
            self.assertEqual(await self.db.get_default_group_duration(101), 14400)
            self.assertEqual(await self.db.get_default_pomodoro_duration(101), 21600)

        asyncio.run(run_test())

    def test_setup_rejects_invalid_lifetimes_without_changing_settings(self):
        async def run_test():
            await self.db.connect()
            await self.db.save_setup(101, 201, 301, 15, default_group_duration=7200)
            invalid_values: tuple[Any, ...] = (0, -1, True, 10**30, "3600")
            for invalid in invalid_values:
                with self.assertRaises(ValueError):
                    await self.db.save_setup(101, 202, 302, 16, default_pomodoro_duration=invalid)
            self.assertEqual(await self.db.get_group_category(101), 201)
            self.assertEqual(await self.db.get_commands_channel(101), 301)
            self.assertEqual(await self.db.get_default_group_duration(101), 7200)
            self.assertEqual(await self.db.get_default_pomodoro_duration(101), 86400)

        asyncio.run(run_test())

    def test_sqlite_io_runs_off_event_loop(self):
        async def run_test():
            await self.db.connect()
            main_thread_ident = threading.get_ident()
            worker_thread_ident = await self.db._run_in_thread(threading.get_ident)
            self.assertNotEqual(main_thread_ident, worker_thread_ident)

            # Test an actual DB operation off the main thread
            def _get_thread_and_count():
                cur = self.db.conn.execute("SELECT COUNT(*) FROM tasks")
                return threading.get_ident(), cur.fetchone()[0]

            op_thread, count = await self.db._run_in_thread(_get_thread_and_count)
            self.assertNotEqual(main_thread_ident, op_thread)
            self.assertEqual(count, 0)

        asyncio.run(run_test())

    def test_run_in_thread_rejects_same_thread_connection(self):
        async def run_test():
            db = DBHandler(db_name=":memory:")
            db.conn = sqlite3.connect(":memory:")
            try:
                with self.assertRaises(sqlite3.ProgrammingError):
                    await db.create_tables()
            finally:
                db.conn.close()

        asyncio.run(run_test())

    def test_cancellation_keeps_sqlite_worker_locked_until_finished(self):
        import threading

        async def run_test():
            db = DBHandler(":memory:")
            await db.connect()
            entered, release = threading.Event(), threading.Event()

            def worker():
                entered.set()
                release.wait(5)
                db.conn.execute("SELECT 1").fetchone()

            async def operation():
                async with db.lock:
                    await db._run_in_thread(worker)

            task = asyncio.create_task(operation())
            await asyncio.to_thread(entered.wait, 2)
            close = asyncio.create_task(db.close())
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(0)
                self.assertTrue(db.lock.locked())
                self.assertFalse(close.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
            await close

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
