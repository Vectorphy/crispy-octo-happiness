import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Union

logger = logging.getLogger(__name__)


class DBHandler:
    def __init__(self, db_name: str = "bot_database.sqlite"):
        self.db_name: str = db_name
        self.conn: sqlite3.Connection = None  # type: ignore[assignment]
        self.lock: asyncio.Lock = asyncio.Lock()
        logger.info(f"Database initialized with name: {db_name}")

    async def connect(self):
        self.conn = sqlite3.connect(self.db_name)
        self.conn.row_factory = sqlite3.Row
        logger.info(f"Connected to database: {self.db_name}")
        await self.create_tables()

    async def create_tables(self):
        async with self.lock:
            cursor = self.conn.cursor()

            table_names = {
                row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type = ?", ("table",))
            }
            if "study_groups_db" in table_names and "study_groups" not in table_names:
                cursor.execute("ALTER TABLE study_groups_db RENAME TO study_groups")
            if "study_group_members_db" in table_names and "study_groups_members" not in table_names:
                cursor.execute("ALTER TABLE study_group_members_db RENAME TO study_groups_members")

            ### STUDY GROUPS TABLE
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                group_id TEXT NOT NULL UNIQUE,
                creator_id INTEGER NOT NULL,
                owner_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                max_members INTEGER NOT NULL,
                group_role_id INTEGER DEFAULT 0,
                vc_id INTEGER DEFAULT 0,
                text_id INTEGER DEFAULT 0,
                info_embed_id INTEGER DEFAULT 0,
                speak_enabled BOOLEAN DEFAULT 1,
                video_mode TEXT DEFAULT 'off',
                video_timer INTEGER DEFAULT 10,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                duration INTEGER NOT NULL,
                active BOOLEAN DEFAULT 0
            )
            """)
            logger.info("Created 'study_groups' table.")

            # Check if the info_embed_id column exists
            cursor.execute("PRAGMA table_info(study_groups);")
            columns = [column[1] for column in cursor.fetchall()]
            if "group_id" not in columns:
                cursor.execute("ALTER TABLE study_groups ADD COLUMN group_id TEXT;")
                # Legacy rosters refer to the numeric primary key. Keeping that
                # value as text preserves those relationships during migration.
                logger.info("Migrated legacy study group identifiers without deleting records")
            cursor.execute(
                "UPDATE study_groups SET group_id = CAST(id AS TEXT) WHERE group_id IS NULL OR group_id = ''"
            )
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_groups_group_id ON study_groups(group_id)")
            # If info_embed_id column does not exist, add it
            if "info_embed_id" not in columns:
                cursor.execute("ALTER TABLE study_groups ADD COLUMN info_embed_id INTEGER DEFAULT 0;")
                logger.info("Added 'info_embed_id' column to 'study_groups' table.")

            legacy_columns = {
                "owner_id": "ALTER TABLE study_groups ADD COLUMN owner_id INTEGER DEFAULT 0",
                "category_id": "ALTER TABLE study_groups ADD COLUMN category_id INTEGER DEFAULT 0",
                "max_members": "ALTER TABLE study_groups ADD COLUMN max_members INTEGER DEFAULT 10",
                "group_role_id": "ALTER TABLE study_groups ADD COLUMN group_role_id INTEGER DEFAULT 0",
                "vc_id": "ALTER TABLE study_groups ADD COLUMN vc_id INTEGER DEFAULT 0",
                "text_id": "ALTER TABLE study_groups ADD COLUMN text_id INTEGER DEFAULT 0",
                "speak_enabled": "ALTER TABLE study_groups ADD COLUMN speak_enabled BOOLEAN DEFAULT 1",
                "video_mode": "ALTER TABLE study_groups ADD COLUMN video_mode TEXT DEFAULT 'off'",
                "video_timer": "ALTER TABLE study_groups ADD COLUMN video_timer INTEGER DEFAULT 10",
                "start_time": "ALTER TABLE study_groups ADD COLUMN start_time REAL DEFAULT 0",
                "duration": "ALTER TABLE study_groups ADD COLUMN duration INTEGER DEFAULT 0",
                "active": "ALTER TABLE study_groups ADD COLUMN active BOOLEAN DEFAULT 0",
            }
            for column, migration in legacy_columns.items():
                if column not in columns:
                    cursor.execute(migration)
            if "owner_id" not in columns:
                cursor.execute("UPDATE study_groups SET owner_id = creator_id")
            if "max_members" not in columns and "max_size" in columns:
                cursor.execute("UPDATE study_groups SET max_members = max_size")
            if "group_role_id" not in columns and "session_role_id" in columns:
                cursor.execute("UPDATE study_groups SET group_role_id = COALESCE(session_role_id, 0)")
            if "vc_id" not in columns and "voice_channel_id" in columns:
                cursor.execute("UPDATE study_groups SET vc_id = COALESCE(voice_channel_id, 0)")

            ### STUDY GROUP MEMBERS TABLE
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_groups_members (
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (group_id) REFERENCES study_groups (group_id),
                PRIMARY KEY (group_id, user_id)
            )
            """)
            logger.info("Created 'study_groups_members' table.")
            if (
                "group_id" not in columns
                and cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?", ("table", "group_members")
                ).fetchone()
            ):
                cursor.execute(
                    "INSERT OR IGNORE INTO study_groups_members (group_id, user_id) SELECT CAST(group_members.group_id AS TEXT), group_members.user_id FROM group_members JOIN study_groups ON study_groups.id = group_members.group_id"
                )

            ### POMODORO TABLE
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                id INTEGER PRIMARY KEY,
                group_id INTEGER,
                start_time REAL,
                end_time REAL,
                focus_duration INTEGER,
                short_break_duration INTEGER,
                long_break_duration INTEGER,
                FOREIGN KEY (group_id) REFERENCES study_groups (id)
            )
            """)
            logger.info("Created 'pomodoro_sessions' table.")

            ### MANAGERS TABLE
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS managers (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                guild_id INTEGER,
                permission_level INTEGER NOT NULL,
                grant_source TEXT NOT NULL DEFAULT 'explicit'
            )
            """)

            manager_columns = {column[1] for column in cursor.execute("PRAGMA table_info(managers)")}
            if "grant_source" not in manager_columns:
                cursor.execute("ALTER TABLE managers ADD COLUMN grant_source TEXT NOT NULL DEFAULT 'explicit'")
                logger.info("Added manager grant source setting")
            cursor.execute(
                "UPDATE managers SET permission_level = ? WHERE permission_level = ?",
                (3, 2),
            )

            cursor.execute("""
                DELETE FROM managers
                WHERE rowid NOT IN (
                    SELECT MIN(rowid)
                    FROM managers
                    GROUP BY user_id, IFNULL(guild_id, -1)
                )
            """)
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_managers_user_guild ON managers(user_id, IFNULL(guild_id, -1))"
            )
            self.conn.commit()
            logger.info("Created 'managers' table.")

            ### VOICE CHANNEL LOGS
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS voice_channel_logs (
                id INTEGER PRIMARY KEY,
                group_id INTEGER,
                channel_id INTEGER,
                creator_id INTEGER,
                create_time TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES study_groups (id)
            )
            """)
            logger.info("Created 'voice_channel_logs' table.")

            ### GUILD SETTINGS
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                vc_cleanup_time INTEGER DEFAULT 600,
                vc_category_id INTEGER,
                group_category_id INTEGER,
                commands_channel_id INTEGER,
                default_group_duration INTEGER NOT NULL DEFAULT 86400,
                default_pomodoro_duration INTEGER NOT NULL DEFAULT 86400
            )
            """)
            logger.info("Created 'guild_settings' table.")

            # Check if group_category_id exists in guild_settings
            cursor.execute("PRAGMA table_info(guild_settings);")
            guild_settings_columns = [column[1] for column in cursor.fetchall()]
            if "group_category_id" not in guild_settings_columns:
                cursor.execute("ALTER TABLE guild_settings ADD COLUMN group_category_id INTEGER DEFAULT NULL;")
                logger.info("Added 'group_category_id' column to 'guild_settings' table.")
            if "commands_channel_id" not in guild_settings_columns:
                cursor.execute("ALTER TABLE guild_settings ADD COLUMN commands_channel_id INTEGER DEFAULT NULL;")
                logger.info("Added 'commands_channel_id' column to 'guild_settings' table.")
            if "default_max_members" not in guild_settings_columns:
                cursor.execute("ALTER TABLE guild_settings ADD COLUMN default_max_members INTEGER DEFAULT 10;")
                logger.info("Added 'default_max_members' column to 'guild_settings' table.")
            if "mod_log_channel_id" not in guild_settings_columns:
                cursor.execute("ALTER TABLE guild_settings ADD COLUMN mod_log_channel_id INTEGER DEFAULT NULL;")
                logger.info("Added moderator log channel setting")
            if "default_group_duration" not in guild_settings_columns:
                cursor.execute(
                    "ALTER TABLE guild_settings ADD COLUMN default_group_duration INTEGER NOT NULL DEFAULT 86400"
                )
                logger.info("Added default group duration setting")
            if "default_pomodoro_duration" not in guild_settings_columns:
                cursor.execute(
                    "ALTER TABLE guild_settings ADD COLUMN default_pomodoro_duration INTEGER NOT NULL DEFAULT 86400"
                )
                logger.info("Added default Pomodoro duration setting")

            ### TASKS
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                completed BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            logger.info("Created 'tasks' table.")

            # Check if group_id and task_number columns exist in tasks
            cursor.execute("PRAGMA table_info(tasks);")
            task_columns = [column[1] for column in cursor.fetchall()]
            if "group_id" not in task_columns:
                cursor.execute("ALTER TABLE tasks ADD COLUMN group_id TEXT DEFAULT NULL;")
                logger.info("Added 'group_id' column to 'tasks' table.")
            if "task_id_str" not in task_columns:
                cursor.execute("ALTER TABLE tasks ADD COLUMN task_id_str TEXT DEFAULT NULL;")
                logger.info("Added 'task_id_str' column to 'tasks' table.")

            if "task_number" not in task_columns:
                cursor.execute("ALTER TABLE tasks ADD COLUMN task_number INTEGER DEFAULT NULL;")
                logger.info("Added 'task_number' column to 'tasks' table.")

            if "guild_id" not in task_columns:
                cursor.execute("ALTER TABLE tasks ADD COLUMN guild_id INTEGER DEFAULT NULL;")
                logger.info("Added 'guild_id' column to 'tasks' table.")

            # Backfill guild_id for tasks associated with a study group
            cursor.execute("""
            UPDATE tasks
            SET guild_id = (
                SELECT guild_id FROM study_groups
                WHERE study_groups.group_id = tasks.group_id
                   OR CAST(study_groups.id AS TEXT) = tasks.group_id
                LIMIT 1
            )
            WHERE guild_id IS NULL AND group_id IS NOT NULL;
            """)

            # If the database only has a single guild registered across study groups/settings, backfill remaining unassigned tasks
            cursor.execute(
                "SELECT DISTINCT guild_id FROM study_groups UNION SELECT DISTINCT guild_id FROM guild_settings;"
            )
            distinct_guilds = [r[0] for r in cursor.fetchall() if r[0] is not None]
            if len(distinct_guilds) == 1:
                cursor.execute("UPDATE tasks SET guild_id = ? WHERE guild_id IS NULL;", (distinct_guilds[0],))

            ### CHECKIN SESSIONS TABLE
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkin_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                creator_id INTEGER NOT NULL,
                owner_id INTEGER NOT NULL,
                text_id INTEGER NOT NULL,
                duration INTEGER NOT NULL,
                start_time REAL NOT NULL,
                last_reminder_time REAL NOT NULL,
                next_reminder_time REAL NOT NULL,
                reminder_count INTEGER NOT NULL,
                last_reminder_message_id INTEGER,
                active BOOLEAN DEFAULT 1
            )
            """)
            logger.info("Created 'checkin_sessions' table.")

            ### CHECKIN MEMBERS TABLE
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkin_members (
                session_id TEXT NOT NULL,
                member_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                absences INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES checkin_sessions (session_id),
                PRIMARY KEY (session_id, member_id)
            )
            """)
            logger.info("Created 'checkin_members' table.")

            self.conn.commit()
            logger.info("Database tables created or verified.")

    async def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")

    async def set_mod_log_channel(self, guild_id: int, channel_id: Optional[int]) -> None:
        async with self.lock:
            self.conn.execute(
                "INSERT INTO guild_settings (guild_id, mod_log_channel_id) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET mod_log_channel_id = excluded.mod_log_channel_id",
                (guild_id, channel_id),
            )
            self.conn.commit()

    async def get_mod_log_channel(self, guild_id: int) -> Optional[int]:
        async with self.lock:
            row = self.conn.execute(
                "SELECT mod_log_channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,)
            ).fetchone()
            return row[0] if row else None

    async def get_commands_channel(self, guild_id: int) -> Optional[int]:
        async with self.lock:
            row = self.conn.execute(
                "SELECT commands_channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,)
            ).fetchone()
            return row[0] if row else None

    async def get_default_group_duration(self, guild_id: int) -> int:
        async with self.lock:
            row = self.conn.execute(
                "SELECT default_group_duration FROM guild_settings WHERE guild_id = ?", (guild_id,)
            ).fetchone()
            return int(row[0]) if row and row[0] is not None else 86400

    async def get_default_pomodoro_duration(self, guild_id: int) -> int:
        async with self.lock:
            row = self.conn.execute(
                "SELECT default_pomodoro_duration FROM guild_settings WHERE guild_id = ?", (guild_id,)
            ).fetchone()
            return int(row[0]) if row and row[0] is not None else 86400

    async def save_setup(
        self,
        guild_id: int,
        category_id: int,
        commands_channel_id: int,
        max_members: int,
        log_channel_id: Optional[int] = None,
        *,
        default_group_duration: Optional[int] = None,
        default_pomodoro_duration: Optional[int] = None,
    ) -> None:
        for name, duration in (
            ("default_group_duration", default_group_duration),
            ("default_pomodoro_duration", default_pomodoro_duration),
        ):
            if duration is None:
                continue
            if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
                raise ValueError(f"{name} must be a positive integer number of seconds")
            try:
                datetime.now(timezone.utc) + timedelta(seconds=duration)
            except OverflowError as exc:
                raise ValueError(f"{name} exceeds the supported date range") from exc
        async with self.lock:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO guild_settings (
                        guild_id, group_category_id, commands_channel_id, default_max_members,
                        mod_log_channel_id, default_group_duration, default_pomodoro_duration
                    ) VALUES (?, ?, ?, ?, ?, COALESCE(?, 86400), COALESCE(?, 86400))
                    ON CONFLICT(guild_id) DO UPDATE SET
                        group_category_id = excluded.group_category_id,
                        commands_channel_id = excluded.commands_channel_id,
                        default_max_members = excluded.default_max_members,
                        mod_log_channel_id = COALESCE(excluded.mod_log_channel_id, guild_settings.mod_log_channel_id),
                        default_group_duration = COALESCE(?, guild_settings.default_group_duration),
                        default_pomodoro_duration = COALESCE(?, guild_settings.default_pomodoro_duration)
                    """,
                    (
                        guild_id,
                        category_id,
                        commands_channel_id,
                        max_members,
                        log_channel_id,
                        default_group_duration,
                        default_pomodoro_duration,
                        default_group_duration,
                        default_pomodoro_duration,
                    ),
                )

    # TODO: saving pomodoro sessions
    async def save_pomodoro_session(self, session) -> None:
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            INSERT INTO pomodoro_sessions (
                group_id, start_time, end_time, focus_duration, short_break_duration, long_break_duration
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    session["group_id"],
                    session["start_time"],
                    session["end_time"],
                    session["focus_duration"],
                    session["short_break_duration"],
                    session["long_break_duration"],
                ),
            )
            self.conn.commit()
            logger.info(f"pomodoro session for {session['group_id']} save")

    ### --- STUDY GROUP DB OPERATIONS --- ###

    ### Save Study Group
    async def save_study_group(self, study_group_data: Dict[str, Any]) -> None:
        """Insert a new study group into the database."""
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(study_groups)")
            has_max_size = any(column[1] == "max_size" for column in cursor.fetchall())
            query = """
            INSERT INTO study_groups (
                guild_id, name, group_id, creator_id, owner_id, category_id,
                max_members, group_role_id, vc_id, text_id, info_embed_id,
                speak_enabled, video_mode, video_timer,
                start_time, end_time, duration, active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(group_id) DO NOTHING
            """
            values: tuple[Any, ...] = (
                study_group_data["guild_id"],
                study_group_data["name"],
                study_group_data["group_id"],
                study_group_data["creator_id"],
                study_group_data.get("owner_id", study_group_data["creator_id"]),
                study_group_data.get("category_id", 0),
                study_group_data.get("max_members", 10),
                study_group_data.get("group_role_id", 0),
                study_group_data.get("vc_id", 0),
                study_group_data.get("text_id", 0),
                study_group_data.get("info_embed_id", 0),
                study_group_data.get("speak_enabled", 1),
                study_group_data.get("video_mode", "off"),
                study_group_data.get("video_timer", 10),
                study_group_data.get("start_time", 0.0),
                study_group_data.get("end_time", 0.0),
                study_group_data.get("duration", 0),
                study_group_data.get("active", 1),
            )
            if has_max_size:
                query = """
                INSERT INTO study_groups (
                    guild_id, name, group_id, creator_id, owner_id, category_id,
                    max_members, group_role_id, vc_id, text_id, info_embed_id,
                    speak_enabled, video_mode, video_timer,
                    start_time, end_time, duration, active, max_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_id) DO NOTHING
                """
                values = (*values, study_group_data.get("max_members", 10))
            cursor.execute(query, values)
            cursor.execute(
                """
                UPDATE study_groups SET guild_id = ?, name = ?, creator_id = ?, owner_id = ?, category_id = ?,
                    max_members = ?, group_role_id = ?, vc_id = ?, text_id = ?, info_embed_id = ?,
                    speak_enabled = ?, video_mode = ?, video_timer = ?, start_time = ?, end_time = ?, duration = ?, active = ?
                WHERE group_id = ?
                """,
                (*values[:2], *values[3:18], study_group_data["group_id"]),
            )
            if has_max_size:
                cursor.execute(
                    "UPDATE study_groups SET max_size = max_members WHERE group_id = ?", (study_group_data["group_id"],)
                )
            member_ids = set(study_group_data.get("member_ids", []))
            member_ids.add(study_group_data["creator_id"])
            cursor.executemany(
                "INSERT OR IGNORE INTO study_groups_members (group_id, user_id) VALUES (?, ?)",
                [(study_group_data["group_id"], member_id) for member_id in member_ids],
            )
            self.conn.commit()
            logger.info(f"Study group '{study_group_data['name']}' created with ID {study_group_data['group_id']}")

    ### Update Study Group
    async def update_study_group_by_id(self, study_group_data: Dict[str, Any]) -> None:
        # List of fields to update dynamically
        fields_to_update = []
        values = []

        # Append fields only if they are present in the passed data
        if "name" in study_group_data:
            fields_to_update.append("name = ?")
            values.append(study_group_data["name"])

        if "owner_id" in study_group_data:
            fields_to_update.append("owner_id = ?")
            values.append(study_group_data["owner_id"])

        if "category_id" in study_group_data:
            fields_to_update.append("category_id = ?")
            values.append(study_group_data["category_id"])

        if "max_members" in study_group_data:
            fields_to_update.append("max_members = ?")
            values.append(study_group_data["max_members"])

        if "group_role_id" in study_group_data:
            fields_to_update.append("group_role_id = ?")
            values.append(study_group_data["group_role_id"])

        if "text_id" in study_group_data:
            fields_to_update.append("text_id = ?")
            values.append(study_group_data["text_id"])

        if "info_embed_id" in study_group_data:
            fields_to_update.append("info_embed_id = ?")
            values.append(study_group_data["info_embed_id"])

        if "vc_id" in study_group_data:
            fields_to_update.append("vc_id = ?")
            values.append(study_group_data["vc_id"])

        if "start_time" in study_group_data:
            fields_to_update.append("start_time = ?")
            values.append(study_group_data["start_time"])

        if "duration" in study_group_data:
            fields_to_update.append("duration = ?")
            values.append(study_group_data["duration"])

        if "end_time" in study_group_data:
            fields_to_update.append("end_time = ?")
            values.append(study_group_data["end_time"])

        if "speak_enabled" in study_group_data:
            fields_to_update.append("speak_enabled = ?")
            values.append(study_group_data["speak_enabled"])

        if "video_mode" in study_group_data:
            fields_to_update.append("video_mode = ?")
            values.append(study_group_data["video_mode"])

        if "video_timer" in study_group_data:
            fields_to_update.append("video_timer = ?")
            values.append(study_group_data["video_timer"])

        if "active" in study_group_data:
            fields_to_update.append("active = ?")
            values.append(study_group_data["active"])

        # If no fields are present to update, return early
        if not fields_to_update:
            logger.warning("No fields to update for the study group.")
            return

        # Ensure that the group_id is always added as the last value for the WHERE clause
        values.append(study_group_data["group_id"])

        # Construct the SQL query dynamically based on the fields to update
        query = f"UPDATE study_groups SET {', '.join(fields_to_update)} WHERE group_id = ?"

        # Execute the dynamically generated query
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(query, values)
            self.conn.commit()

        logger.info(f"StudyGroup '{study_group_data.get('name', 'Unknown')}' updated in the database.")

    async def get_user_group(self, user_id, channel_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT study_groups.*
                FROM study_groups
                JOIN study_groups_members ON study_groups.group_id = study_groups_members.group_id
                WHERE study_groups_members.user_id = ? AND (study_groups.text_id = ? OR study_groups.vc_id = ? OR ? IS NULL)
                AND study_groups.active = 1
                ORDER BY study_groups.id DESC
                LIMIT 1
            """,
                (user_id, channel_id, channel_id, channel_id),
            )
            group = cursor.fetchone()
            if not group:
                cursor.execute(
                    """
                    SELECT study_groups.*
                    FROM study_groups
                    JOIN study_groups_members ON study_groups.group_id = study_groups_members.group_id
                    WHERE study_groups_members.user_id = ? AND study_groups.active = 1
                    ORDER BY study_groups.id DESC
                    LIMIT 1
                """,
                    (user_id,),
                )
                group = cursor.fetchone()
            logger.debug(f"Retrieved group for user {user_id}: {'Found' if group else 'Not found'}")
            return dict(group) if group else None

    async def get_study_group_by_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Fetch active study group matching text_id or vc_id."""
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM study_groups
                WHERE (text_id = ? OR vc_id = ?) AND active = 1
                ORDER BY id DESC
                LIMIT 1
            """,
                (channel_id, channel_id),
            )
            group = cursor.fetchone()
            logger.debug(f"Retrieved study group for channel {channel_id}: {'Found' if group else 'Not found'}")
            return dict(group) if group else None

    ### Fetch Study Group by NAME (and GUILD ID)
    async def fetch_study_group_by_name(self, name: str, guild_id: str) -> Optional[Dict[str, Any]]:
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM study_groups WHERE LOWER(name) = LOWER(?) AND guild_id = ? AND active = 1 ORDER BY id DESC LIMIT 1",
                (name, guild_id),
            )
            study_group_db = cursor.fetchone()
            logger.debug(
                f"Retrieved study group by name '{name}' for guild {guild_id}: {'Found' if study_group_db else 'Not found'}"
            )
            return dict(study_group_db) if study_group_db else None

    ### Fetch Study Group by GROUP ID or numeric ID
    async def fetch_study_group_by_id(self, group_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM study_groups WHERE group_id = ? OR id = ?",
                (
                    str(group_id),
                    (
                        group_id
                        if isinstance(group_id, int) or (isinstance(group_id, str) and group_id.isdigit())
                        else -1
                    ),
                ),
            )
            group = cursor.fetchone()
            if group:
                logger.debug(f"Fetched StudyGroup {group_id}: Found.")
                return dict(group)
            else:
                logger.debug(f"Fetched StudyGroup {group_id}: Not found.")
                return None

    ### Add Member to Study Group by Group ID
    async def add_member_to_study_group_db(self, group_id: str, user_id: int) -> bool:
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            INSERT OR IGNORE INTO study_groups_members (group_id, user_id)
            SELECT group_id, ? FROM study_groups
            WHERE group_id = ? AND active = 1
              AND (SELECT COUNT(*) FROM study_groups_members WHERE group_id = ?) < max_members
            """,
                (user_id, group_id, group_id),
            )
            self.conn.commit()
            added = cursor.rowcount > 0
            logger.info("Group membership admission group_id=%s user_id=%s added=%s", group_id, user_id, added)
            return added

    ### Remove Member from Study Group by Group ID
    async def remove_member_from_study_group_db(self, group_id: str, user_id: int) -> None:
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            DELETE FROM study_groups_members WHERE group_id = ? AND user_id = ?
            """,
                (group_id, user_id),
            )
            self.conn.commit()
            logger.info(f"Removed member {user_id} from StudyGroup {group_id}.")

    ### Transfer Study Group Ownership, using Group ID
    async def transfer_ownership_study_group_db(self, group_id: str, new_owner_id: int) -> None:
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            UPDATE study_groups SET owner_id = ? WHERE group_id = ?
            """,
                (new_owner_id, group_id),
            )
            self.conn.commit()
            logger.info(f"Ownership of StudyGroup {group_id} transferred to {new_owner_id}.")

    ### Fetch Study Group Members from Group ID
    async def fetch_members_of_group(self, group_id: str) -> List[int]:
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT user_id FROM study_groups_members WHERE group_id = ?",
                (group_id,),
            )
            members_ids = [row["user_id"] for row in cursor.fetchall()]
            logger.debug(f"Fetched {len(members_ids)} members for StudyGroup {group_id}.")
            return members_ids

    ### Fetch Owner of Group by Group ID
    async def fetch_owner_of_group(self, group_id: str) -> Optional[int]:
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT owner_id FROM study_groups WHERE group_id = ?", (group_id,))
            owner = cursor.fetchone()
            logger.debug(f"Fetched owner for Study Group {group_id}: {owner['owner_id'] if owner else 'Not found'}.")
            return owner["owner_id"] if owner else None

    ### Delete Study Group
    async def delete_study_group(self, group_id: Union[int, str]):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE study_groups SET active = 0 WHERE id = ? OR group_id = ?",
                (
                    (
                        group_id
                        if isinstance(group_id, int) or (isinstance(group_id, str) and group_id.isdigit())
                        else -1
                    ),
                    str(group_id),
                ),
            )
            cursor.execute("DELETE FROM study_groups_members WHERE group_id = ?", (str(group_id),))
            self.conn.commit()
            logger.info("Study group marked inactive group_id=%s", group_id)

    ### Get Groups the User is in (Fetches multiple groups per user)
    async def get_study_groups_of_user(self, user_id: int, guild_id: int):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT study_groups.*
                FROM study_groups
                JOIN study_groups_members ON study_groups.group_id = study_groups_members.group_id
                WHERE study_groups_members.user_id = ? AND study_groups.guild_id = ? AND study_groups.active = 1
            """,
                (user_id, guild_id),
            )
            groups = cursor.fetchall()  # Fetch all groups within the guild
            logger.debug("Retrieved study groups user_id=%s guild_id=%s count=%s", user_id, guild_id, len(groups))
            return [dict(group) for group in groups]

    ### Get All Groups in the Guild
    async def get_all_study_groups_of_guild(self, guild_id: int):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM study_groups WHERE guild_id = ? AND active = 1", (guild_id,))
            groups = cursor.fetchall()
            logger.debug(f"Retrieved {len(groups)} study groups for guild {guild_id}")
            return [dict(group) for group in groups]

    async def get_guild_group_names(self, guild_id: int) -> list[str]:
        """Return active and retired group names for guild-local name allocation."""
        async with self.lock:
            rows = self.conn.execute(
                "SELECT name FROM study_groups WHERE guild_id = ? ORDER BY id", (guild_id,)
            ).fetchall()
            return [row[0] for row in rows]

    async def get_all_study_groups(self, guild_id: int):
        """Alias for get_all_study_groups_of_guild."""
        return await self.get_all_study_groups_of_guild(guild_id)

    ### --- CHECKIN SESSION DB OPERATIONS --- ###

    ## Save Check-in Session
    async def save_checkin_session(self, session_data: Dict[str, Any]) -> None:
        """Insert a new check-in session into the database."""
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            INSERT INTO checkin_sessions (
                session_id, guild_id, name, creator_id, owner_id, text_id,
                duration, start_time, last_reminder_time, next_reminder_time, reminder_count, last_reminder_message_id, active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_data["session_id"],
                    session_data["guild_id"],
                    session_data["name"],
                    session_data["creator_id"],
                    session_data["owner_id"],
                    session_data["text_id"],
                    session_data["duration"],
                    session_data["start_time"],
                    session_data["last_reminder_time"],
                    session_data["next_reminder_time"],
                    session_data["reminder_count"],
                    session_data["last_reminder_message_id"],
                    session_data["active"],
                ),
            )
            self.conn.commit()
            logger.info(f"Check-in session '{session_data['name']}' created with ID {session_data['session_id']}.")

    ## Update Check-in Session
    async def update_checkin_session(self, session_data: Dict[str, Any]) -> None:
        """Update an existing check-in session in the database by session ID."""
        async with self.lock:
            cursor = self.conn.cursor()
            update_fields = []
            update_values = []

            # Dynamically build the query based on which fields are in session_data
            if "last_reminder_time" in session_data:
                update_fields.append("last_reminder_time = ?")
                update_values.append(session_data["last_reminder_time"])

            if "next_reminder_time" in session_data:
                update_fields.append("next_reminder_time = ?")
                update_values.append(session_data["next_reminder_time"])

            if "reminder_count" in session_data:
                update_fields.append("reminder_count = ?")
                update_values.append(session_data["reminder_count"])

            if "last_reminder_message_id" in session_data:
                msg_id = session_data["last_reminder_message_id"]
                clean_msg_id = (
                    int(msg_id) if isinstance(msg_id, int) or (isinstance(msg_id, str) and msg_id.isdigit()) else None
                )
                update_fields.append("last_reminder_message_id = ?")
                update_values.append(clean_msg_id)

            if "active" in session_data:
                update_fields.append("active = ?")
                update_values.append(session_data["active"])

            # Ensure that we're updating only the necessary fields
            if update_fields:
                update_values.append(session_data["session_id"])  # Add session_id for the WHERE clause
                query = f"UPDATE checkin_sessions SET {', '.join(update_fields)} WHERE session_id = ?"
                cursor.execute(query, update_values)
                self.conn.commit()

            logger.info(f"Check-in session '{session_data['session_id']}' updated in the database.")

    ## Fetch Check-in Session by Session ID
    async def fetch_checkin_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a check-in session from the database by session ID."""
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM checkin_sessions WHERE session_id = ?", (session_id,))
            session = cursor.fetchone()
            logger.debug(f"Fetched check-in session {session_id}: {'Found' if session else 'Not found'}.")
            return dict(session) if session else None

    ## Add or Update Check-in Member
    async def add_or_update_checkin_member(
        self, session_id: str, member_id: int, status: Any, absences: int = 0
    ) -> None:
        """Insert or update a member's status in a check-in session."""
        async with self.lock:
            cursor = self.conn.cursor()
            status_val = status.value if hasattr(status, "value") else str(status)
            cursor.execute(
                """
            INSERT INTO checkin_members (session_id, member_id, status, absences)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id, member_id) DO UPDATE SET
                status = excluded.status,
                absences = excluded.absences
            """,
                (session_id, member_id, status_val, absences),
            )
            self.conn.commit()
            logger.info(
                f"Updated member {member_id} in check-in session {session_id} with status '{status_val}' and absences {absences}."
            )

    ## Fetch Check-in Members by Session ID
    async def fetch_checkin_members(self, session_id: str) -> List[Dict[str, Any]]:
        """Fetch all members in a check-in session."""
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM checkin_members WHERE session_id = ?", (session_id,))
            members = cursor.fetchall()
            logger.debug(f"Fetched {len(members)} members for check-in session {session_id}.")
            return [dict(member) for member in members]

    ## Fetch Active Check-in Sessions
    async def fetch_active_checkin_sessions(self) -> List[Dict[str, Any]]:
        """
        Fetch all active check-in sessions from the database.
        Returns a list of active sessions with all relevant session data.
        """
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM checkin_sessions WHERE active = 1")
            sessions = cursor.fetchall()
            logger.debug(f"Fetched {len(sessions)} active check-in sessions.")
            return [dict(session) for session in sessions]

    ## Delete Check-in Session
    async def delete_checkin_session(self, session_id: str) -> None:
        """Remove a check-in session and its members from the database."""
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM checkin_members WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM checkin_sessions WHERE session_id = ?", (session_id,))
            self.conn.commit()
            logger.info(f"Deleted check-in session with ID: {session_id}.")

    async def get_study_group(self, guild_id: int):
        """Fetch the most recent active study group for a guild."""
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            SELECT * FROM study_groups
            WHERE guild_id = ? AND active = 1
            ORDER BY id DESC
            LIMIT 1
            """,
                (guild_id,),
            )
            group = cursor.fetchone()
            logger.debug(f"Retrieved study group for guild {guild_id}: {'Found' if group else 'Not found'}")
            return dict(group) if group else None

    async def update_group_roles(self, group_id, admin_role_id, session_role_id):
        async with self.lock:
            cursor = self.conn.cursor()
            role_id = session_role_id if session_role_id is not None else admin_role_id
            cursor.execute(
                """
            UPDATE study_groups
            SET group_role_id = ?
            WHERE id = ? OR group_id = ?
            """,
                (role_id or 0, group_id, str(group_id)),
            )
            self.conn.commit()
            logger.info(f"Updated roles for group {group_id}: group_role_id={role_id}")

    async def get_group_roles(self, group_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT group_role_id FROM study_groups WHERE id = ? OR group_id = ?",
                (group_id, str(group_id)),
            )
            role = cursor.fetchone()
            role_id = role["group_role_id"] if role else None
            logger.debug(f"Retrieved roles for group {group_id}: {role_id}")
            return (role_id, role_id)

    async def update_voice_channel(self, group_id, voice_channel_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            UPDATE study_groups
            SET vc_id = ?
            WHERE id = ? OR group_id = ?
            """,
                (voice_channel_id or 0, group_id, str(group_id)),
            )
            self.conn.commit()
            logger.info(f"Updated voice channel for group {group_id}: vc_id={voice_channel_id}")

    async def log_vc_creation(self, group_id, channel_id, creator_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            INSERT INTO voice_channel_logs (group_id, channel_id, creator_id, create_time)
            VALUES (?, ?, ?, ?)
            """,
                (group_id, channel_id, creator_id, datetime.now()),
            )
            self.conn.commit()
            logger.info(f"Logged voice channel creation: group={group_id}, channel={channel_id}, creator={creator_id}")

    async def get_vc_logs(self, guild_id, start_date):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            SELECT channel_id, voice_channel_logs.creator_id, create_time FROM voice_channel_logs
            JOIN study_groups ON voice_channel_logs.group_id = study_groups.id
            WHERE study_groups.guild_id = ? AND create_time >= ?
            """,
                (guild_id, start_date),
            )
            logs = cursor.fetchall()
            logger.debug(f"Retrieved {len(logs)} VC logs for guild {guild_id} since {start_date}")
            return logs

    async def update_vc_cleanup_time(self, guild_id, cleanup_time):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            INSERT INTO guild_settings (guild_id, vc_cleanup_time)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET vc_cleanup_time = excluded.vc_cleanup_time
            """,
                (guild_id, cleanup_time),
            )
            self.conn.commit()
            logger.info(f"Updated VC cleanup time for guild {guild_id}: {cleanup_time} seconds")

    async def get_vc_cleanup_time(self, guild_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT vc_cleanup_time FROM guild_settings WHERE guild_id = ?",
                (guild_id,),
            )
            result = cursor.fetchone()
            cleanup_time = result["vc_cleanup_time"] if result else 600
            logger.debug(f"Retrieved VC cleanup time for guild {guild_id}: {cleanup_time} seconds")
            return cleanup_time

    async def update_vc_category(self, guild_id, category_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            INSERT INTO guild_settings (guild_id, vc_category_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET vc_category_id = excluded.vc_category_id
            """,
                (guild_id, category_id),
            )
            self.conn.commit()
            logger.info(f"Updated VC category for guild {guild_id}: category_id={category_id}")

    async def get_vc_category(self, guild_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT vc_category_id FROM guild_settings WHERE guild_id = ?",
                (guild_id,),
            )
            result = cursor.fetchone()
            category_id = result["vc_category_id"] if result else None
            logger.debug(f"Retrieved VC category for guild {guild_id}: {category_id}")
            return category_id

    async def update_group_category(self, guild_id, category_id):
        async with self.lock:
            cursor = self.conn.cursor()
            # Insert or update group_category_id without affecting other columns
            cursor.execute(
                """
            INSERT INTO guild_settings (guild_id, group_category_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET group_category_id=excluded.group_category_id
            """,
                (guild_id, category_id),
            )
            self.conn.commit()
            logger.info(f"Updated group category for guild {guild_id}: category_id={category_id}")

    async def get_group_category(self, guild_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT group_category_id FROM guild_settings WHERE guild_id = ?",
                (guild_id,),
            )
            result = cursor.fetchone()
            category_id = result["group_category_id"] if result else None
            logger.debug(f"Retrieved group category for guild {guild_id}: {category_id}")
            return category_id

    async def update_default_max_members(self, guild_id, max_members):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            INSERT INTO guild_settings (guild_id, default_max_members)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET default_max_members=excluded.default_max_members
            """,
                (guild_id, max_members),
            )
            self.conn.commit()
            logger.info(f"Updated default_max_members for guild {guild_id}: {max_members}")

    async def get_default_max_members(self, guild_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT default_max_members FROM guild_settings WHERE guild_id = ?",
                (guild_id,),
            )
            result = cursor.fetchone()
            max_members = result["default_max_members"] if (result and "default_max_members" in result.keys()) else 10
            return max_members if max_members is not None else 10

    async def add_manager(self, user_id, guild_id, permission_level, *, grant_source="explicit"):
        if grant_source not in ("explicit", "server_sync"):
            raise ValueError("grant_source must be explicit or server_sync")
        level_val = permission_level.value if hasattr(permission_level, "value") else int(permission_level)
        if level_val == 2:
            level_val = 3
        async with self.lock:
            cursor = self.conn.cursor()
            with self.conn:
                existing = cursor.execute(
                    "SELECT grant_source FROM managers WHERE user_id = ? AND guild_id IS ?",
                    (user_id, guild_id),
                ).fetchone()
                if existing and not (grant_source == "server_sync" and existing[0] == "explicit"):
                    cursor.execute(
                        "UPDATE managers SET permission_level = ?, grant_source = ? "
                        "WHERE user_id = ? AND guild_id IS ?",
                        (level_val, grant_source, user_id, guild_id),
                    )
                elif not existing:
                    cursor.execute(
                        "INSERT INTO managers (user_id, guild_id, permission_level, grant_source) VALUES (?, ?, ?, ?)",
                        (user_id, guild_id, level_val, grant_source),
                    )
            logger.info(
                "Manager grant saved: user_id=%s guild_id=%s permission_level=%s grant_source=%s",
                user_id,
                guild_id,
                level_val,
                grant_source,
            )

    async def sync_guild_manager_grants(self, guild_id: int, grants: Mapping[int, int]) -> None:
        """Replace a guild's native staff grants while retaining explicit grants."""
        levels = {int(user_id): int(level) for user_id, level in grants.items()}
        if any(level not in (2, 3) for level in levels.values()):
            raise ValueError("server-synced manager levels must be 2 or 3")
        levels = {user_id: 3 for user_id in levels}
        async with self.lock:
            with self.conn:
                current = self.conn.execute(
                    "SELECT user_id FROM managers WHERE guild_id = ? AND grant_source = ?",
                    (guild_id, "server_sync"),
                ).fetchall()
                for row in current:
                    if row[0] not in levels:
                        self.conn.execute(
                            "DELETE FROM managers WHERE guild_id = ? AND user_id = ? AND grant_source = ?",
                            (guild_id, row[0], "server_sync"),
                        )
                for user_id, level in levels.items():
                    existing = self.conn.execute(
                        "SELECT grant_source FROM managers WHERE guild_id = ? AND user_id = ?",
                        (guild_id, user_id),
                    ).fetchone()
                    if existing and existing[0] == "explicit":
                        continue
                    if existing:
                        self.conn.execute(
                            "UPDATE managers SET permission_level = ? WHERE guild_id = ? AND user_id = ?",
                            (level, guild_id, user_id),
                        )
                    else:
                        self.conn.execute(
                            "INSERT INTO managers (user_id, guild_id, permission_level, grant_source) "
                            "VALUES (?, ?, ?, ?)",
                            (user_id, guild_id, level, "server_sync"),
                        )
        logger.info("Synchronized server staff grants: guild_id=%s count=%s", guild_id, len(levels))

    async def remove_manager(self, user_id, guild_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "DELETE FROM managers WHERE user_id = ? AND guild_id IS ?",
                (user_id, guild_id),
            )
            self.conn.commit()
            logger.info(f"Removed manager: user={user_id}, guild={guild_id}")

    async def get_manager(self, user_id, guild_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM managers WHERE user_id = ? AND "
                "(guild_id = ? OR (guild_id IS NULL AND permission_level = 4)) "
                "ORDER BY permission_level DESC, guild_id IS NULL ASC LIMIT 1",
                (user_id, guild_id),
            )
            manager = cursor.fetchone()
            logger.debug(
                f"Retrieved manager info for user {user_id} in guild {guild_id}: {'Found' if manager else 'Not found'}"
            )
            return manager

    async def get_all_managers(self, guild_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM managers WHERE guild_id = ? OR (guild_id IS NULL AND permission_level = 4) "
                "ORDER BY permission_level DESC, user_id",
                (guild_id,),
            )
            managers = cursor.fetchall()
            logger.debug(f"Retrieved {len(managers)} managers for guild {guild_id}")
            return managers

    async def add_task(self, user_id, description, group_id=None, guild_id=None):
        import secrets
        import string

        async with self.lock:
            cursor = self.conn.cursor()

            # If guild_id not provided, try to find it from group_id
            if group_id and not guild_id:
                cursor.execute(
                    "SELECT guild_id FROM study_groups WHERE group_id = ? OR CAST(id AS TEXT) = ? LIMIT 1",
                    (str(group_id), str(group_id)),
                )
                row = cursor.fetchone()
                if row:
                    guild_id = row[0]

            # Generate a unique 4-character ID
            while True:
                new_id = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
                cursor.execute("SELECT 1 FROM tasks WHERE task_id_str = ?", (new_id,))
                if not cursor.fetchone():
                    break

            cursor.execute(
                """
            INSERT INTO tasks (user_id, description, group_id, task_id_str, guild_id)
            VALUES (?, ?, ?, ?, ?)
            """,
                (user_id, description, str(group_id) if group_id else None, new_id, guild_id),
            )
            self.conn.commit()
            logger.info(
                f"Added task for user {user_id}: ID={new_id}, group={group_id}, guild={guild_id}, description='{description}'"
            )
            return new_id

    async def complete_task(self, user_id, task_id, group_id=None):
        async with self.lock:
            cursor = self.conn.cursor()
            if group_id:
                cursor.execute(
                    """
                UPDATE tasks SET completed = 1
                WHERE (task_id_str = ? OR id = ? OR task_number = ?) AND user_id = ? AND group_id = ?
                """,
                    (
                        str(task_id),
                        (task_id if isinstance(task_id, int) or str(task_id).isdigit() else -1),
                        (task_id if isinstance(task_id, int) or str(task_id).isdigit() else -1),
                        user_id,
                        str(group_id),
                    ),
                )
            else:
                cursor.execute(
                    """
                UPDATE tasks SET completed = 1
                WHERE (task_id_str = ? OR id = ? OR task_number = ?) AND user_id = ?
                """,
                    (
                        str(task_id),
                        (task_id if isinstance(task_id, int) or str(task_id).isdigit() else -1),
                        (task_id if isinstance(task_id, int) or str(task_id).isdigit() else -1),
                        user_id,
                    ),
                )
            self.conn.commit()
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Marked task {task_id} as completed for user {user_id}")
            else:
                logger.warning(f"Failed to complete task {task_id} for user {user_id} (Not found or unauthorized)")
            return success

    async def apply_task_action(self, user_id: int, task_id: int, group_id: Optional[str], action: str) -> bool:
        if action == "complete":
            query = "UPDATE tasks SET completed = 1 WHERE id = ? AND user_id = ? AND group_id IS ? AND completed = 0"
        elif action == "delete":
            query = "DELETE FROM tasks WHERE id = ? AND user_id = ? AND group_id IS ?"
        else:
            raise ValueError("Unknown task action")
        async with self.lock:
            cursor = self.conn.execute(query, (task_id, user_id, group_id))
            self.conn.commit()
            return cursor.rowcount > 0

    async def get_user_tasks(self, user_id, group_id=None, global_only=False, guild_id=None):
        async with self.lock:
            cursor = self.conn.cursor()
            if group_id:
                cursor.execute(
                    "SELECT * FROM tasks WHERE user_id = ? AND group_id = ? ORDER BY id ASC",
                    (user_id, str(group_id)),
                )
            elif guild_id is not None:
                cursor.execute(
                    "SELECT * FROM tasks WHERE user_id = ? AND guild_id = ? ORDER BY id ASC",
                    (user_id, guild_id),
                )
            elif global_only:
                cursor.execute(
                    "SELECT * FROM tasks WHERE user_id = ? AND group_id IS NULL AND guild_id IS NULL ORDER BY id ASC",
                    (user_id,),
                )
            else:
                cursor.execute("SELECT * FROM tasks WHERE user_id = ? ORDER BY id ASC", (user_id,))
            tasks = cursor.fetchall()
            logger.debug(f"Retrieved {len(tasks)} tasks for user {user_id}")
            return tasks

    async def delete_task(self, user_id, task_id, group_id=None):
        async with self.lock:
            cursor = self.conn.cursor()
            if group_id:
                cursor.execute(
                    """
                DELETE FROM tasks
                WHERE (task_id_str = ? OR id = ? OR task_number = ?) AND user_id = ? AND group_id = ?
                """,
                    (
                        str(task_id),
                        (task_id if isinstance(task_id, int) or str(task_id).isdigit() else -1),
                        (task_id if isinstance(task_id, int) or str(task_id).isdigit() else -1),
                        user_id,
                        str(group_id),
                    ),
                )
            else:
                cursor.execute(
                    """
                DELETE FROM tasks
                WHERE (task_id_str = ? OR id = ? OR task_number = ?) AND user_id = ?
                """,
                    (
                        str(task_id),
                        (task_id if isinstance(task_id, int) or str(task_id).isdigit() else -1),
                        (task_id if isinstance(task_id, int) or str(task_id).isdigit() else -1),
                        user_id,
                    ),
                )
            self.conn.commit()
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Deleted task {task_id} for user {user_id}")
            else:
                logger.warning(f"Failed to delete task {task_id} for user {user_id}")
            return success

    async def purge_group_tasks(self, user_id, group_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            DELETE FROM tasks
            WHERE user_id = ? AND group_id = ?
            """,
                (user_id, str(group_id)),
            )
            self.conn.commit()
            count = cursor.rowcount
            logger.info(f"Purged {count} tasks for user {user_id} in group {group_id}")
            return count

    async def purge_guild_tasks(self, user_id, guild_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            DELETE FROM tasks
            WHERE user_id = ? AND guild_id = ?
            """,
                (user_id, guild_id),
            )
            self.conn.commit()
            count = cursor.rowcount
            logger.info(f"Purged {count} tasks for user {user_id} in guild {guild_id}")
            return count

    async def purge_all_user_tasks(self, user_id):
        async with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
            DELETE FROM tasks
            WHERE user_id = ?
            """,
                (user_id,),
            )
            self.conn.commit()
            count = cursor.rowcount
            logger.info(f"Purged {count} tasks globally for user {user_id}")
            return count
