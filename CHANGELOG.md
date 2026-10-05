# Changelog

All notable changes to the **Chief Productivity Officer (CPO)** Discord Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Independent exhaustive source audit, 2026-10-05 — deployment blocked
- Completed source-body review of 1008/1008 functions across 49 executable files, 50/50 lambdas and 83/83 counted module statements, plus config/CI/packaging inspection. Detailed semantic mapping remains pending. Current unchanged-runtime offline checks pass (484 full tests, 134 focused tests, Mypy, Ruff and whitespace), without deployment signoff.
- Opened verified invitation policy/CAS/restart, missing general command audit, cross-guild votekick, check-in owner persistence and Pomodoro save-failure findings in KNOWN_ISSUES/TODO. Existing vote and invite-only blockers remain open. DATA-02 parentheses are equivalent; complete lock coverage is unverified.
- Added partial-provisioning, missing/higher-tier authority, embed-limit and SQLite notification findings. Reopened democratic-vote, invitation durability, comprehensive audit and full-serialization claims. DATA-02 is an equivalent-expression correction.
- Attempted fresh offline packaging in a disposable source copy; build failed because setuptools.build_meta is unavailable. Runtime/tests were not modified.


### Independent audit, 2026-10-05

- Fresh local checks passed 484 full-suite tests, 134 focused tests, Mypy across 43 files, Ruff lint/format, and whitespace validation.
- Deployment remains blocked: adverse-order probes reproduced stale end-group votes, owner removal after failed ownership persistence, and votekick ignoring a target's promotion to administrator. Invite-only admission remains unresolved. Runtime source was not changed by the audit.

### Resumed fixes, 2026-10-05 (Antigravity fixes — yet to be verified; previous checkpoint: codex checkpoint [8e9e298], intermediate: antigravty checkpoint [f9a3981])
- **[VERIFIED OFFLINE for covered scenarios; live Discord pending]** Default DM task purge deletes only the invoker's personal tasks with no server or study-group scope. Explicit `all_tasks: true` retains its cross-scope behavior.
- **[VERIFIED OFFLINE for covered scenarios; live Discord pending]** Setup records resource mutation intents, IDs, original categories, and permission overwrites in the approved durable recovery journal. Settings commit atomically with the journal phase; staff synchronization follows the commit and remains retryable after restart.
- **[VERIFIED OFFLINE for covered scenarios; live Discord pending]** New study groups apply their saved or explicitly overridden member limit to voice-channel capacity. Updating setup defaults does not resize existing groups.
- **[VERIFIED OFFLINE for covered scenarios; live Discord pending]** Setup and selected moderator logs use private channel overwrites for current staff and the bot. Staff synchronization seals log access before role changes, and action logging verifies access before sending.
- **[VERIFIED OFFLINE for covered scenarios; live Discord pending]** Guild configuration and group allocation share setup recovery's lock; recovery revalidates resource ownership after recording rollback intent. Discord authority changes reconcile log access, and private logs remain independent of category staff-role permissions.
- **[VERIFIED OFFLINE for covered scenarios; live Discord pending]** Check-in reminder waits drain cancellation without leaving sleep/event tasks behind. Reminder, admission, and ending operations serialize; cancelled video-enforcement tasks cannot unregister replacements.
- **[VERIFIED OFFLINE for covered scenarios; live Discord pending]** Shutdown unloads and drains background timers, reminders, monitors, and video tasks before closing SQLite. Pomodoro state remains persisted for restart.
- **[Antigravity fix — yet to be verified]** Command-granted developers are Level 4 within their guild; only `.env` `BOT_DEVELOPER_ID` is global Level 5, named Supreme Commander. Legacy null-guild developer rows remain stored without conferring guild authority. Non-task activity, focus metrics, limits, and settings use the current guild; explicit cross-scope task operations remain available.
- **[VERIFIED OFFLINE for covered scenarios; live Discord pending]** Check-in guild settings and permission lists are validated and persisted in the approved `checkin_guild_settings` table. Startup restores them; successful saves update memory and active-session policy, while failed writes preserve the previous policy. Failed session deletion remains retryable.
- **[Antigravity fix — yet to be verified]** Setup can select, create, or clear an optional required access role. Its nullable guild setting and creation recovery journal survive restart; no members are enrolled automatically. Guild commands and controls require the selected role, including staff and the Supreme Commander. Authorized Setup remains available to repair access; no selection leaves the server unrestricted.
- **[Antigravity fix — yet to be verified]** Implemented durable recipient invitations across study groups, check-in sessions, and Pomodoro timers, backed by the `session_invitations` table. Enforces a 360-second impending-expiration warning and an absolute 600-second expiration notice. Direct message delivery supports target member resolution, and button callbacks enforce CAS locks, roster limits, and lifecycle re-checks.
- **[Antigravity fix — yet to be verified]** Added guild-scoped command audit events logging in SQLite via `command_audit_events` table and Discord moderator logs, tracking invoker snowflake, evaluated authorization tier (Tiers 0–5), target resource identities, action name, execution outcome, and timestamp.
- **[Antigravity fix — yet to be verified]** Created `database_architecture.md` and updated `ARCHITECTURE.md` with complete Mermaid entity-relationship diagrams, invitation/journal state-machine models, data dictionaries for all 16 tables, and concurrency invariants.
- **[Antigravity fix — yet to be verified]** **Democratic End Group Voting**: Group Owner and regular members initiate a democratic vote via `EndGroupVoteView` requiring majority consent `(len(members) // 2) + 1` to end the study group. Single-member groups end immediately. Level 3+ Staff/Managers bypass the vote and terminate groups instantly.
- **[Antigravity fix — yet to be verified]** **Votekick with Staff Immunity and Owner Reassignment**: Added `/votekick` slash command and interactive dashboard button `votekick_callback` with `VotekickSelectView` and `VotekickView`. Server staff (Level 3+) are strictly immune. If a group owner is voted out, ownership automatically transfers to the next member in the roster. Self-kicking is rejected.
- **[Antigravity fix — yet to be verified]** **Pomodoro Concurrency & Authorization**: Added session-level lock (`session.lock`) and group-level creation lock (`_start_locks`) to serialize timer ticks, stage advances, pause/resume, and prevent duplicate session creation. Gated `/start_pomodoro`, `/pause_pomodoro`, and `/resume_pomodoro` to group creator/owner or Level 3+ managers. Fixed operator precedence bug in focus accounting (`cogs/pomodoro.py:1468`). Added rollback cleanup on voice channel creation failure.
- **[Antigravity fix — yet to be verified]** **Check-in Hardening**: Guarded `start_checkin` and command permissions decorators with early interaction deferrals before DB queries to guarantee Discord 3s SLA. Fixed break callback to correctly increment absence counts instead of resetting to 1. Wrapped `mark_present_callback` and `start_break_callback` under `join_lock`.
- **[Antigravity fix — yet to be verified]** **Group Management & UI**: Synchronized in-memory `owner_id` on `/transfer_group`. Bounded `/create_group` `max_members` to 1–99 and made `mentions: Optional[str] = None`. Updated `acknowledge_interaction` to catch `discord.InteractionResponded`.

