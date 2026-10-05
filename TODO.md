# TODO

Updated on 2026-10-05 for the antigravity-fix branch. Historical verification counts describe earlier checkpoints.

## Resumed security and persistence scope

- [x] Verify durable setup recovery, guild operation serialization, and ownership rechecks after awaited work.
- [x] Verify private logs under native-authority changes, category propagation, and failed role synchronization.
- [x] Verify async wait cancellation, replacement task ownership, and cog shutdown before SQLite closes.
- [x] Verify non-task activity/settings isolation across guilds; guild-granted developers are Level 4, while only `.env` `BOT_DEVELOPER_ID` is global Level 5 Supreme Commander.
- [x] Persist and hydrate validated check-in settings; keep memory consistent after failed writes and teardown.
- [x] Persist invitation lifecycle: six-minute warning, ten-minute expiry, restart recovery, and recipient/target validation.
- [x] Record invitations, joins, and command authorization/action outcomes in guild-scoped SQLite audit and Discord logs.
- [x] Validate current actor IDs, guild membership, role/tier, ownership, membership, and active targets across all commands and controls.
- [x] Add an optional saved Setup default role and optional creation; require current guild/default-role membership for invitation recipients and apply the selected guild command gate.
- [x] Rebuild `ARCHITECTURE.md` and create `database_architecture.md` with complete Mermaid ER and state machine diagrams.

## Immediate refactoring (Phase 1)

- [x] Correct awaited Discord mocks and keep synchronous `InteractionResponse.is_done()` checks as `MagicMock`.
- [x] Fix the `/create_vc` dictionary lookup regression.
- [x] Handle Discord error 10003 after `/purge_groups` deletes the invocation channel, with a DM result fallback.
- [x] Restore `InteractionResponse.is_done()` calls and test fresh interaction acknowledgement.

## Feature requirements (Phase 2)

- [x] Reject `/resume_pomodoro` when the session is already running.
- [x] Support cross-group task listing through `/task_list all_groups`.
- [x] Implement persisted Speak and Video on/off controls, preserve unrelated overwrites, and roll back after failed database writes.
- [x] Batch task purges and clean matching bot task messages owned by the invoker among the latest 100 messages in the current channel.
- [x] Provide owner-checked Select menus for completion and deletion, with exact row and group checks.
- [x] Send recipient-only invitation DMs with Join/Decline controls, expiry, lifecycle and capacity checks, and serialized admission.
- [ ] Keep all task commands usable in DMs. Add/list/action menus work, and `/task_purge all_tasks:true` works; default DM purge still requires a server or group.
- [x] Make ordinary task and `/create_group` success results public in active group channels and the saved commands channel. Errors, menus, DMs, and cross-group results stay private.
- [x] Combine initial group mentions, status, and controls in one dashboard message.
- [x] Persist `/set_mod_log_channel` and send group creation, ending, and purge event embeds without mentions.
- [x] Implement forced video participation with a default 60-second total wait and a warning for the final 30 seconds; members without a camera or screen sharing are relocated to the saved default VC. Microphone enforcement remains off.

## Technical debt

- [x] Move SQLite I/O off the event loop using `asyncio.to_thread` or an approved async driver.
- [x] Replace placeholder productivity hours with measured, persisted attended Pomodoro focus time. Arbitrary study-group or voice-channel time is not measured.
- [ ] Decompose complex group and Pomodoro handlers into services.
- [x] Include the standalone command matrix in pytest discovery.
- [ ] Add explicit timeouts around external resource provisioning calls.
- [x] Validate `BOT_DEVELOPER_ID` and reject placeholder or invalid values.
- [x] Add persistent retry tracking for Discord resources left behind when group cleanup lacks permissions.
- [x] Recover retained setup channels/categories within the current process, with ownership checks and exact channel-permission rollback. Restart loses recovery handles; staff-role and membership changes remain outside rollback (ARC-08).

## Release audit findings

