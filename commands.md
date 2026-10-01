# Chief Productivity Officer (CPO) Discord Bot Commands

## Study Groups

- `/create_group <mentions> [name] [max_members]`: Create a study group in the configured category.
  - `mentions`: Users or roles to include in the initial roster, alongside the creator.
  - `name`: Optional group name; omitted names are generated.
  - `max_members`: Optional member limit; defaults to the server's `/setup` setting.
  - Posts one dashboard with member mentions, channel links, and controls. The command result is public.

- `/join_group <name>`: Join an existing study group
  - `name`: The name of the study group you want to join
  - Adds you to the specified study group if it exists and isn't full.

- `/leave_group [name]`: Leave the current study group
  - `name`: Optional name; defaults to the current channel's group.
  - Removes you from the specified study group.

- `/end_group [name]`: End a study group (owner, creator, or server manager).
  - `name`: Optional name; defaults to the current channel's group.
  - Cleans up channels, roles, and related sessions, then marks the database record inactive.

- `/purge_groups`: End all active groups in this server (Moderator or higher).
  - Uses persisted records after a restart. If cleanup deletes the invocation channel, the final result is sent by DM.

The dashboard's Speak and Force Video controls change the voice permissions and save the settings. Speak controls microphone access for the channel. Force Video allows camera and screen sharing, warns members after 30 seconds, and disconnects members who still do not enable video after 60 seconds.