### QA and packaging, 2026-10-05
- Prerelease validation/build jobs now pin Python `3.11.17` on Ubuntu 24.04. General CI replaces its floating 3.11 entry with `3.11.17`, retains 3.10/3.12 coverage, and consistently invokes `python -m pytest`. Availability was verified against Python.org and the official Actions Python manifest.
- Published prerelease `v1.0.0-rc.5` on Chief-Productivity-Officer from immutable source commit `a01656c`. Both authorized branches include workflow repair `817cccf`. Downloaded wheel, sdist, runtime ZIP, and GitHub source ZIP passed integrity, digest, membership, version, and source checks. The same rc.5 prerelease was subsequently published on crispy-octo-happiness after exact Python 3.11.17 validation/build succeeded. Both repositories' 3.10/3.11.17/3.12 CI matrices passed. Downloaded crispy assets passed the same archive/source checks. The existing Chief release was preserved; neither release includes later partial-implementation work.
- Release verification invokes `python -m pytest` so repository imports resolve under the configured importlib test mode. Manual release recovery checks out the requested tag for both verification and packaging, preserving its immutable source commit.
- Package version is `1.0.0rc5` for `v1.0.0-rc.5`. Wheel, source distribution, and hosting runtime ZIP exclude tests, caches, databases, secrets, governance reports, and development automation; release builds validate exact archive contents before upload. Git retains regression tests. Removed the unused `cogs/study_groups.txt` backup.
- Added source-based code and database maps and a checked-TODO evidence audit. Corrected unsupported completion claims; 53 current checked items are supported within their documented offline scope. Default server task lists and action menus now select only that server's global tasks outside a group.

### Added
- A new `/remove_bot_developer` command to remove developers (Bot Developer only).
- Self-update guards for `/add_bot_developer`, `/remove_bot_developer`, `/add_guild_manager`, `/remove_guild_manager`, and `/set_permission_level`. Prevent users from modifying their own roles and immediately DM the primary bot developer on violation.
- Standardized and updated permission denial responses to the user-requested "Go away peasent" message.
- A private `/help` command with everyday explanations of setup, groups, timers, tasks, invitations, and reply visibility. Staff (Level 3–4) see elevated descriptions; regular members (Level 0–2) see standard guidance only. `/help` defers privately immediately to avoid 3-second timeout.
- Pomodoro lifetime expiry, including while paused, and a Renew control offered with one hour left. Renew adds 24 hours to the current deadline.
- Approved additive SQLite settings columns `default_group_duration` and `default_pomodoro_duration`, stored in seconds with 86400 defaults. Setup saves both values atomically and checks them for stale drafts.
- Approved `managers.grant_source` migration distinguishes explicit grants from server-synced staff. Sync revokes stale server-synced grants while preserving explicit grants; legacy moderator grants normalize to Level 3.
- `CPO Manager` and `CPO Bot Developer` roles synchronize membership and scoped access to the configured CPO category and its channels during setup and staff grant updates.
- **Pomodoro runtime persistence** (`database.py`, `cogs/pomodoro.py`): new `pomodoro_runtime` table stores `session_key`, `group_id`, `guild_id`, `state_json` JSON, and `active` flag. `save_pomodoro_runtime`, `retire_pomodoro_runtime`, and `retire_group_pomodoro_runtime` persist and clean up snapshots under the asyncio lock. `_runtime_lock` serializes concurrent persist/retire. `load_active_sessions_from_db` (called from `bot.py:on_ready`) hydrates deadlines, stage, cycles, timer, pause state, consent roster, dropout list, absence counts, and per-user focus-second accumulators. Offline-elapsed time advances stages without attendance or focus credit. Malformed or cross-guild/cross-UUID records are retired. Group deletion retires all group runtimes atomically. Snapshots target a 15-second interval; the crash-loss window can grow when persistence fails. Runtime saves reject inactive or missing same-guild groups.
- **Productivity focus-time analytics** (`database.py`, `utils.py`, `cogs/productivity_tracker.py`): new `productivity_focus_time` table accumulates per-session per-user seconds with a monotonic MAX upsert. `save_productivity_focus_time` validates finite non-negative values and rejects partial writes. `get_productivity_focus_seconds` aggregates cumulative seconds. `ProductivityService` computes exact unrounded efficiency from measured seconds and returns zero when no focus time is recorded. Embed labelled "measured-focus". Focus is counted only for consented + present + not-dropped-out members during active focus stages; breaks, pauses, dropout, and bot downtime are excluded.
- **Default VC and video relocation** (`cogs/_setup_view.py`, `cogs/_voice_relocation.py`, `cogs/manager.py`, `cogs/study_groups.py`, `database.py`): `/setup` adds an optional `default_vc` slash command parameter and interactive `VoiceSelect` channel picker in `SetupView`; creates or reuses `CPO Lobby` (or the selected voice channel) under the selected category; destination saved atomically as `default_vc_id` (backward-compatible additive column on `guild_settings`). `SetupView.render()` shows a move notice if the default VC resides outside the selected category; `_save_locked` validates `view_channel`, `connect`, and `move_members` bot permissions before saving. `_voice_relocation.py` shared helper checks destination existence, guild, capacity, Connect/Move Members permissions, and member's current source before moving; sends a DM notification upon successful move, or informative guidance on failure without a disconnect fallback. `study_groups.py` calls the helper after the existing video grace period. Microphone enforcement intentionally disabled per user request.
- New test modules and test additions: `tests/test_cleanup_retries.py` (8 persistent cleanup retry scenarios), `tests/test_bot_developer_id.py` (46 developer ID validation and CPO integration scenarios), `tests/test_pomodoro_recovery.py` (9 recovery scenarios), `tests/test_default_vc.py` (default VC migration, relocation, and notification), `tests/test_productivity_time.py` (monotonic upsert, multiple users, invalid values, restart survival), `tests/test_setup.py` (default VC slash option, VoiceSelect staging, category move notices, and bot permission verification), `tests/test_database.py` (thread execution and cancellation safety). The initial test checkpoint passed 337 offline tests.
- **`BOT_DEVELOPER_ID` strict validation and placeholder rejection** (`utils.py`, `bot.py`, `main.py`): added `validate_bot_developer_id` checking 17–20 digit Discord snowflake format, 64-bit unsigned bounds, and rejecting `.env.example` dummies (`123456789012345678`, `1234567890123456789`), doc string placeholders (`your_discord_user_id_here`), generic placeholders (`placeholder`, `changeme`, `none`, `null`, `todo`), repetitive digit sequences (`111111111111111111`), negative numbers, booleans, and floats. Supports `strict=True` for configuration assertions and non-strict graceful degradation (logging a warning and returning `None`) for startup imports.
- **Setup resource recovery with explicit ownership checks** (`cogs/_setup_view.py`, `cogs/manager.py`): interactive `Recover` button on `SetupView` and programmatic `recover_retained_resources` allow cleaning up uncommitted Discord resources (categories, commands channels, log channels, voice channels) and reverting moved channels when setup saves fail or are discarded. Strict explicit ownership checks verify session creation ownership, ensure IDs do not collide with active database settings (`guild_settings`) or active study groups, ensure categories are completely empty before deletion, revert moved channels without deletion, and verify current guild and staff authority. Superseded sessions in `Manager.setup` automatically recover uncommitted resources. Covered by 6 dedicated tests in `tests/test_setup.py`. That checkpoint passed 343 offline tests.
- **Persistent retry tracking for Discord resources** (`database.py`, `cogs/study_groups.py`, `bot.py`): new `pending_resource_cleanups` table and index store `guild_id`, `group_id`, `resource_type` (text_channel, voice_channel, role), `resource_id`, `retry_count`, `last_error`, and `status`. Group termination in `StudyGroup.end_group` and fallback records failed deletions instead of abandoning them. A background task (`cleanup_retry_loop` every 10 minutes) and startup sweep in `bot.py:on_ready` automatically re-attempt deletion or prune records when resources are confirmed gone. Staff command `/retry_cleanups` allows on-demand execution and status reporting.
- **Invitation Syncing and Owner DMs** (`cogs/study_groups.py`, `cogs/pomodoro.py`): Automatically add users to the study group when they accept Pomodoro invitations if they are not already members. Group owners are now explicitly DMed whenever an invited user accepts or declines a study group or Pomodoro invitation.