- [x] Restore standalone success assertions, real task IDs, and mandatory dashboard callback execution.
- [x] Isolate `test_file.py` with an in-memory database and close the bot in `finally`.
- [x] Replace the destructive migration with additive schema changes; preserve rows, legacy roster references, and stable primary keys.
- [x] Cover the earliest schema, historical table names, partially migrated IDs, and repeated startup.
- [x] Remove ended groups from active lookups and remove related Pomodoro aliases during cleanup.
- [x] Check permission denial, malformed selections, missing resources, failed API calls, and persistence rollback.

## Setup and command reply visibility

- [x] Open an invoker-owned private setup wizard on every `/setup` invocation, with existing-category selection and a new-category name modal.
- [x] Keep all settings staged until Save; Cancel and expiry leave the stored configuration unchanged. Reject Cancel while Save is in progress.
- [x] Create or reuse `#cpo-commands` and `#cpo-logs` in the chosen category and save their IDs with the category and default member limit.
- [x] Synchronize new and reused logs channels with category permissions and use the existing moderator activity log destination.
- [x] Make normal slash success replies public in active study-group channels and the exact stored commands channel; keep threads, other channels, DMs, errors, and sensitive results private.

- [x] Show newly added guild managers and bot developers immediately in `/list_managers`, without duplicate people or truncating large lists.

## Consent and session controls

- [x] Add creator-only initial rosters and recipient Join/Decline invitations for groups, check-ins, and Pomodoros.
- [x] Remove voice auto-start and limit attendance, pings, and moves to opted-in Pomodoro participants.
- [x] Validate check-in intervals and Pomodoro stages at 2–240 minutes.
- [x] Add UTC Pomodoro expiry, expiry during pause, and 24-hour renewal with an hour remaining.
- [x] Persist configurable group/Pomodoro default lifetimes in setup; include both in stale-draft checks.
- [x] Route member end requests to the current owner's DM and enforce current ownership/activity on approval.
- [x] Serialize group name allocation/provisioning per guild and retain UUIDs.
- [x] Add private everyday `/help`; accept camera or screen sharing for video requirements.
- [x] Persist and hydrate Pomodoro deadlines, stages, pause state, and consented participants across restarts; agree a persistence schema first.
- [x] Distinguish auto-synced staff grants from explicit grants so permission removals can revoke auto-synced authority safely. Preserve legacy grants as explicit because their original source cannot be inferred.
- [x] Use the contextual five-level profile with Server Member wording and highest-level precedence.
- [x] Synchronize CPO Manager and Bot Developer roles with category/channel access and stored staff grants.
- [x] Resolve group invitations from persisted records, case-insensitive names, and text/voice channel context.
- [x] Remove check-in/Pomodoro buttons from the group dashboard and hide standalone resource maintenance commands.
- [x] Add a default voice channel to `/setup`, create or reuse it under the selected category, and synchronize its permissions with that category. Persist its destination with a backward-compatible schema change after approval. When video participation enforcement removes a member from a study VC, move them to this default VC; handle missing destinations, full channels, and Move Members permission failures. Keep camera or screen sharing acceptable for video. (Microphone enforcement intentionally disabled per user directive).
  - **Completed (2026-10-04)**: `/setup` supports optional `default_vc` parameter; `SetupView` includes interactive `VoiceSelect`, cross-category move notices, and `connect`/`move_members` permission checks on save; `_voice_relocation.py` notifies relocated members via DM on move. 281 tests pass.

## Release verification

- [x] Verify the 2026-10-05 QA fixes: 402 offline tests, zero Mypy errors, Ruff lint/format, and whitespace checks. Independent scoped QA passes; live Discord behavior still requires staging validation.