- `/transfer_group <new_owner> [group_name]`: Transfer study group ownership
  - `new_owner`: The server member to transfer ownership to
  - `group_name`: (Optional) The name of the study group (defaults to current channel's group)
  - Transfers ownership of the study group, updating database records and role privileges.

- `/list_groups`: List all active study groups in the server
  - Displays a list of all current study groups with their member counts.

- `/invite_to_group <user> [group_name]`: Invite a user to your study group.
  - `group_name`: Optional name; defaults to the current channel's group.
  - Sends a DM with Join and Decline buttons that expire after five minutes. Only the recipient can respond. Joining rechecks group activity and capacity; blocked DMs do not add the recipient.

## Pomodoro

- `/start_pomodoro [focus] [short_break] [long_break]`: Start a Pomodoro session
  - `focus`: (Optional) Duration of focus sessions in minutes (default is 25)
  - `short_break`: (Optional) Duration of short breaks in minutes (default is 5)
  - `long_break`: (Optional) Duration of long breaks in minutes (default is 15)
  - Starts a new Pomodoro session for your study group with the specified durations.

- `/end_pomodoro`: End the current Pomodoro session
  - Stops the ongoing Pomodoro session for your study group.

- `/pause_pomodoro`: Pause the current Pomodoro session
  - Temporarily halts the timer in the ongoing Pomodoro session.

- `/resume_pomodoro`: Resume the paused Pomodoro session
  - Continues the timer from where it was paused in the Pomodoro session.

- `/pomodoro_status`: Check the status of the current Pomodoro session
  - Displays information about the ongoing Pomodoro session, including current stage, time remaining, and completed cycles.

## Voice Channels

- `/create_vc [name]`: Create a voice channel for the study group
  - `name`: (Optional) Custom name for the voice channel
  - Creates a new voice channel for your study group, visible only to group members.

- `/delete_vc`: Delete the voice channel for the study group
  - Removes the voice channel associated with your study group.

- `/delete_role <role>`: Delete the selected role for the study group (Manage Roles permission required)
  - `role`: The group role to delete and unassign.

- `/delete_text_channel <text_channel>`: Delete the selected text channel for the study group (Manage Channels permission required)
  - `text_channel`: The group text channel to delete.

## Task List

- `/task_add <description>`: Add a new task to your list
  - `description`: The description of the task
  - Adds a new task to your personal task list, scoped to the current server (and study group if invoked within one).

- `/task_complete [task_ids]`: Complete tasks by comma-separated IDs or numbers. Omit IDs to use a Select menu.
  - Inside a study group, choices and operations are scoped to that group. Only the task owner can use the menu.

- `/task_delete [task_ids]`: Delete tasks by comma-separated IDs or numbers. Omit IDs to use the same owner-checked menu.

- `/task_list [all_groups]`: List tasks, including completed ones, with 15 tasks per page.
  - By default, tasks are scoped to the current server and active group (or global server tasks outside groups). Set `all_groups:True` to list all tasks across groups.
  - Note: `all_groups:True` results are always sent ephemerally to prevent channel clutter.

- `/task_purge [all_tasks]`: Delete your tasks in the current group with one database operation.
  - Set `all_tasks:True` to delete your tasks across every group in this server and global scope.
  - Also checks the latest 100 messages in the current text channel and removes matching bot task messages attributed to you. Cleanup failure is reported after the task records are deleted.

Task command results follow category-based visibility and work in DMs. Menus show up to 25 choices; use typed IDs for additional tasks. Menu actions use the database row ID internally to avoid ambiguous legacy task numbers.

## Productivity

- `/productivity`: Display your personal productivity metrics
  - Returns an embed showing total tasks completed, total time spent, and efficiency score (tasks completed per hour).

## Check-in

- `/checkin <duration> <mentions>`: Start a check-in session
  - `duration`: The duration of the check-in session (e.g., "30m" for 30 minutes)
  - `mentions`: Users or roles to include in the check-in session
  - Starts a new check-in session with specified duration and participants.

- `/settings_checkin [max_absences] [warning_threshold]`: Configure check-in settings for this server (Manager only)
  - `max_absences`: Number of consecutive unacknowledged pings before taking action.
  - `warning_threshold`: Absence count triggering a warning alert.

## Management & Authorization

### Authorization Tiers
- **Admin Tier** (Permission Level 3-4): Server Owner, Server Administrators (`administrator=True`), Bot Developers. Admin commands are invisible to non-admins in Discord's slash command picker.
- **Mod Tier** (Permission Level 2): Moderators with `manage_guild`, `manage_channels`, `manage_roles`, `moderate_members`, `kick_members`, `ban_members`, staff roles, or registered in DB.
- **User Tier** (Permission Level 0-1): Baseline server members and study group participants.

### Management Commands

- `/setup [max_members] [category]`: View or update server-wide study group defaults (Manage Server permission required)
  - `max_members`: Optional default member limit for new groups (1–50).
  - `category`: Optional category for new study group channels.
- `/set_group_category <category>`: Set the category used by `/create_group` (Moderator or higher).
- `/set_mod_log_channel [channel]`: Save a channel for group creation, ending, and purge event embeds (server manager).
  - Omit `channel` to disable logging. Event embeds identify the group and actor without sending mentions. Missing channels or Discord send failures are logged locally.
- `/sync_commands [guild_only: bool = False]`: Synchronize application slash commands with Discord (Administrator only, invisible to non-admins)
  - `guild_only`: When `True`, synchronizes slash commands to the current server; when `False`, syncs globally.

- `/user_level [user: Optional[discord.Member]]`: Check the authorization level and tier of any member (Visible to all)
  - `user`: Optional member to inspect (defaults to yourself). Returns an embed displaying the user's High-Level Tier (`Admin`, `Mod`, `User`) and numeric permission level.

- `/add_bot_developer <user>`: Add a bot developer (Bot Developer only, Admin permission required)
  - `user`: The user to promote to bot developer.

- `/add_guild_manager <user>`: Add a guild manager (Admin only)
  - `user`: The user to promote to administrator/manager.

- `/remove_guild_manager <user>`: Remove a guild manager (Admin only)
  - `user`: The user to demote from manager status.

- `/list_managers`: List all managers and staff for this server (Moderator / Admin permission required)
  - Displays all staff members, moderators, administrators, and bot developers.

- `/set_permission_level <user> <level>`: Set the permission level for a user (Bot Developer only)
  - `user`: The user to set permissions for.
  - `level`: The level to assign (0: User, 1: Member, 2: Mod, 3: Admin, 4: Dev).

- `/sync_managers`: Synchronize server owner and moderators (Admin only)
  - Scans the guild and registers the server owner & administrators as `ADMIN` (Level 3) and moderators/staff as `MODERATOR` (Level 2).

Note: All commands use slash command syntax (`/`). Commands requiring elevated permissions use Discord's native `default_permissions` to remain hidden from unauthorized members in the Discord client interface.

### Response Visibility & Privacy Rules

- **Category-Based Contextual Visibility**: Commands invoked inside the configured study group category send public responses so group members can collaborate and view session updates in the channel.
- **Outside-Category Ephemeral Fallback**: Commands invoked outside the study group category (such as general channels or DMs) default to ephemeral responses to prevent channel clutter.
- **Strict Privacy for Errors & Cross-Group Lists**: Permission denials, authorization rejections, missing server context, input validation errors, and cross-group task lists (`/task_list all_groups:True`) are strictly sent as ephemeral responses regardless of channel context.

---