### Changed
- **Asynchronous SQLite execution off event loop** (`database.py`): all database I/O, schema migrations, queries, and transactions are moved off the asyncio event loop using `asyncio.to_thread`. Connections initialize with `check_same_thread=False` and execute synchronous SQLite drivers in worker threads under `async with self.lock:`, preventing event loop latency and starvation. The dispatcher drains cancelled workers before releasing the database lock; test connections use `check_same_thread=False`.
- `/setup` opens a private wizard for moderators, with category selection or creation, commands and logs channels, default voice channel selection/creation, group size, and default group/Pomodoro lifetimes. Both lifetimes default to 24 hours and apply to new sessions. Saving synchronizes recorded channels with the category permissions, including logs and lobby already in that category. Setup now also creates/reuses `CPO Lobby` VC and saves its ID.
- Ordinary command replies are public in active study-group channels and the exact configured commands channel. Other channels, threads, and DMs use private replies; help, errors, and sensitive menus stay private everywhere.
- Mentioned group and check-in invitees receive DM Join/Decline controls. Pomodoro group members receive separate opt-in invitations. Only the creator joins automatically; entering voice does not start or join a Pomodoro.
- Check-in reminder intervals and each Pomodoro focus/break stage accept 2 minutes through 4 hours. Automatic breaks retain the 5:1:3 calculation with a two-minute minimum.
- Current owners and guild staff can end groups and sessions directly. Ordinary participants request the current owner's approval by DM; outsiders cannot request an end. Former owners do not retain an ending override.
- New groups use `{user-name}-studysession-{number}` when unnamed. Duplicate custom names receive numeric suffixes; guild creation locks serialize name allocation and provisioning while UUIDs stay unchanged.
- Force Video accepts a camera or screen sharing.
- Authorization labels use Server Member (0), contextual Group Member (1), contextual Owner (2), Manager/Admin/Mod (3), and Bot Developer (4), with the highest level taking precedence. `/user_level` uses a fixed title and does not expose unrelated group membership outside that group's channels.
- Removed check-in and Pomodoro action buttons from the group dashboard while retaining their status fields. Standalone voice/channel/role maintenance commands are hidden from the public command tree.

