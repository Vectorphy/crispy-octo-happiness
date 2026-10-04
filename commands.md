# Chief Productivity Officer (CPO) Discord Bot Commands

## Study Groups

- `/create_group <mentions> [name] [max_members]`: Create a study group in the configured category.
  - `mentions`: Users or roles to invite by DM. Only the creator joins immediately; invitees choose Join or Decline.
  - `name`: Optional group name. Omitted names use `{user-name}-studysession-{number}`. Duplicate custom names receive suffixes such as `vec-2`.
  - `max_members`: Optional member limit; defaults to the server's `/setup` setting.
  - Posts one dashboard with member mentions, channel links, and controls in the group's text channel. The command acknowledgement follows the response visibility rules below.

- `/join_group <name>`: Join an existing study group
  - `name`: The name of the study group you want to join
  - Adds you to the specified study group if it exists and isn't full.

- `/leave_group [name]`: Leave the current study group
  - `name`: Optional name; defaults to the current channel's group.
  - Removes you from the specified study group.

- `/end_group [name]`: End a study group directly as its current owner or guild staff. Current members send the owner a DM approval request; outsiders cannot request an end.
  - `name`: Optional name; defaults to the current channel's group.
  - Cleans up channels, roles, and related sessions, then marks the database record inactive.

- `/purge_groups`: End all active groups in this server (Moderator or higher).
  - Uses persisted records after a restart. If cleanup deletes the invocation channel, the final result is sent by DM.

The dashboard's Speak and Force Video controls change the voice permissions and save the settings. Speak controls microphone access for the channel. Force Video allows camera and screen sharing, warns members after 30 seconds, and disconnects members who still have neither camera nor screen sharing enabled after 60 seconds.

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

- `/start_pomodoro [focus] [short_break] [long_break] [require_vc]`: Start a Pomodoro session
  - `focus`: (Optional) Duration of focus sessions in minutes (default is 25)
  - `short_break`: (Optional) Duration of short breaks in minutes (default is 5)
  - `long_break`: (Optional) Duration of long breaks in minutes (default is 15)
  - Each stage must be 2–240 minutes. Omitted timings are calculated using the 5:1:3 ratio, with a two-minute minimum. `require_vc: False` enables text-only use. The creator joins automatically; other group members receive DM Join/Decline invitations. Entering voice alone does not start or join a session.
  - The lifetime defaults to 24 hours, or the server setting saved in `/setup`. With one hour left, participants receive a remaining-time message and Renew control. Renew adds 24 hours to the current deadline. Pausing does not stop lifetime expiry. Running Pomodoros do not survive a bot restart.

- `/end_pomodoro`: End the current Pomodoro session
  - The current session owner or guild staff can stop it directly. Participants request the owner's approval by DM; outsiders cannot request an end.

- `/pause_pomodoro`: Pause the current Pomodoro session
  - Temporarily halts the timer in the ongoing Pomodoro session.

- `/resume_pomodoro`: Resume the paused Pomodoro session
  - Continues the timer from where it was paused in the Pomodoro session.

- `/pomodoro_status`: Check the status of the current Pomodoro session
  - Displays information about the ongoing Pomodoro session, including current stage, time remaining, and completed cycles.

## Voice Channels

Group creation provisions text and voice channels with the parent category's permissions. Ending the group handles its channel and role cleanup. Standalone `/create_vc`, `/delete_vc`, `/delete_role`, and `/delete_text_channel` are removed from the public command tree. There is no public `/create_text_channel` command.

The group dashboard retains group controls and Pomodoro/check-in status fields. Check-in Present/Break and Pomodoro Pause/Resume/End buttons belong to the sessions' own controls, rather than the group dashboard.

## Task List

- `/task_add <description>`: Add a new task to your list
  - `description`: The description of the task
  - Adds a new task to your personal task list, scoped to the current server (and study group if invoked within one).