- [x] Prevent default task-list results from exposing group tasks; require `all_groups: true` for cross-group listing and make cross-group results ephemeral.
- [x] Scope task persistence and default listings by `guild_id`, preventing cross-server task leaks.
- [x] Keep study-group voice channels when the last member leaves; retain explicit deletion paths.
- [x] Provide a `main.py` compatibility launcher for hosting panels whose default startup command targets `python3 main.py`.
- [x] Correct unsupported completion claims and synchronize commands, architecture, and issue documentation.
- [x] Publish `v1.0.0-rc.5` as a prerelease on `Vectorphy/Chief-Productivity-Officer` and verify downloaded packages. [Release](https://github.com/Vectorphy/Chief-Productivity-Officer/releases/tag/v1.0.0-rc.5); [successful CI](https://github.com/Vectorphy/Chief-Productivity-Officer/actions/runs/37234471606). No existing tags moved or release/main merges occurred.
  - Both authorized branches include workflow correction `817cccf` and exact CI pin `10acee4`; release tags/source remain `a01656c` on both repositories. CI verified that tag with 402 tests, zero Mypy errors, and Ruff. Downloads passed digest/integrity and exact membership checks: wheel 21, sdist 26, runtime ZIP 21, GitHub source ZIP 26; package version `1.0.0rc5`. No test/internal/secret/database/cache entries. Remote authorization was restored; exact Python `3.11.17` CI and publication on crispy-octo-happiness were subsequently requested.

- [x] Publish the same immutable `v1.0.0-rc.5` source on `Vectorphy/crispy-octo-happiness`, run validation/build on Python `3.11.17`, and verify downloaded assets. [Release](https://github.com/Vectorphy/crispy-octo-happiness/releases/tag/v1.0.0-rc.5); [successful release CI](https://github.com/Vectorphy/crispy-octo-happiness/actions/runs/37235239110). Both jobs used exact 3.11.17 and tag `a01656c`; 402 tests, Mypy, Ruff, and package checks passed. Downloaded wheel 21 / sdist 26 / runtime 21 / GitHub source 26 passed integrity, digest, version, exact membership, and tagged-source comparisons. Both repositories' general CI matrices passed 3.10, 3.11.17, and 3.12. Existing Chief release preserved.

## Verification history

The checked-TODO audit covers the earlier 53 supported items with corrected scopes; downloaded release verification on both repositories adds two deployment completion ticks. Code and database maps are in `docs/`. The unused study-group backup was removed; published rc.5 packages and GitHub source archive were downloaded and validated with tests retained in Git and excluded from deployment archives.

Earlier handoffs report checkpoints of 68, 107, 224, and 281 tests. These describe past branches or test selections and are not current verification evidence. The rc4 category-based visibility policy was superseded by exact commands-channel and active-group matching. The current evidence audit is in `docs/TODO_AUDIT.md`.

## Comprehensive System Issue Audit (2026-10-05)

Systematic audit of 34 identified operational, concurrency, permission, and architectural issues against the active codebase, tracking resolved progress, partially addressed items, and open backlog tasks.

### Critical Issues (🔴)

- [ ] **🔴 Check-in decorators run before defer — slow checks can exceed Discord’s 3s response limit.**
  - **Status**: OPEN / CRITICAL SLA ISSUE
  - **Evidence**: In `cogs/checkin.py:1502-1504`, `@CheckinGuildSettings.check_user_groups` and `@CheckinGuildSettings.checkin_command_permissions` wrap `start_checkin`. These decorators invoke `await cog._get_guild_settings(...)` which awaits SQLite queries and locks *before* the command callback runs `await acknowledge_interaction(interaction)`. If SQLite is locked or I/O exceeds 3 seconds, Discord interactions time out with HTTP 400/404.
  - **Next Step**: Acknowledge/defer the interaction inside or before the decorator wrapper execution.

- [ ] **🔴 Pomodoro pause/resume lacks proper owner/manager authorization.**
  - **Status**: OPEN / SECURITY DEFECT
  - **Evidence**: In `cogs/pomodoro.py:1292-1329` (`pause_pomodoro`) and `1330-1370` (`resume_pomodoro`), `_resolve_group(interaction)` resolves the group for any member or voice participant, but neither command checks `interaction.user.id == session.owner_id` or `await check_manager(interaction)` (unlike `_end_pomodoro` at line 1244 which enforces owner/manager authorization). Any regular group participant can pause or resume the entire group's session without permission.
  - **Next Step**: Enforce owner/manager authorization checks in `pause_pomodoro` and `resume_pomodoro`, routing unauthorized requests to owner approval or permission denial.

- [ ] **🔴 Pomodoro state has race conditions between timer, buttons, pause/resume/edit.**
  - **Status**: OPEN / CONCURRENCY ISSUE
  - **Evidence**: `cogs/pomodoro.py` maintains mutable state on `PomodoroSession` (`is_paused`, `current_stage`, `timer`, `cycles`, `present_members`) without an `asyncio.Lock` per session. The background loop `run_timer` runs continuously while slash commands (`pause_pomodoro`, `resume_pomodoro`, `edit_pomodoro`) and button callbacks mutate these fields concurrently across await points, leading to lost updates or corrupted cycle transitions.
  - **Next Step**: Introduce an `asyncio.Lock` per session protecting state mutations across `run_timer`, commands, and UI views.

- [ ] **🔴 Two simultaneous /start_pomodoro calls can create duplicate sessions.**
  - **Status**: OPEN / CONCURRENCY RACE
  - **Evidence**: In `cogs/pomodoro.py:950-1030`, `start_pomodoro` checks `existing_session = self._get_session(group)` at line 974, but does not acquire a lock before awaiting Discord API operations (`category.create_voice_channel`, `fetch_members_of_group`, sending invitations). Two concurrent invocations both observe `existing_session is None`, await external API calls, and subsequently register duplicate sessions in `self.sessions`.
  - **Next Step**: Serialize session creation per group/guild using an `asyncio.Lock` or check-and-reserve sentinel prior to awaiting channel creation and invitations.

- [x] **🔴 Check-in reminder tasks are untracked and can leak/duplicate after lifecycle changes.**
  - **Status**: RESOLVED / MITIGATED
  - **Evidence**: `_reminder_tasks: dict[str, asyncio.Task[None]]` was implemented in `cogs/checkin.py:1350`, tracked in `_start_reminders` (line 1371), cleaned up in `finally` (line 1368), and cancelled/gathered in `cog_unload` (line 1377). Verified by `tests/test_async_lifecycle.py:133-159`. Outstanding debt: explicitly cancel `_reminder_tasks.pop(session_id, None)` during mid-run manual session teardown.

- [x] **🔴 Check-in asyncio.wait() leaves losing tasks running instead of cancelling them.**
  - **Status**: RESOLVED
  - **Evidence**: Legacy untracked `asyncio.wait(..., return_when=FIRST_COMPLETED)` patterns were refactored away. Check-in reminders now use `await asyncio.wait_for(self.end_session_event.wait(), timeout=...)` in `cogs/checkin.py:818`, and task cleanup cleanly cancels and gathers tasks with `asyncio.gather(..., return_exceptions=True)`.

- [x] **🔴 Check-in reminder DB updates can race due to unawaited create_task().**
  - **Status**: RESOLVED
  - **Evidence**: In `cogs/checkin.py:861-869`, reminder state persistence is directly awaited via `await self.db.update_checkin_session(...)`, which in turn executes inside `async with self.lock:` in `database.py:1159`. No unawaited background `create_task()` calls update reminder DB state.

- [x] **🔴 Check-in settings are memory-only and disappear after bot restart.**
  - **Status**: RESOLVED
  - **Evidence**: Additive SQLite table `checkin_guild_settings` was implemented in `database.py:234`. `CheckinCog.cog_load()` iterates stored guild settings and hydrates `self.guild_settings` on startup (`cogs/checkin.py:1382-1389`), and `_commit_checkin_settings` writes changes to DB before updating in-memory cache. Verified by `tests/test_guild_persistence.py`.

- [ ] **🔴 Configured Check-in min/max duration is ignored when creating sessions.**
  - **Status**: OPEN / LOGIC DEFECT
  - **Evidence**: In `cogs/checkin.py:1522-1524`, `/checkin` enforces hardcoded limits `120 <= duration_seconds <= 14400`, completely ignoring `guild_settings.min_duration` and `guild_settings.max_duration` configured by guild administrators via `/settings_checkin`.
  - **Next Step**: Read `guild_settings.min_duration` and `guild_settings.max_duration` in `start_checkin` and validate `duration_seconds` against the configured guild bounds.

- [ ] **🔴 Study Groups aren’t fully hydrated on restart, breaking automatic lifecycle handling.**
  - **Status**: OPEN / LIFECYCLE DEFECT
  - **Evidence**: `StudyGroupCog` lacks a `cog_load()` or `on_ready()` hook to load active study groups from the database on bot reboot. `StudyGroup` instances are only loaded on-demand when commands are invoked. As a result, background monitors (`check_end_condition`) and automatic expiration / inactivity handling do not run after a restart until an explicit interaction touches the group.
  - **Next Step**: Add startup hydration in `StudyGroupCog.cog_load()` that queries `fetch_active_study_groups()` and spawns `_start_group_monitor(study_group)` for all active groups.

- [ ] **🔴 Study Group creation isn’t transactional; partial failures can leave orphan roles/channels/VCs.**
  - **Status**: OPEN / RESOURCE LEAK RISK
  - **Evidence**: In `cogs/study_groups.py:220-255`, `setup_group_resources` creates a Discord role, text channel, and voice channel sequentially. If voice channel creation or member role assignment fails with an exception, the created role and text channel are not rolled back or deleted, leaving orphan Discord resources.
  - **Next Step**: Implement a try/except rollback block in `setup_group_resources` that tracks created resource IDs and deletes them if any subsequent setup step fails.

- [ ] **🔴 Group context can silently select the wrong group when a user belongs to multiple groups.**
  - **Status**: OPEN / CONTEXT RESOLUTION DEFECT
  - **Evidence**: In `database.py:1303-1316`, `get_user_group` has a fallback when `channel_id` does not match: it executes `SELECT * FROM study_groups ... WHERE user_id = ? AND active = 1 ORDER BY id DESC LIMIT 1`. If a user belongs to multiple active study groups and invokes a command in a non-group channel (e.g. `#cpo-commands` or DM), it arbitrarily selects the newest group, silently executing actions on the wrong group.
  - **Next Step**: Disallow ambiguous fallback when user belongs to >1 active group; require an explicit group name or selection prompt when invoked outside group channels.

- [x] **🔴 VC commands exist in code but are explicitly removed from the public command tree.**
  - **Status**: RESOLVED / INTENDED BEHAVIOR
  - **Evidence**: In `cogs/voice_channels.py:261-263`, `bot.tree.remove_command(command.name)` removes `create_vc`, `delete_vc`, `delete_role`, and `delete_text_channel` from the public application command tree. This was explicitly requested in product specifications to deprecate standalone resource maintenance commands in favor of unified `/setup` and `/create_group`.

---

### Major Issues (🟠)

- [ ] **🟠 Pomodoro required VC deletion can silently cause everyone to receive zero focus credit.**
  - **Status**: OPEN / TRACKED DEFECT
  - **Evidence**: In `cogs/pomodoro.py:1469-1476`, focus time calculation checks `if session.require_vc: voice = guild.get_channel(session.vc_id)`. If the VC is deleted mid-session, `voice` is `None` or not found, causing `eligible` members to be empty. The timer continues running normally, but all participants silently accumulate 0 focus seconds.
  - **Next Step**: Detect deleted VC in `run_timer`, pause the session or alert the group, and either offer VC recreation or fallback to text-only mode rather than silently discarding focus credit.

- [ ] **🟠 VC recreation may inherit category permissions instead of explicit group-only permissions.**
  - **Status**: OPEN / PRIVACY LEAK RISK
  - **Evidence**: In `cogs/voice_channels.py:63-65` and `cogs/pomodoro.py:1020-1025`, recreated voice channels are created directly under the category without passing explicit `overwrites` (overriding `@everyone` View/Connect to False and granting only `group_role_id`). As a result, the voice channel inherits default category permissions, potentially exposing private study sessions to unauthorized server members.
  - **Next Step**: Explicitly construct permission overwrites denying `@everyone` and allowing `group_role_id` whenever a voice channel is created or recreated.

- [ ] **🟠 Missing Move Members permission isn’t handled cleanly before attempting user moves.**
  - **Status**: OPEN / ERROR HANDLING GAP
  - **Evidence**: In `cogs/pomodoro.py:456` and `1041`, `member.move_to(destination)` is invoked without checking `guild.me.guild_permissions.move_members`. While wrapped in generic `try/except Exception`, it logs unnecessary error noise and fails without notifying the user why they weren't moved.
  - **Next Step**: Check `guild.me.guild_permissions.move_members` before calling `move_to`, emitting an informative notice if the bot lacks move permissions.

- [ ] **🟠 Check-in sessions are linked to groups via channel IDs instead of explicit group IDs.**
  - **Status**: OPEN / ARCHITECTURAL DEBT
  - **Evidence**: In `database.py:180` (`checkin_sessions`), records store `text_id INTEGER` rather than an explicit foreign key `group_id TEXT`. Cross-cog lookups in `cogs/study_groups.py:804, 1547` iterate active check-in sessions matching `s.text_id == self.text_id`, coupling check-ins to channel IDs and breaking if channels are renamed, recreated, or decoupled from groups.
  - **Next Step**: Add an additive, nullable `group_id` column to `checkin_sessions` and link sessions directly by group UUID.

- [ ] **🟠 Check-in join DB/memory updates aren’t transactional and can desync on partial failure.**
  - **Status**: PARTIALLY ADDRESSED / OPEN
  - **Evidence**: `self.join_lock` was added in `cogs/checkin.py:1060`, but DB mutation (`add_or_update_checkin_member`) and in-memory lists (`member_statuses`, `member_ids`) are updated sequentially. If embed update or a network call fails, or in invitations if admission fails after DB write, state can desync between memory and SQLite.
  - **Next Step**: Structure join mutations so that in-memory collections roll back if subsequent operations fail, or hydrate strictly from committed DB state.

- [ ] **🟠 Study Group/Pomodoro cleanup can race with active timers and interactions.**
  - **Status**: OPEN / CONCURRENCY HAZARD
  - **Evidence**: During group termination (`end_group`) or Pomodoro shutdown (`end_pomodoro`), Discord channel/role deletions and DB status updates take several seconds. During this window, background loops (`run_timer`, `check_end_condition`) and active UI views can still process events and attempt mutations on resources currently being destroyed.
  - **Next Step**: Set an immediate `session.is_terminating` / `active = False` flag and cancel running background tasks before awaiting Discord channel and role deletions.

- [ ] **🟠 /create_group max_members has no proper upper bound.**
  - **Status**: OPEN / INPUT VALIDATION DEFECT
  - **Evidence**: In `cogs/study_groups.py:2111`, validation only checks `if max_members < 1:`. A user can input arbitrarily large integers (e.g. `max_members = 1000000`). While Discord VC limits are clamped to 99, the study group object and database retain the unbounded value.
  - **Next Step**: Enforce an upper bound (e.g. `1 <= max_members <= 99` or server-configured maximum) in parameter validation.

- [ ] **🟠 /create_group mentions is still required despite intended optional behavior.**
  - **Status**: OPEN / COMMAND SIGNATURE DEFECT
  - **Evidence**: In `cogs/study_groups.py:2065`, `mentions: str` is declared without `= None` or `Optional[str]`. Discord's slash command schema treats this as a required parameter, forcing users to input mentions even though the command description states "(optional)".
  - **Next Step**: Update command signature to `mentions: Optional[str] = None` and handle empty string / None gracefully.

- [ ] **🟠 Check-in settings accept poorly bounded numeric values and free-form permission mode.**
  - **Status**: OPEN / VALIDATION DEFECT
  - **Evidence**: In `cogs/checkin.py:1625-1657`, `/settings_checkin` validates `min_duration` and `max_duration`, but leaves `max_members`, `max_absences`, `max_breaks`, and `max_user_sessions` without lower/upper bounds (allowing negative or excessive numbers), and accepts arbitrary strings for `permission_mode` instead of restricting to `"ALLOW"` / `"DENY"`.
  - **Next Step**: Add range checks for all numeric parameters and constrain `permission_mode` using `app_commands.choices`.

- [x] **🟠 Group/server permission levels are mixed conceptually despite having different scopes.**
  - **Status**: RESOLVED IN PART / DOCUMENTED MODEL
  - **Evidence**: Formalized in 6-Tier authorization model (Tiers 0–5) in `cogs/manager.py` and `KNOWLEDGE_GRAPH.md`. However, group-scoped roles (Tier 1: Group Member, Tier 2: Group Owner) and guild-scoped roles (Tier 3: Guild Manager, Tier 4: Bot Developer) remain flattened into a single linear integer hierarchy, which creates conceptual ambiguity when evaluating commands that operate outside of group contexts.
  - **Next Step**: Decouple group-scoped permissions from server-wide managerial authority checks.

- [ ] **🟠 Raw exception text can still be exposed to users in some error paths.**
  - **Status**: OPEN / INFORMATION DISCLOSURE RISK
  - **Evidence**: Multiple user-facing command responses embed raw exception strings: `cogs/study_groups.py:277` (`f"Failed to send messages for StudyGroup '{self.name}': {e}"`), `cogs/manager.py:565` (`f"Failed to sync commands: {e}"`), and `cogs/checkin.py:1134` (`f"Failed to leave session. {str(e)}"`). This risks leaking internal paths, SQL details, or stack frames to Discord users.
  - **Next Step**: Replace `{e}` / `{str(e)}` in user-facing replies with sanitized, generic error messages and log the detailed exception to `logger.exception`.

- [ ] **🟠 Broad except Exception handlers can hide programming/runtime failures.**
  - **Status**: OPEN / CODE QUALITY DEBT
  - **Evidence**: Throughout `cogs/checkin.py`, `cogs/study_groups.py`, and `cogs/pomodoro.py`, numerous top-level callbacks use broad `except Exception:` blocks that catch programming bugs (`AttributeError`, `KeyError`, `TypeError`) alongside transient API errors, masking defects and preventing proper crash telemetry.
  - **Next Step**: Narrow exception clauses to specific expected errors (`discord.HTTPException`, `discord.Forbidden`, `sqlite3.Error`, `ValueError`) and let unexpected runtime exceptions bubble to global error handlers.

- [x] **🟠 User-facing "Go away peasent" permission errors are unsuitable for production.**
  - **Status**: TRACKED / USER SPECIFICATION
  - **Evidence**: Multiple permission denial checks throughout `cogs/manager.py`, `cogs/study_groups.py`, `cogs/pomodoro.py`, and `bot.py` return `"Go away peasent"` (including typo "peasent"). Tests explicitly assert this exact string (`tests/test_manager_roles_and_perms.py:123`). While tracked as unprofessional for production environments, it is preserved strictly per user directive.
  - **Next Step**: Retain until product owner explicitly approves migration to standard message (e.g. "You do not have permission to execute this command.").

- [ ] **🟠 Background task exceptions lack consistent ownership/telemetry.**
  - **Status**: OPEN / TELEMETRY GAP
  - **Evidence**: Background loops (`run_checkin_reminders`, `check_end_condition`, `run_timer`, video enforcement tasks) log errors to standard logger, but do not record telemetry into `command_audit_events` or notify guild managers of unrecoverable loop termination.
  - **Next Step**: Implement a centralized task supervisor or error callback that logs structured incident records when background tasks terminate unexpectedly.

- [ ] **🟠 Lock registries can grow indefinitely without lifecycle cleanup.**
  - **Status**: OPEN / RESOURCE LEAK RISK
  - **Evidence**: Dictionaries storing dynamic locks (`self.locks` in `cogs/_invitations.py:406` keyed by UUID `invitation_id`, `_creation_locks` in `cogs/study_groups.py`, `_settings_locks` in `cogs/checkin.py`) use `setdefault()` without eviction. For invitations, every created invitation permanently adds an entry to `self.locks`, leaking memory over long runtimes.
  - **Next Step**: Evict locks from dictionaries upon completion of the protected lifecycle (e.g. `self.locks.pop(invitation_id, None)` after invitation reaches a terminal state).

- [ ] **🟠 Group creation uses a guild-wide lock, unnecessarily serializing unrelated creations.**
  - **Status**: OPEN / DESIGN TRADEOFF
  - **Evidence**: In `cogs/study_groups.py:2076`, `async with self._creation_locks.setdefault(interaction.guild.id, asyncio.Lock()):` serializes all `/create_group` commands across the entire guild. While preventing name collisions and role creation races, it creates an unnecessary bottleneck for large servers with concurrent study groups.
  - **Next Step**: Scope creation locks to normalized group names or use optimistic concurrency with DB unique constraints instead of serializing the entire guild.

- [ ] **🟠 Check-in + Pomodoro simultaneous attendance has no defined cross-module consistency rule.**
  - **Status**: OPEN / SPECIFICATION GAP
  - **Evidence**: Check-in tracks presence/breaks independently from Pomodoro focus stages. A user can be marked "Present" in Pomodoro focus while concurrently marked "Break" or "Exited" in Check-in, or vice-versa. No precedence or cross-module synchronization logic exists.
  - **Next Step**: Define product specification for cross-module attendance and implement shared status listener if synchronization is desired.

- [x] **🟠 Delayed UI actions need authoritative state revalidation before committing mutations.**
  - **Status**: PARTIALLY RESOLVED / TRACKED
  - **Evidence**: Progress was made in `cogs/_invitations.py:720-750` by implementing CAS transitions (`pending` -> `accepting` -> `accepted`) and revalidating capacity, guild membership, and default roles before committing mutations. However, older interaction views (`PomodoroPresenceView`, `CheckinPresenceView`) still mutate in-memory state without authoritative DB revalidation.
  - **Next Step**: Retrofit remaining legacy UI views to follow the CAS and state revalidation pattern established in `_invitations.py`.

- [x] **🟠 Missing automated tests for concurrency, restart recovery, stale UI, and partial failures.**
  - **Status**: PARTIALLY RESOLVED / TRACKED
  - **Evidence**: The repository now contains 479 tests covering restart recovery (`test_pomodoro_recovery.py`, `test_guild_persistence.py`), async lifecycle (`test_async_lifecycle.py`), and cleanup retries (`test_cleanup_retries.py`). However, real multi-client concurrent Discord gateway interactions, distributed race conditions, and live latency simulation remain untested outside unit mocks.
  - **Next Step**: Add concurrency stress tests with simulated concurrent coroutines hitting shared command and session endpoints.

- [ ] **🟠 No integration tests verify every interaction acknowledges within Discord’s 3s SLA.**
  - **Status**: OPEN / TEST DEBT
  - **Evidence**: While tests verify whether `acknowledge_interaction` or `response.defer` was invoked, no test measures actual execution latency or asserts that all code paths prior to deferral execute in < 3.0 seconds under simulated slow database queries or network delays.
  - **Next Step**: Introduce an interaction test wrapper that measures elapsed time to initial response/deferral and asserts `< 3.0s`.

- [x] **🟠 Error telemetry lacks consistent incident IDs and structured lifecycle context.**
  - **Status**: PARTIALLY RESOLVED / TRACKED
  - **Evidence**: Progress was made by adding `command_audit_events` in `cogs/_audit.py` to log structured authorization and command outcomes (`actor_id`, `actor_tier`, `action`, `outcome`). However, general application errors do not generate unique `incident_id` UUIDs returned to users and logged in telemetry for log correlation.
  - **Next Step**: Standardize an error reporting utility that generates an `incident_id`, logs full context, and provides users with a reference ID.