### Fixed (Done by Antigravity — yet to be tested)
- **[Done by Antigravity — yet to be tested]** Restricted default guild task lists and action menus to personal tasks outside groups. Explicit cross-group listing remains private; active group and DM scopes are preserved. Real SQLite regressions cover listing, menus, foreign guilds, and analytics.
- **[Done by Antigravity — yet to be tested]** Prevented duplicate group teardown after manual ending and background expiry overlap. Ending is serialized, deleted Discord resources are treated as already gone, and a failed final focus save leaves the group usable for retry with a private failure notice.
- **[Done by Antigravity — yet to be tested]** Corrected fractional Pomodoro timing and stage overflow. Gateway downtime advances stages without focus credit or attendance penalties. Present status is tracked separately from Absent responses, and voice-mode credit requires current session-VC presence.
- **[Done by Antigravity — yet to be tested]** Preserved cumulative focus counters across split runtime/analytics writes and failed final saves. Recovery reconciles counters by tracking ID before resuming.
- **[Done by Antigravity — yet to be tested]** Kept the SQLite lock until cancelled workers finish, including repeated cancellation; connection opening and closing use that lock. Removed the synchronous test fallback.
- **[Done by Antigravity — yet to be tested]** Made setup recovery fail closed on ownership lookup errors, restore original channel overwrites, and retain failed recovery handles. Cancelled or expired drafts can retry recovery through `/setup`.
- **[Done by Antigravity — yet to be tested]** Guarded cleanup retries against active groups, saved settings, foreign resources, and uncertain fetch failures.
- **[Done by Antigravity — yet to be tested]** Fixed `/remove_guild_manager` false negatives when attempting to remove a user that had global elevated status by relying on actual db removal count rather than high-level role checks.
- **[Done by Antigravity — yet to be tested]** Resolved ARC-06: Uncommitted setup resources retained after failed saves can now be recovered and cleanly removed or reverted with explicit ownership verification rather than stranded permanently in the Discord guild.
- **[Done by Antigravity — yet to be tested]** Resolved ARC-05: Discord channels and roles left behind during group ending due to permission denial are persistently tracked and cleaned up on retry rather than orphaned.
- **[Done by Antigravity — yet to be tested]** Prevented unhandled `ValueError` crashes and privilege escalation during startup if `BOT_DEVELOPER_ID` contains placeholder or invalid values.
- **[Done by Antigravity — yet to be tested]** Fixed `invite_to_group` raising `AttributeError` when inviting a bot due to `create_dm` limitations by adding a `member.bot` check.
- **[Done by Antigravity — yet to be tested]** Fixed `transfer_ownership` silently replacing owners with non-members when `add_member` failed by verifying its boolean return value.
- **[Done by Antigravity — yet to be tested]** Fixed `/set_permission_level` failing to demote users with global Bot Developer grants to Server Members by explicitly removing both guild-scoped and global permission records.
- **[Done by Antigravity — yet to be tested]** Full-unit and compound duration parsing, including `3 hours` and `1d 12h`.
- **[Done by Antigravity — yet to be tested]** Role-name guesses no longer confer moderator authority. Permission checks use actual Discord permissions or scoped stored grants; foreign-guild grants and member objects cannot escalate access.
- **[Done by Antigravity — yet to be tested]** `/list_managers` shows newly added guild managers and global developers immediately, with uncached-user labels, one entry per person at the highest grant, and untruncated multi-embed lists. Repeated global grants update rather than append, and permission lookup selects the highest valid grant.
- **[Done by Antigravity — yet to be tested]** `/invite_to_group` resolves trimmed, case-insensitive names and current group text/voice channels from active persisted records after a cache miss.
- **[Done by Antigravity — yet to be tested]** Voice-channel creation uses the configured category and rolls back if persistence fails.
- **[Done by Antigravity — yet to be tested]** `test_session_controls.py`: two tests that constructed `Pomodoro(MagicMock())` without an async DB now use `bot.db = AsyncMock()` so that `_retire_runtime` and `_persist_session` can be awaited correctly (fixes `TypeError: object MagicMock can't be used in 'await' expression`).

### Verification
- On 2026-10-05, all 479 offline tests pass on Python 3.12.14. Mypy reports zero errors across 43 source files; Ruff lint, formatting, and whitespace checks pass. No new dependencies introduced. Live Discord behavior remains unverified / yet to be tested.


## [1.0.0-rc.5] - 2026-10-05

### Changed
- Setup saves a default voice destination; video enforcement relocates members without camera or screen sharing after the grace period. Microphone enforcement remains off.
- Pomodoro snapshots restore timer state after restart. Productivity uses measured attended focus, excluding breaks, pauses, absence, dropout, and bot downtime.
- Help descriptions follow permission level; command replies follow active-group or exact commands-channel context.

### Fixed
- Serialized group ending prevents duplicate channel/role deletion and use of cleared group state. Final focus writes finish before cleanup; failures preserve the active group for retry.
- SQLite cancellation drains worker operations before releasing locks. Cleanup retries verify resource ownership; setup recovery restores original channel/category permissions.
- Separate Present status prevents Absent responses earning focus credit. Fractional countdowns, reconnect stage advancement, and cumulative analytics recovery avoid double counting.
- Default server task lists and action menus exclude group tasks outside an active group.

### Deployment and verification
- Clean wheel, source distribution, and runtime ZIP exclude tests, internal automation, audit notes, caches, databases, and secrets. Tests remain in Git. Use the runtime ZIP for hosting panels.
- 402 offline tests pass; Mypy and Ruff lint/format pass, including the package validator. Archive membership and injected-file rejection were verified.
- Live Discord provisioning, DM delivery, hierarchy behavior, and relocation remain unverified. Setup recovery handles are memory-only; snapshot write failures can widen the target 15-second crash-loss window.

## [1.0.0-rc.4] - 2026-10-02

This rc4 release candidate introduces category-based response visibility and server-scoped tasks. Python package metadata is `1.0.0rc4`.

### Changed
- Expanded category-based response visibility (`should_use_ephemeral`) across study groups, Pomodoro, check-ins, management, and productivity commands, keeping success responses public inside configured group categories and ephemeral elsewhere while preserving strictly ephemeral permission and validation errors.
- Scoped task storage and default `/task_list` results in a server to that specific server (`guild_id`), preventing tasks from leaking across different servers unless `all_groups: true` is explicitly opted into.
- Integrated category-based response visibility helper (`should_use_ephemeral`) across all task commands (`/task_add`, `/task_complete`, `/task_delete`, `/task_purge`, and `/task_list` when `all_groups=False`) and voice commands (`/create_vc`, `/delete_vc`, `/delete_role`, `/delete_text_channel`), ensuring `/task_list` is ephemeral outside the configured study group category and always ephemeral when `all_groups: true`.
- Scoped default `/task_list` results to global tasks outside a study group; `all_groups: true` is now the explicit cross-group opt-in and returns an ephemeral result.
- Force Video now stores `force`, warns members after 30 seconds, uses a default 60-second total wait with a warning for the final 30 seconds, and Speak toggles update both channel-wide and group-role microphone permissions.
- Study-group voice channels now remain available when the last member leaves; deletion remains manual or part of group cleanup.
- Added a `main.py` compatibility launcher for hosting providers that invoke `/home/container/main.py`; it delegates to the canonical `bot.py` startup path.
- Corrected the TODO and known-issue registers after checking completion claims against the release code and test assertions.
- Restored asserted, in-memory command tests and completed the rc3 task, invitation, voice-setting, and moderator-log flows.
- Replaced destructive legacy schema startup with additive migration and retained group primary keys during updates.