- `/task_complete [task_ids]`: Complete tasks by comma-separated IDs or numbers. Omit IDs to use a Select menu.
  - Inside a study group, choices and operations are scoped to that group. The menu and its acknowledgements are always private, and only the task owner can use it.

- `/task_delete [task_ids]`: Delete tasks by comma-separated IDs or numbers. Omit IDs to use the same owner-checked menu.

- `/task_list [all_groups]`: List tasks, including completed ones, with 15 tasks per page.
  - By default, tasks are scoped to the current server and active group (or global server tasks outside groups). Set `all_groups:True` to list your tasks across all groups and servers.
  - Note: `all_groups:True` results are always sent ephemerally to prevent channel clutter.

- `/task_purge [all_tasks]`: Delete your tasks in the current group with one database operation.
  - Set `all_tasks:True` to delete your tasks across every group and server, including global tasks. Its result is always private.
  - Also checks the latest 100 messages in the current text channel and removes matching bot task messages attributed to you. Cleanup failure is reported after the task records are deleted.

Task command results follow the response visibility rules below and work in DMs. Menus show up to 25 choices; use typed IDs for additional tasks. Menu actions use the database row ID internally to avoid ambiguous legacy task numbers.

## Productivity

- `/productivity`: Display your personal productivity metrics
  - Returns an embed showing completed tasks, time spent, and efficiency score. Task counts use stored tasks, but time spent currently uses a random placeholder value; efficiency is therefore not measured productivity.

## Check-in

- `/checkin <name> <duration> [mentions]`: Start a check-in session.
  - `duration`: Reminder interval from 2 minutes to 4 hours, such as `30m` or `2h`.
  - `mentions`: People or roles to invite by DM. Only the creator joins automatically.
  - Use Join/Present, Break, and Leave to manage participation. Current owners and guild staff can end directly; participants request the current owner's approval by DM.

- `/settings_checkin [max_members] [min_duration] [max_duration] [max_absences] [max_breaks] [max_user_sessions] [permission_mode]`: Configure this server's check-in limits (Manager only).
  - Reminder limits are seconds and must stay within 120–14400. Absences count consecutive unacknowledged reminders.

## Management & Authorization

### Authorization Tiers
- **Level 4 — Bot Developer**: Configured developer or an explicit developer grant; overrides lower levels.
- **Level 3 — Manager / Admin / Mod**: Bot-added grants display Manager. Native/server-synced owners and administrators display Admin; native moderators display Mod. Moderator permissions include `manage_channels`, `manage_roles`, `moderate_members`, `kick_members`, or `ban_members`. Role names alone never grant access.
- **Level 2 — `{group_name} Owner`**: Current owner of the active study group in the invocation channel.
- **Level 1 — `{group_name} Group Member`**: Verified member of that contextual group.
- **Level 0 — Server Member**: Baseline participant.

The highest applicable level wins: 4 > 3 > 2 > 1 > 0. Outside active group channels, `/user_level` reports only server/global authority. Historical manager grants retain explicit provenance; server sync removes stale grants that it created without removing explicit grants.

### Management Commands

- `/setup [max_members] [category]`: Open a private setup wizard for server-wide study group defaults (Moderator or higher).
  - Every invocation opens the wizard, including servers that already have saved settings. Only the person who opened it can use its controls.
  - Choose an existing server category or enter a name for a new category. The selected category holds new study group channels, a dedicated `#cpo-commands` text channel, and a `#cpo-logs` channel for group activity logs.
  - `max_members`: Optional starting value for the default group limit (1–50).
  - `category`: Optional starting selection for an existing category.
  - Category choices and settings remain staged until Save. Save creates the commands and logs channels or reuses their recorded channels in the chosen category, then stores the category, channel IDs, member limit, and default lifetimes together. Choose Edit lifetimes to stage positive durations such as `24h` or `1d 12h`; both default to 24 hours and affect new groups or Pomodoros. Cancel or expiry leaves saved settings unchanged; controls reject changes and cancellation while Save is in progress.
  - Commands, logs, and new group channels inherit the selected category permissions. Configure category visibility to control who can read logs. Logs record group creation, ending, and purges. They do not stream the bot's runtime output.
  - Save also creates or reuses `CPO Manager` and `CPO Bot Developer` roles and synchronizes staff membership and category/channel access. These roles receive scoped CPO channel permissions, without guild-wide Administrator permission. The bot needs Manage Roles and a higher role position. Saved grants remain recorded if Discord role sync fails; the reply reports the failure.
  - Reusing recorded channels can move them into a newly selected category with `sync_permissions=True`, including channels already in the category whose permissions differ. If a Save attempt changes Discord resources but cannot store the settings, retry Save or review the retained or moved resource IDs shown on cancellation or expiry. Created resources are not automatically deleted, and moved channels are not automatically restored.