## [1.0.0-rc.3] - 2026-10-01

This rc3 candidate builds on the `c7bdca3` release base. Python package metadata remains `1.0.0rc3`.

### Added
- Four-character alphanumeric task IDs.
- Interactive task-list pagination with 15 tasks per page.
- A regression test verifying that fresh Pomodoro interactions defer before using follow-up messages.
- Recipient-only invitation DMs with Join and Decline buttons, five-minute expiry, and capacity checks.
- Persisted moderator logging through `/set_mod_log_channel`, with creation, ending, and purge event embeds.
- Owner-checked Select menus for task completion and deletion.
- Declared `davey>=0.1.6` in runtime dependency manifests.

### Fixed
- Restored `InteractionResponse.is_done()` calls in command handlers and corrected the standalone synchronous interaction-state mock.
- Read study-group lookup records by dictionary keys when creating voice channels.
- Removed duplicate rc3 changelog entries and unsupported completion claims from the release notes.
- Preserved legacy groups, rosters, and role/channel IDs during schema migration, including historical table names and partially migrated IDs.
- Preserved group database IDs when saving existing groups. Ended groups remain as inactive records and are excluded from active lookups.
- Implemented Speak and Video permission controls without replacing unrelated voice-channel overwrites. Failed database writes trigger permission rollback.
- Serialized group admission and blocked joins during teardown. Failed role assignment or membership persistence does not admit the recipient.
- Combined group mentions, status, and controls in one dashboard message; task command results and group creation results are public.
- Batched task purges and limited channel cleanup to matching bot messages owned by the invoking user. Discord cleanup failures are reported.
- Added a DM response fallback for Discord error 10003 after group cleanup removes the invocation channel.
- Removed related Pomodoro aliases during group cleanup and made moderator logging failures independent of cleanup.
- Restored standalone success assertions, real task IDs, mandatory dashboard execution, an in-memory database, and cleanup in `finally`; pytest now executes the command matrix.
- Included the standalone runner, dependency manifests, and release documentation in source distributions so packaged tests remain runnable.

### Verification and remaining work
- All 60 pytest tests pass on Python 3.12, including the asserted 54-flow standalone command matrix. Mypy, Ruff lint, and Ruff formatting checks pass.
- Forced camera participation, asynchronous SQLite I/O, external API timeouts, and other documented debt remain open. See `TODO.md` and `KNOWN_ISSUES.md`.

## [1.0.0-rc.2] - 2026-09-28

### Added
- **`/setup` Command**: Added `/setup` to view or update the default study-group member limit and category for a server.
- **`/purge_groups` Command**: Added a standalone command allowing server Moderators/Admins to end all active study groups in the current guild.
- **Global Task Purge**: Added an `all_tasks` parameter to `/task_purge` to allow any user to purge all their tasks globally across all groups.
- **Default Max Members Setting**: `/setup` lets server managers configure the default maximum number of members per study group (1–50). `/create_group` uses this value when no group limit is provided.
- **Pomodoro Interactive Attendance UI**: A UI with "Present" and "Absent" buttons is now sent at the start of every focus session.
- **Pomodoro Dropout System**: Users who miss marking themselves Present for 4 consecutive focus sessions (absence > 3) are automatically dropped out of the session. If all members drop out, the Pomodoro session automatically pauses.
- **Individual Pings in Pomodoro**: Pomodoro alerts now ping individual active members instead of the entire group role, except when resuming.
- **Pomodoro Resume Enhancements**: When `/resume_pomodoro` is used, the member is reinstated into the active session, and the entire group role is pinged with one of 100 randomly selected encouraging messages.
- **Pomodoro Auto-Start**: Pomodoro sessions now automatically start with default settings (25m Focus, 5m Short Break, 15m Long Break) as soon as any member joins the group's active voice channel (if a session isn't already running).
- **Pomodoro Cycle Tracking**: Pomodoro cycle counts (e.g., "Cycle 1 complete!", "Cycle 2 starting!") are now explicitly displayed in all session status messages and alerts.

### Fixed
- Fixed Pomodoro controls failing after voice-channel auto-start by returning study-group lookups as dictionaries and indexing active sessions by both database ID and group UUID.
- Fixed missing `/setup` and management slash commands by syncing the global command tree to each guild on startup and applying Discord visibility permissions that match command authorization.
- Fixed `/list_groups` reporting incomplete member counts by persisting the creator and invited members at group creation and consistently looking up membership by group UUID.
- Removed a stale commented credential from `bot.py`.
- Removed unused MongoDB packages from the dependency manifests, avoiding an invalid package-extra warning during installation.
- Updated the GitHub Actions runtimes and pinned the runner image to remove Node.js and Ubuntu migration warnings.
- Fixed critical crash bug in `start_pomodoro` and task management where `sqlite3.Row` was causing `AttributeError` on `.get()` calls by safely casting row results to dictionaries.
- Fixed `Unknown Webhook` errors on `/task_list`, `/task_add`, and `/setup`'s default category select by ensuring `interaction.response.defer()` is consistently awaited prior to fetching from the database or responding.
- Fixed missing `defer()` in `/add_guild_manager`, `/remove_guild_manager`, `/add_bot_developer`, and `/set_permission_level` causing these commands to crash with `Unknown interaction` before or after modifying the database.
- Fixed `/list_managers` failing to properly list added bot managers by resolving an Enum type comparison error.
- Fixed `/list_managers` showing removed managers by reverting it to strictly query the authoritative database instead of blending with dynamic native Discord roles.
- Fixed `purge_groups` silent failure issue on bot restart by querying the active groups directly from the database instead of volatile memory dicts.
- Fixed an accidental text formatting bug where literal `\n` was outputting raw string text `\n` instead of actual line breaks in `/list_managers`.
- Fixed time formatting pluralization logic in `parse_seconds_to_hms` to dynamically remove 's' on singular values (e.g. `1 minute` instead of `1 minutes`).

### Planned
- Migration of synchronous SQLite queries in `database.py` to `aiosqlite`.
- Periodic database snapshot and backup routine.