- `/set_group_category <category>`: Set the category used by `/create_group` (Moderator or higher).
- `/set_mod_log_channel [channel]`: Save a channel for group creation, ending, and purge event embeds (server manager).
  - Omit `channel` to disable logging. Event embeds identify the group and actor without sending mentions. Missing channels or Discord send failures are logged locally.
- `/sync_commands [guild_only: bool = False]`: Synchronize application slash commands with Discord (staff only; runtime authorization enforced).
  - `guild_only`: When `True`, synchronizes slash commands to the current server; when `False`, syncs globally.

- `/user_level [user: Optional[discord.Member]]`: Check the authorization level and tier of any member (Visible to all)
  - `user`: Optional member to inspect (defaults to yourself). Returns a fixed-title authorization embed with the member, contextual tier label, and numeric level. A display name is never used as the authorization level.

- `/add_bot_developer <user>`: Add a bot developer (Bot Developer only).
  - `user`: The user to promote to bot developer.

- `/add_guild_manager <user>`: Add a guild manager (Level 3 staff or Bot Developer).
  - `user`: The user to promote to administrator/manager.

- `/remove_guild_manager <user>`: Remove a guild manager (Level 3 staff or Bot Developer).
  - `user`: The user to demote from manager status.

- `/list_managers`: List all managers and staff for this server (Moderator / Admin permission required)
  - Includes newly added guild managers and global bot developers immediately, even if the user is not cached. A user appears once at their highest grant; large lists span multiple embeds without truncating entries. The configured bot developer is included too.

- `/set_permission_level <user> <level>`: Set the permission level for a user (Bot Developer only)
  - `user`: The user to set permissions for.
  - `level`: 0 removes the server grant, 3 grants Manager, and 4 grants Bot Developer. Levels 1 and 2 come from contextual group membership and ownership and cannot be assigned by this command.

- `/sync_managers`: Synchronize server owner and moderators (Level 3 staff or Bot Developer).
  - Scans native guild permissions and records server owners, administrators, and moderators at Level 3 with `server_sync` provenance. Explicit bot-added grants are preserved.

All commands use slash syntax (`/`). Registered staff commands omit Discord's default permission restriction so explicitly granted managers and developers can reach them without native Administrator permissions. Runtime handlers still enforce each command's authorization and return private denials. Servers can impose their own command restrictions through Discord settings.

### Response visibility and privacy

Normal replies are public in active study-group channels and the exact commands channel saved by `/setup`. Other channels, threads, and DMs receive private replies. Without a saved commands channel, only active group channels allow public replies. Channel names and category membership alone do not enable public replies.

The private `/help` command, setup wizard, permission denials, validation failures, and sensitive results remain private everywhere. Task action menus, cross-group task lists (`/task_list all_groups:True`), and global task purges (`/task_purge all_tasks:True`) are always private. Ordinary productivity metric replies follow the group/commands-channel rule.

This rule applies to command replies. Group dashboards, check-in reminders, Pomodoro announcements, moderator logs, and invitation DMs continue to use their existing destinations.

---