---

## [1.0.0-rc.1] - 2026-09-25

### Added
- **GitHub Workflows & Automated Packaging Infrastructure**:
  - Added [`.github/workflows/ci.yml`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/.github/workflows/ci.yml) providing multi-version Python testing matrix (3.10, 3.11, 3.12) with automated static typing (`mypy`), linting (`ruff check`), formatting validation (`ruff format`), and test coverage reporting (`pytest`).
  - Added [`.github/workflows/prerelease.yml`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/.github/workflows/prerelease.yml) automating wheel (`.whl`) and source distribution (`.tar.gz`) packaging via `python -m build` and deploying GitHub Prereleases on `v*` tag pushes or manual `workflow_dispatch`.
  - Configured `[tool.setuptools]` and `[tool.setuptools.packages.find]` in [`pyproject.toml`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/pyproject.toml) to support standard wheel/sdist distribution generation.
  - Removed outdated legacy workflows (`workflows/python-app.yml` and `.github/workflows/python-app.yml`).
- **Autonomous Governance & Agentic Architecture Framework**:
  - Overhauled [`AGENTS.md`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/AGENTS.md) with copy-pasteable toolchain directives (install, dev, build, lint, test, format), strict Three-Tier Guardrails (Always Do, Ask First, Never Do), architectural invariants, offline test mocking patterns, and the mandatory Agent Operating Contract.
  - Refreshed [`KNOWLEDGE_GRAPH.md`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/KNOWLEDGE_GRAPH.md) detailing directory topology, component boundaries, execution lifecycles (slash commands & background standup loops), SQLite ER schema, and state invariants.
  - Established [`KNOWN_ISSUES.md`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/KNOWN_ISSUES.md) tracking active defects, architectural debt (such as blocking SQLite calls and high cyclomatic complexity), and security/reliability hazards.
  - Established [`TODO.md`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/TODO.md) organizing all audit findings into prioritized engineering tiers (P0, P1, P2, and Backlog).
- **On-Demand Single Slash Command Sync (`/sync_commands`)**:
  - Added dedicated `/sync_commands [guild_only: bool = False]` slash command in [`cogs/manager.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/manager.py) allowing Administrators and Bot Developers to trigger immediate application command synchronization (either globally across all guilds or scoped strictly to the current guild).
- **Admin Command Invisibility for Non-Admins (`default_permissions`)**:
  - Implemented Discord native `@app_commands.default_permissions(...)` on all administrative and management commands so that they are completely invisible to regular non-admin/non-mod users in Discord's slash command picker:
    - `administrator=True`: `/sync_commands`, `/sync_managers`, `/add_bot_developer`, `/add_guild_manager`, `/remove_guild_manager`, `/set_permission_level`, `/settings_checkin`.
    - `manage_guild=True`: `/list_managers`.
    - `manage_channels=True`: `/delete_vc`, `/delete_text_channel`.
    - `manage_roles=True`: `/delete_role`.
- **Three-Tier User Level Hierarchy (`User`, `Mod`, `Admin`)**:
  - Formalized a clear 3-tier authorization model across permission checks, database queries, and UI inspection:
    - **`Admin`** (Levels 3 & 4): Bot Developer (`BOT_DEVELOPER`), Server Owner (`owner_id`), Server Administrator (`perms.administrator`).
    - **`Mod`** (Level 2): Members with `manage_guild`, `manage_channels`, `manage_roles`, `moderate_members`, `kick_members`, `ban_members`, staff role names, or registered in DB as `MODERATOR`.
    - **`User`** (Levels 0 & 1): Baseline members (`REGULAR_USER`) and group participants (`GROUP_MEMBER`).
  - Added `/user_level [user]` command allowing any server member to inspect their own or another user's authorization tier (`Admin`, `Mod`, `User`) and numeric permission level with rich embed styling.
  - Updated `utils.py:check_manager` to grant management and moderation access to database managers with `permission_level >= 2` (`MODERATOR`).
- **Comprehensive 54-Test End-to-End Test Matrix**:
  - Expanded [`test_file.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/test_file.py) to 54 exhaustive test flows, covering `/sync_commands` (global/guild/unauthorized), `/user_level` (Admin, Mod, User), tier mapping logic, slash command `default_permissions` visibility verification, and unauthorized rejection on `/settings_checkin`. All 54 tests pass with 100% success.
- **Interactive Group Transfer Dashboard & Slash Command**: Added a dedicated `Transfer Group` button (`🔄`) with an interactive `discord.ui.UserSelect` modal view on the study group dashboard, and registered a `/transfer_group` slash command in [`cogs/study_groups.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/study_groups.py).
- **Study Group Slash Commands**: Added `/end_group` slash command in `StudyGroupCog` allowing group creators, owners, and server managers to cleanly close sessions and clean up Discord channels/roles.
- **Channel-Aware Database Lookup**: Added `get_study_group_by_channel` to `DBHandler` in [`database.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/database.py) to resolve active study groups directly from text or voice channel context.
- **Instant Guild Slash Command Propagation**: Added per-guild tree synchronization in [`bot.py:on_ready`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/bot.py) (`copy_global_to` + `sync(guild=guild)`), eliminating Discord's 1-hour global cache propagation delay.
- Created [`.python-version`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/.python-version) setting Python 3.12 as the project default.
- Created [`.vscode/settings.json`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/.vscode/settings.json) mapping IDE default interpreter path to `.venv/Scripts/python.exe`.
- Strict typing and type annotations across all project modules (`database.py`, `utils.py`, `cogs/manager.py`, `cogs/pomodoro.py`, `cogs/voice_channels.py`, `cogs/study_groups.py`, `cogs/checkin.py`).

### Changed
- **Permissions Hierarchy Overhaul**:
  - Upgraded `utils.py:check_manager` and `cogs/manager.py:get_permission_level` to natively grant `GUILD_MANAGER` authority to Server Owners (`user.id == guild.owner_id`), server members with moderation permissions (`administrator`, `manage_guild`, `manage_channels`, `manage_roles`, `moderate_members`, `kick_members`, `ban_members`), and members with moderator-style role names.
  - Upgraded `utils.py:is_group_creator`, `StudyGroup.can_control`, and `CheckinGuildSettings.is_owner` to permit server owners and moderators to manage all study groups and check-in sessions.
  - Added safe `.get()` defaults in `database.py:save_study_group` to prevent `KeyError` exceptions when creating or migrating study groups.

### Fixed
- **Repository Hygiene & Static Analysis Traps (Architect Audit)**:
  - Fixed `.gitignore` corrupted wildcard spacing (`* . s q l i t e` -> `*.sqlite` and `scratch_*.py`), which caused Git to treat `*` as a global ignore wildcard and blinded version control to all newly created governance and test files.
  - Resolved Mypy static type errors in [`cogs/pomodoro.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/pomodoro.py) (`_get_session` argument type signature) and [`cogs/study_groups.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/study_groups.py) (`text_id` attribute lookup), restoring 100% clean type check status (0 errors across 16 files).
  - Resolved unawaited coroutine mock RuntimeWarnings in [`tests/test_new_features.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/tests/test_new_features.py) by assigning `MagicMock(return_value=False)` to synchronous `interaction.response.is_done`.
  - Pruned unused imports in [`cogs/tasklist.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/tasklist.py) and [`cogs/voice_channels.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/voice_channels.py), and removed trailing whitespace in multiline SQL execution blocks in [`database.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/database.py).
- **Duplicate Slash Commands in Discord UI**:
  - Resolved duplicate slash command entries (`/create_group`, `/create_vc`, `/delete_role`, etc. appearing twice in Discord) caused by simultaneous global command sync (`tree.sync()`) and guild command copying (`copy_global_to()`).
  - Updated [`bot.py:on_ready`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/bot.py) to execute `tree.clear_commands(guild=guild)` and sync empty guild trees, eliminating guild-scoped duplicates so that only uniquely registered global commands appear in Discord clients.
- **Pomodoro Status Timeout ("The application did not respond")**:
  - Added early interaction deferral in [`cogs/pomodoro.py:pomodoro_status`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/pomodoro.py) and across all pomodoro lifecycle commands (`start_pomodoro`, `end_pomodoro`, `pause_pomodoro`, `resume_pomodoro`).
  - Added `_resolve_group` in `Pomodoro` cog to seamlessly detect sessions via user membership, active channel, or server-wide fallback for server owners and moderators.
- **Group Transfer & Lifecycle Locks**:
  - Fixed issue where group owners were locked out of transferring study groups or sessions.
  - Enforced permission validation on study group dashboard callbacks (`end_group_callback`, `rename_group_callback`, `extend_duration_callback`, `transfer_group_callback`).
- **Check-in Session Management by Staff**:
  - Updated `cogs/checkin.py` (`change_owner_callback`, `end_session_callback`, `can_end`) to grant full administrative override to server owners and moderators.

### Changed
- Verified and installed all production and development dependencies from [`requirements-dev.txt`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/requirements-dev.txt) into the Python 3.12 virtual environment.
- Converted class-level permission and validation decorators in `cogs/manager.py` and `cogs/checkin.py` to `@staticmethod` with explicit typing.
- Updated `View` disabling routines to safely construct views from message payloads using `View.from_message`.

### Fixed
- **UI & Message Formatting**:
  - Formatted raw Unix timestamp in [`cogs/study_groups.py:extend_duration_callback`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/study_groups.py) to use Discord timestamp tags `<t:{end_timestamp}:F> (<t:{end_timestamp}:R>)` instead of printing raw epoch floats.
- **Resolved Discord "The application did not respond" & Interaction Responded Failures**:
  - Global `on_app_command_error` in [`bot.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/bot.py) now unwraps `error.original`, handles `CheckFailure` with user-friendly messages, and safely catches `discord.InteractionResponded` to fall back to `interaction.followup.send`.
  - Fixed button callbacks in [`cogs/checkin.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/checkin.py) (`mark_present_callback`, `start_break_callback`, `leave_session_callback`, `new_owner_callback`) to use `interaction.followup.send` after deferral rather than attempting secondary `send_message` calls.
  - Implemented dual-path response handling (`is_done()` branching with `send_message` / `followup.send`) across [`cogs/voice_channels.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/voice_channels.py), [`cogs/manager.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/manager.py), and [`cogs/pomodoro.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/pomodoro.py).
- **Startup & Pre-Login Stability**:
  - Replaced `bot.fetch_guild()` with `bot.get_guild()` in `cogs/checkin.py:load_active_sessions_from_db` to avoid `_MissingSentinel` gateway lock crashes prior to bot connection.
- **Database & Parameter Binding**:
  - Sanitized `MemberStatus` enum binding in `database.py:add_or_update_checkin_member` using `.value` / `str()` extraction, fixing `sqlite3.InterfaceError: Error binding parameter 3: type 'MemberStatus' is not supported`.
- **Validation & Mentions**:
  - Upgraded `utils.py:parse_mentions` to use robust regular expression extraction (`<@&(\d+)>`, `<@!?(\d+)>`), resolving `ValueError` on comma-separated or mixed mention strings.
  - Updated category channel validation in `utils.py:validate_parameters` to match against channel snowflake IDs rather than object identity.
- **Concurrency & Permission Architecture**:
  - Refactored `cogs/pomodoro.py:run_timer` loop from a parameterized singleton to an in-memory session iterator, eliminating `RuntimeError: Task is already launched`.
  - Removed conflicting stacked `@app_is_manager()` check on `cogs/voice_channels.py` commands while granting bot developers and guild managers transparent access via `utils.py:is_group_creator`.
  - Added auto-initialization of default `CheckinGuildSettings` on unconfigured servers in `cogs/checkin.py:checkin_command_permissions`, preventing false-positive permission denials.
- **Resolved all 220 `mypy` static type checking errors** across all 16 repository source files (`mypy .` now reports 0 errors).
- Fixed latent `AttributeError` in `cogs/study_groups.py` where `StudyGroup` accessed non-existent `self.study_group.name` instead of `self.name`.
- Fixed invalid `await self.disable_buttons()` invocation on a synchronous method in `cogs/study_groups.py`.
- Fixed raw `Component` item additions to `discord.ui.View` during reminder and session cleanup.
- Fixed parameter type discrepancy between `utils.parse_mentions` and `utils.validate_parameters`.
- Fixed button type definitions replacing raw `discord.Button` with `discord.ui.Button[Any]`.
- **Database & SQL Schema Alignment**:
  - Fixed `update_group_roles` and `get_group_roles` in `database.py` referencing non-existent `admin_role_id`/`session_role_id` columns; mapped to `group_role_id`.
  - Fixed `update_voice_channel` in `database.py` referencing non-existent `voice_channel_id` column; mapped to `vc_id`.
  - Fixed `get_vc_logs` ambiguous `creator_id` column by prefixing with table qualifier `study_groups.creator_id`.
  - Implemented missing `get_study_group(guild_id: int)` in `database.py`.
  - Made `save_study_group` idempotent using `INSERT OR REPLACE INTO study_groups`.
  - Sanitized `last_reminder_message_id` parameter binding in `database.py:update_checkin_session`.
  - Upgraded `get_user_group` in `database.py` to support `text_id`, `vc_id`, and active-group fallbacks.
- **Permission & Access Control**:
  - Converted `PermissionLevel` in `cogs/manager.py` to `IntEnum` for robust integer comparisons and SQLite parameter binding.
  - Aligned `/set_permission_level` with 5-tier architecture (0: Regular User, 1: Group Member, 2: Group Owner, 3: Guild Manager, 4: Bot Developer).
  - Fixed `utils.py:is_group_creator` which mistakenly compared `group[2]` (name string) instead of `creator_id`.
  - Added superuser bypass for `bot_developer_id` in `utils.py:check_manager` and `is_group_creator`.
- **Voice Channels & Pomodoro**:
  - Fixed `cogs/voice_channels.py` brittle tuple index access by switching to dictionary keys (`vc_id`, `group_role_id`, `text_id`).
  - Fixed `cogs/voice_channels.py:delete_text_channel` erroneously calling `update_voice_channel`.
  - Initialized `PomodoroSession.timer = focus * 60` and safeguarded `timedelta` calculation in `cogs/pomodoro.py:pomodoro_status`.
- **Event Loop & Startup**:
  - Replaced deprecated `bot.loop.create_task` in `cogs/checkin.py` and `cogs/study_groups.py` with `asyncio.create_task` and added `cog_load()` hooks.
  - Fixed `cogs/checkin.py:load_active_sessions_from_db` attempting to read `'text_channel_id'` instead of `'text_id'` from SQLite.
  - Replaced blocking `await asyncio.sleep` in `load_active_sessions_from_db` with a non-blocking background task wrapper.
  - Streamlined `bot.py` command registration: removed redundant `tree.sync()` inside `on_ready()` to prevent connection-time Discord API rate limits.
- **End-to-End Test Suite**:
  - Implemented [`test_file.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/test_file.py) to simulate dummy requests under server `885134444992806962` and user `534168986149978112` for all 16 slash commands and interactive button callbacks with rate limit safety.

### Planned
- MongoDB aggregation pipeline for global cross-guild analytics.
- Voice channel auto-deafening during Pomodoro deep focus intervals.
- Webhook alert integrations for study group milestones.

---

## [1.0.0] - 2026-09-04

### Added
- **AI Agent Readiness & Autonomous Tooling**:
  - Created [`AGENTS.md`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/AGENTS.md) with detailed conventions, async SQLite rules, and offline mock testing patterns.
  - Created [`GEMINI.md`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/GEMINI.md) and [`.agents/rules/cpo_development_rules.md`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/.agents/rules/cpo_development_rules.md) establishing agent constraints and workflows.
  - Created [`docs/LOGGING_STANDARDS.md`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/docs/LOGGING_STANDARDS.md) mandating structured logging and audit standards across all modules.
- **System Architecture & Visual Documentation**:
  - Created comprehensive [`ARCHITECTURE.md`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/ARCHITECTURE.md) with C4 Container Diagrams, State Machines, Data Pipelines, and Security Maps.
  - Created [`KNOWLEDGE_GRAPH.md`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/KNOWLEDGE_GRAPH.md) documenting system nodes, database entity relationships, and command mappings.
  - Created machine-readable [`knowledge_graph.json`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/knowledge_graph.json) for LLM and RAG indexing.
- **Packaging & Testing Infrastructure**:
  - Added [`pyproject.toml`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/pyproject.toml) supporting `pytest`, `pytest-asyncio`, `ruff`, and `mypy`.
  - Added [`requirements-dev.txt`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/requirements-dev.txt) for testing and code quality tools.
  - Added [`.env.example`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/.env.example) configuration template.
  - Added unit test suites in [`tests/`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/tests/):
    - [`test_database.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/tests/test_database.py) (In-memory SQLite CRUD and concurrency tests)
    - [`test_utils.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/tests/test_utils.py) (Duration parsers, time formatting, and productivity calculations)
    - [`test_tasklist.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/tests/test_tasklist.py) (Mock interaction tests for task addition and completion)
- **Core Bot Cogs & Feature Modules**:
  - `CheckinCog` ([`cogs/checkin.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/checkin.py)): Automated standup check-in loops, status tracking buttons (`Present`, `Break`, `Exit`), and strike counts.
  - `StudyGroupCog` ([`cogs/study_groups.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/study_groups.py)): Study group lifecycle, category creation, role binding, capacity management.
  - `Pomodoro` ([`cogs/pomodoro.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/pomodoro.py)): Focus and break state machines with voice channel routing.
  - `Manager` ([`cogs/manager.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/manager.py)): 5-tier permission hierarchy and session limit enforcement.
  - `TaskList` ([`cogs/tasklist.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/tasklist.py)): Personal to-do list tracking.
  - `ProductivityTracker` ([`cogs/productivity_tracker.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/productivity_tracker.py)): Metric calculations and embed views.
  - `VoiceChannels` ([`cogs/voice_channels.py`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/cogs/voice_channels.py)): Temporary voice channel lifecycle management.

### Changed
- Cleaned [`requirements.txt`](file:///c:/Users/Vector/OneDrive/Desktop/CR/CPO/requirements.txt) by removing duplicate packages and invalid standard library entries (`asyncio`, `datetime`).

---

### Agent Protocol for Updating This Changelog
Whenever you modify this codebase:
1. Add new items under the `## [Unreleased]

## [1.0.0-rc.3] - 2026-09-29` section.
2. Group modifications under standard categories: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.
3. Provide clickable file links and concise rationale for changes.
