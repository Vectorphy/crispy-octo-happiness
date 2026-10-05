# TODO

## Exhaustive audit — source review complete; deployment blocked

- [x] Verify current unchanged runtime offline: 484 full tests, 134 focused tests, zero Mypy errors in 43 files, Ruff lint/format and whitespace pass. This checks those scenarios only.
- [x] Complete source review: 1008/1008 function bodies in 49 executable files, 50/50 lambdas and 83/83 counted module statements. Source review and passing offline tests do not establish live integration or deployment readiness. Detailed semantic mapping remains a mapper handoff task.
- [ ] INV-01: Fail required-role invitation eligibility closed when settings lookup fails.
- [ ] INV-02: Reject invitation admission after failed/rejected persistent transition; test real DAL failure and adverse ordering.
- [ ] INV-03: Restore pending invitation views and warning/expiration tasks on restart.
- [ ] AUD-01: Implement and verify the promised command/control audit coverage beyond invitations.
- [ ] VOTE-05: Validate same-guild group resolution and authority in all votekick paths.
- [ ] CHECK-01: Persist owner transfer and revalidate selection authorization/lifecycle.
- [ ] POMO-02 / SEC-09: Propagate persistence failure or return explicit failure so acceptance does not report memory-only success.
- [ ] BUILD-01: Supply an authorized build environment, build/validate final-source archives, and exercise current-source CI. Offline build attempt failed: setuptools.build_meta unavailable.

- [ ] GROUP-01: Roll back partial Discord group provisioning.
- [ ] AUTH-01/AUTH-02: Fail closed without Manager and protect higher-tier grants.
- [ ] UI-01/UI-02: Bound embed characters and fields.
- [ ] NOTIFY-01: Handle SQLite manager rows correctly.

Updated on 2026-10-05 for the antigravity-fix branch. Previous checkpoint was `codex checkpoint` (`8e9e298`), followed by intermediate `antigravty checkpoint` (`f9a3981`). Current uncommitted Antigravity changes have evidence-scoped offline verification; reopened defects and unsupported claims remain pending. The final exhaustive audit report governs readiness. Historical verification counts describe earlier checkpoints.

## Resumed security and persistence scope

### Independent audit blockers — 2026-10-05

- [ ] VOTE-01: Reconcile end-group votes with current membership; cover initiator/voter departure before the deciding vote.
- [ ] VOTE-02: Preserve persisted and in-memory ownership/membership on failed owner transfer during votekick; cover retry and successful transfer.
- [ ] VOTE-03: Recheck staff immunity at votekick execution; cover target promotion during voting and the immediate-vote path.
- [ ] SEC-10: Enforce the saved invite-only admission requirement for `/join_group`, including database fallback.
- [ ] VOTE-04: Return and check a removal outcome; do not announce success after role/database removal failure. Define and verify session/voice cleanup expected on a group kick.
- [ ] POMO-01: Restore a supported recovery route for dropped ordinary participants and correct the UI instructions.
- [ ] Reconcile lock-coverage and DATA-02 claims with evidence, and resolve public-command signature authorization before release.
- [ ] Build and validate packages from the final verified source and run current-source Python 3.11.17 CI; default rc.5 dispatch targets older immutable source.
- [ ] After fixes, run affected QA sequentially and repeat final checks against the resulting source before declaring deployment readiness.

The current dirty tree passes 484 full-suite tests and 134 focused tests, Mypy, Ruff lint/format, and whitespace checks, but the adverse-order audit reproduced voting defects. Historical checked items below do not override these blockers.

- [x] Verify durable setup recovery, guild operation serialization, and ownership rechecks after awaited work.
- [x] Verify private logs under native-authority changes, category propagation, and failed role synchronization.
- [x] Verify async wait cancellation, replacement task ownership, and cog shutdown before SQLite closes.
- [x] Verify non-task activity/settings isolation across guilds; guild-granted developers are Level 4, while only `.env` `BOT_DEVELOPER_ID` is global Level 5 Supreme Commander.
- [x] Persist and hydrate validated check-in settings; keep memory consistent after failed writes and teardown.
- [ ] Persist invitation lifecycle: six-minute warning, ten-minute expiry, restart recovery, and recipient/target validation.
- [ ] Record invitations, joins, and command authorization/action outcomes in guild-scoped SQLite audit and Discord logs.
- [ ] Validate current actor IDs, guild membership, role/tier, ownership, membership, and active targets across all commands and controls; AUTH-01/AUTH-02/VOTE-05 remain open.
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
- [x] Keep all task commands usable in DMs. Add/list/action menus work, and `/task_purge all_tasks:true` works; default DM purge correctly purges personal tasks. (VERIFIED OFFLINE for personal DM purge scope; explicit all-task behavior tested)
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

- [x] **🔴 Check-in decorators run before defer — slow checks can exceed Discord’s 3s response limit.**
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Evidence**: Added `await acknowledge_interaction(interaction)` before DB reads in `@CheckinGuildSettings.checkin_command_permissions` and `@CheckinGuildSettings.check_user_groups`. Guarded `start_checkin` with `if not interaction.response.is_done():` and prevented double acknowledgements in `acknowledge_interaction`.

- [x] **🔴 Pomodoro pause/resume lacks proper owner/manager authorization.**
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Evidence**: Enforced creator/owner and Level 3+ manager check (`check_manager(interaction)`) in `/start_pomodoro`, `/pause_pomodoro`, and `/resume_pomodoro` in `cogs/pomodoro.py`, denying unauthorized users with `"Go away peasent"`.

- [x] **🔴 Pomodoro state has race conditions between timer, buttons, pause/resume/edit.**
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Evidence**: Added `self.lock = asyncio.Lock()` to `PomodoroSession.__init__` and synchronized timer stage transitions, elapsed tick deductions, cycle advances, pause, resume, and edit operations under `async with session.lock:`.

- [x] **🔴 Two simultaneous /start_pomodoro calls can create duplicate sessions.**
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Evidence**: Added per-group creation locks `self._start_locks: Dict[str, asyncio.Lock]` in `Pomodoro.__init__`, serialized session provisioning in `start_pomodoro`, and wrapped `self.sessions` registry updates inside `async with self._runtime_lock:`.

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

- [x] **🟠 /create_group max_members has no proper upper bound.**
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Evidence**: Enforced bounds `1 <= max_members <= 99` in `cogs/study_groups.py:2111` with user error reply "The group member limit must be between 1 and 99."

- [x] **🟠 /create_group mentions is still required despite intended optional behavior.**
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Evidence**: Changed `mentions: Optional[str] = None` in `cogs/study_groups.py:2065` and `_create_group_locked`, parsing mentions gracefully when omitted.

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

---

## Function-Level Audit Findings (2026-10-05)

Exhaustive function-by-function audit across all source files. Every item below is a new finding not previously tracked above. Files audited: `utils.py`, `cogs/study_groups.py` (full 2801 lines), `cogs/pomodoro.py`, `cogs/checkin.py`, `cogs/manager.py`, `cogs/_session_controls.py`.

---

### Critical (🔴) — New Findings

- [x] **🔴 `eligible` set has operator-precedence bug — dropped-out members still accrue focus seconds.**
  - **Location**: `cogs/pomodoro.py:1468`
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Root Cause**: `session.participants & session.present_members - session.dropped_out_members` — Python evaluates `-` before `&`. Actual result: `participants & (present_members - dropped_out_members)`. Members who dropped out but remain in `present_members` still intersect with `participants` and receive focus credit.
  - **Fix**: Wrapped intersection in parentheses: `(session.participants & session.present_members) - session.dropped_out_members`.

- [x] **🔴 `/start_pomodoro` — any group member can create and own a session (no ownership gate).**
  - **Location**: `cogs/pomodoro.py:964` — after `_resolve_group`, no permission check occurs before session creation.
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Fix**: Gated on `interaction.user.id in (group["creator_id"], group["owner_id"]) or await check_manager(interaction)`.

- [x] **🔴 `run_timer` mutates session state without a per-session lock.**
  - **Location**: `cogs/pomodoro.py:1415–1536` — `run_timer` (1-second loop) and command handlers (`pause_pomodoro`, `resume_pomodoro`, `edit_pomodoro`) mutate `session.timer`, `session.is_paused`, `session.cycles`, `session.present_members`, `session.dropped_out_members` without synchronization.
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Fix**: Added `self.lock = asyncio.Lock()` to `PomodoroSession.__init__`; acquired in `run_timer` per-session and in mutating operations.

- [x] **🔴 Two concurrent `/start_pomodoro` calls can create duplicate sessions.**
  - **Location**: `cogs/pomodoro.py:974` — `existing_session` check is not protected by a lock before the first `await` (Discord channel creation). Two concurrent calls both see `None` and register duplicate sessions.
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Fix**: Serialized per-group session creation with `_start_locks` `asyncio.Lock` per `group_id`.

---

### Major (🟠) — New Findings

- [x] **🟠 `start_break_callback` resets absence counter to hardcoded `1` instead of incrementing.**
  - **Location**: `cogs/checkin.py:1023`
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Root Cause**: `self.member_statuses[user_id][MemberStatusKey.ABSENCES.value] = 1` — any number of prior absences is discarded.
  - **Fix**: Increment existing absences: `current = self.member_statuses[user_id].get(MemberStatusKey.ABSENCES.value, 0); self.member_statuses[user_id][MemberStatusKey.ABSENCES.value] = current + 1`.

- [x] **🟠 `mark_present_callback` and `start_break_callback` not locked against `_run_reminder_cycle`.**
  - **Location**: `cogs/checkin.py:914–1052` — reminder cycle holds `join_lock` while deciding who to ping; button callbacks do not acquire `join_lock`, so a member can click Present concurrently while the reminder picks them as absent.
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Fix**: Acquired `self.join_lock` inside both button callbacks.

- [x] **🟠 Voice channel created before DB update with no rollback on failure.**
  - **Location**: `cogs/pomodoro.py:1020–1024` — `category.create_voice_channel(...)` succeeds, then `update_voice_channel(...)` may raise; the orphaned VC is never deleted.
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Fix**: Wrapped in `try/except`; `await voice_channel.delete(...)` on DB failure before returning.

- [x] **🟠 `/pause_pomodoro` and `/resume_pomodoro` have no ownership / manager gate.**
  - **Location**: `cogs/pomodoro.py:1292–1384` — any group member can pause or resume the shared session.
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Fix**: Added creator/owner and Level 3+ manager check denying unauthorized users with `"Go away peasent"`.

- [x] **🟠 `start_pomodoro` writes `self.sessions` without `_runtime_lock`.**
  - **Location**: `cogs/pomodoro.py:1083–1084` — `for k in keys_to_set: self.sessions[k] = session` is outside the lock, concurrent with `_remove_session` / `load_active_sessions_from_db` that use `async with self._runtime_lock`.
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Fix**: Wrapped session registration in `async with self._runtime_lock:`.

- [ ] **🟠 `extend_duration_callback` extends by a hardcoded 1 hour with no user input.**
  - **Location**: `cogs/study_groups.py:1119` — `extra_time: int = 3600` is hardcoded with a comment "Example: Extend by 1 hour". Users cannot choose the extension amount.
  - **Fix**: Present a modal or selection for extension time (e.g., 30m / 1h / 2h).

- [ ] **🟠 `rename_group_callback` references `old_name` from outer scope in inner `on_submit` before it is defined.**
  - **Location**: `cogs/study_groups.py:1068, 1073, 1078` — `logger.info(f"Role '{old_name} Group' renamed...")` uses `old_name` from the outer `rename_group_callback` scope. If `on_submit` is invoked after the outer call stack is gone, `old_name` is captured via closure correctly. However, `self.study_group.name = new_name` is set at line 1059 *before* the Discord edits; if a Discord API call fails, `self.study_group.name` is already updated in memory but the channels are not renamed — desync between in-memory name and channel names.
  - **Fix**: Assign `self.study_group.name = new_name` only after all Discord edits succeed.

- [ ] **🟠 `send_welcome_message` has an unbound variable in the `except` handler.**
  - **Location**: `cogs/study_groups.py:664–681` — if `self.guild.get_channel(self.text_id)` returns `None`, `send_channel.send(...)` raises `AttributeError`, and the `except` block then accesses `send_channel.name`, raising a second `AttributeError` that shadows the first.
  - **Fix**: Guard with `if not isinstance(send_channel, discord.TextChannel): return` before use.

- [ ] **🟠 `clear_group_data` logs `self.name` after setting it to `None`.**
  - **Location**: `cogs/study_groups.py:1608` — `logger.info(f"Group data cleared for group '{self.name}'.")` appears after `self.name = None` (line 1576), always logging `None`.
  - **Fix**: Capture `name = self.name` before nulling it.

- [ ] **🟠 `_end_group` sets `self.active = False` inside `self.membership_lock` but Pomodoro cleanup runs before acquiring that lock.**
  - **Location**: `cogs/study_groups.py:1434–1445` — Pomodoro session removal (lines 1435–1442) runs before `self.active = False` is set (line 1445). A concurrent Pomodoro tick between these two lines can still process a session that is logically being torn down.
  - **Fix**: Set `self.active = False` first, before removing associated sessions.

- [ ] **🟠 `_remove_session` raises on `_retire_runtime` failure, leaving `session.runtime_active = True` without re-adding it to the timer loop.**
  - **Location**: `cogs/pomodoro.py:811–834` — on `_retire_runtime` error, `session.runtime_active` is restored to `True` but the session is no longer serviced by `run_timer` (it was removed from the snapshot). The session leaks in `self.sessions` indefinitely.
  - **Fix**: Separate the retire-failure path from the save-failure path; only block re-entry if save fails.

- [ ] **🟠 `on_ready` in `CheckinCog` runs the full DB load on every `READY` event (including gateway resumes).**
  - **Location**: `cogs/checkin.py:1404–1408` — each bot reconnect triggers `load_active_sessions_from_db`, which queries the full session table even when sessions are already in memory.
  - **Fix**: Guard with a `_sessions_loaded: bool` flag (set on first successful load, reset on `cog_unload`).

- [ ] **🟠 `VCFunctions` inner class is dead code with placeholder implementations.**
  - **Location**: `cogs/study_groups.py:1612–1652` — `VCFunctions.create_vc`, `delete_vc`, `update_vc_permissions`, `set_speak`, `set_video`, `force_video_timer` all contain pseudocode comments and `pass` bodies. The class is instantiated nowhere and serves no runtime purpose.
  - **Next Step**: Remove the class or replace its stubs with the actual production implementations already present in `StudyGroup._set_voice_permission` and `_enforce_video`.

- [ ] **🟠 `leave_group` DB-fallback path silently suppresses `remove_roles` errors.**
  - **Location**: `cogs/study_groups.py:2669–2670` — bare `except: pass` on role removal after the DB record is already deleted. If role removal fails, the member still has the role on Discord but is not in the DB.
  - **Fix**: Log the exception; attempt pending-cleanup record.

- [x] **🟠 `create_group` — `mentions` parameter is declared as required `str` instead of `Optional[str] = None`.**
  - **Location**: `cogs/study_groups.py:2065` — `mentions: str` has no default. Discord treats it as a required slash command option, contradicting the `(optional)` in the `describe` decorator.
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Fix**: `mentions: Optional[str] = None`.

- [x] **🟠 `create_group` — `max_members` has no upper bound (only lower bound `< 1` checked).**
  - **Location**: `cogs/study_groups.py:2111` — values like `max_members=1000000` are accepted and written to the DB.
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Fix**: Enforced `1 <= max_members <= 99`.

- [ ] **🟠 `list_groups` — N+1 query: one DB call per active group to fetch member counts.**
  - **Location**: `cogs/study_groups.py:2498` — `await self.bot.db.fetch_members_of_group(g["group_id"])` is called inside a `for` loop over all active groups. For a server with 20 groups this is 20 sequential queries.
  - **Fix**: Add a bulk `get_member_counts_for_groups(guild_id)` DAL method returning a `{group_id: count}` dict.

- [ ] **🟠 `invite_to_group` acquires the guild-wide `_creation_locks` just to resolve a group — over-broad lock.**
  - **Location**: `cogs/study_groups.py:2698` — `_resolve_invite_group` only reads from `active_study_groups` and the DB; it does not mutate state. Wrapping it in the guild creation lock unnecessarily serializes all invitations with group creation.
  - **Fix**: Remove the lock from `invite_to_group`; add a narrower per-group lock inside `send_invite` if race protection is needed.

---

### Minor (🟡) — New Findings

- [ ] **🟡 `remove_member` dead guard `len(self.member_ids) < 0`.**
  - **Location**: `cogs/study_groups.py:419` — list length is never negative; the intended check is `== 0`. The empty-list fast-path never fires.
  - **Fix**: `if len(self.member_ids) == 0:`.

- [ ] **🟡 `validate_parameters` exposes raw `Forbidden` and `HTTPException` text to users.**
  - **Location**: `utils.py:297–309` — `f"Permission error occurred during validation: {forbidden_e}"` and `f"HTTP error occurred during validation: {http_e}"` embed raw exception text in user-facing responses.
  - **Fix**: Use generic messages; log the exception with `logger.exception`.

- [ ] **🟡 `parse_seconds_to_hms` calls `logger.debug` on every invocation.**
  - **Location**: `utils.py:126` — debug logging a pure-format helper on every call (called in the 1-second `run_timer` loop and in embed refreshes) generates excessive log volume in debug mode.
  - **Fix**: Remove the `logger.debug` call; the function is deterministic and needs no tracing.

- [ ] **🟡 `parse_mentions` always includes the interaction author even for explicit mention lists.**
  - **Location**: `utils.py:173–175` — the author is appended unconditionally. For commands that explicitly build a mentions list excluding the author (e.g., for "invite others only"), the author is silently added.
  - **Fix**: Make author inclusion opt-in via a parameter: `include_author: bool = True`.

- [ ] **🟡 `ProductivityService.calculate_efficiency` is not used anywhere outside tests.**
  - **Location**: `utils.py:450–453` — `ProductivityService` is defined but `bot.py` uses `ProductivityService.get_productivity_metrics` only for the `/productivity` command. `calculate_efficiency` is a dead helper that divides tasks by focus hours without unit normalization (tasks-per-hour is not meaningful without context).

- [ ] **🟡 `send_ping_message` sends two separate Discord API calls instead of one combined message.**
  - **Location**: `cogs/study_groups.py:901–902` — two consecutive `await send_channel.send(...)` calls could be merged into one to reduce API round-trips and avoid message ordering issues under load.

- [ ] **🟡 `StudyGroupCog.cog_load` does not hydrate active groups from DB.**
  - **Location**: `cogs/study_groups.py:1702–1704` — only starts the `cleanup_retry_loop`; there is no `fetch_active_study_groups` call. After a bot restart, `active_study_groups` is empty and `check_end_condition` does not run for any persisted groups until a command touches them. (Already tracked as a lifecycle defect; confirmed at function level.)

- [ ] **🟡 `_process_pending_cleanups_locked` fetches `get_group_category`, `get_commands_channel`, `get_mod_log_channel`, and `get_default_vc` inside the per-item loop.**
  - **Location**: `cogs/study_groups.py:1772–1776` — four DB queries repeated for every pending cleanup item. In a batch of 10 items these become 40 extra queries.
  - **Fix**: Fetch `setting_ids` once before the loop and cache the tuple.

- [x] **🟡 `transfer_group` DB-only path does not update the in-memory `StudyGroup.owner_id`.**
  - **Location**: `cogs/study_groups.py:2300` — `transfer_ownership_study_group_db` updates the DB, but if the group is in `active_study_groups`, its `owner_id` in memory remains stale, allowing the old owner to continue controlling the group via button callbacks.
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Fix**: Look up the in-memory group and update `group.owner_id` after the DB write.

- [ ] **🟡 `check_end_condition` sleeps 60 seconds while `self.ending = True` — 60-second dead-loop.**
  - **Location**: `cogs/study_groups.py:1379–1381` — while a group is ending, the monitor loop sleeps for 60 seconds per iteration before checking `self.ended`. This is unnecessary busy-wait; the loop should exit when `self.ending` is set.
  - **Fix**: `if self.ending: await asyncio.sleep(1); continue` and then `if self.ended: return`.

- [ ] **🟡 `on_voice_state_update` iterates ALL active groups on every VC event.**
  - **Location**: `cogs/study_groups.py:1918–1921` — for a server with 20 active groups, every VC move event triggers 20 comparisons. Index groups by `vc_id` for O(1) lookup.

- [ ] **🟡 `group_info_embed` — Pomodoro session lookup iterates all sessions as a fallback.**
  - **Location**: `cogs/study_groups.py:767–774` — if the first `pomo_cog.sessions.get(self.group_id)` misses, the code iterates all sessions with string comparisons. This is O(n) on every embed refresh, including the 1-second timer-driven refresh.
  - **Fix**: Maintain a reverse index in Pomodoro: `text_id → session`.

- [x] **🟡 `acknowledge_interaction` swallows `InteractionResponded` silently.**
  - **Location**: `utils.py:82–91` — if called twice (e.g., from a decorator and then the command body), `interaction.response.send_message` raises `InteractionResponded`. There is no guard. The interaction is silently left in a partially acknowledged state.
  - **Status**: RESOLVED (Antigravity fix — yet to be verified)
  - **Fix**: Caught `discord.InteractionResponded` to prevent duplicate response exceptions across decorated pipelines.

- [ ] **🟡 `send_response` unconditionally deletes the "Processing…" acknowledgement — breaks pagination.**
  - **Location**: `utils.py:98–108` — every `send_response` call attempts to delete the original `cpo_acknowledged` message. For commands that send multiple embeds (e.g., `list_managers` pagination), the first `send_response` deletes the acknowledgement; subsequent calls attempt deletion of an already-deleted message and raise `discord.HTTPException` (caught, but noisy).
  - **Fix**: Delete the acknowledgement only once (on the final `send_response` call), or mark it deleted after the first successful deletion.

---

### Technical Debt (🔵) — New Findings

- [ ] **🔵 "Go away peasent" typo in 6 command locations.**
  - **Locations**: `cogs/manager.py:833, 877, 915, 1021`; `cogs/study_groups.py:1904, 1930, 2035, 2295, 2320, 2344`; `cogs/pomodoro.py:1173`.
  - **Status**: Preserved per user directive. Replace with "You do not have permission to use this command." when product owner approves.

- [ ] **🔵 Notification path queries DB on every send when `require_vc=False`.**
  - **Location**: `cogs/pomodoro.py:1552–1556` — `if not text_id or not vc_id: db_grp = await fetch_study_group_by_id(...)`. When `vc_id` is intentionally `None` (text-only mode), this triggers a DB query on every 1-second tick notification dispatch.
  - **Fix**: `if not text_id:` (only query when text channel is missing, not when VC is intentionally absent).

- [ ] **🔵 `has_guild_permissions` enumerates 7 permission names via `getattr` on each call.**
  - **Location**: `utils.py:329–338` — trivially fast, but called on every permission-gated command and button callback. Could be reduced to a single bitmask check for performance at scale.

- [ ] **🔵 `complete_operation` in `utils.py` is only used in Check-in; its `asyncio.CancelledError` contract is correct but fragile.**
  - **Location**: `utils.py:25–46` — the shield-retry loop correctly re-raises `CancelledError` after the task finishes. However, if the operation raises a non-`CancelledError` exception *and* the outer task was cancelled, the error is re-raised as `CancelledError` (line 40), swallowing the original cause.
  - **Fix**: Use `raise asyncio.CancelledError from original_error` to preserve the cause chain.

- [ ] **🔵 `StudyGroup.VCFunctions` nested class should be removed (dead code).**
  - **Location**: `cogs/study_groups.py:1612–1652` — entirely unused stubs. Adds ~40 lines of noise with no runtime value.

- [ ] **🔵 `extend_duration_callback` does not persist the new `start_time`/`duration` to the Pomodoro session or check-in session.**
  - **Location**: `cogs/study_groups.py:1120–1128` — only the `StudyGroup.end_time` is extended. If an active Pomodoro session tracks its own `session.focus * 60` deadline separate from the group, the Pomodoro timer is not notified of the group extension.

- [ ] **🔵 `refresh_gui_callback` does not defer the interaction before calling `group_info_embed`.**
  - **Location**: `cogs/study_groups.py:1338–1345` — `group_info_embed` fetches a message (`fetch_message`) and edits it; this can take >3 seconds if Discord is slow. The callback sends a response only after the embed update, risking a 3-second timeout.
  - **Fix**: `await interaction.response.defer(ephemeral=True)` at the top; then call `group_info_embed` and `send_response`.

- [ ] **🔵 No test covers `run_timer` stage transitions or absence counting.**
  - **Status**: Confirmed gap. All 479 existing tests are sequential and mock-based; the timer loop is never exercised. Stage transitions, `eligible` set computation, and absence logic in §4.1-C above cannot be caught by the current suite.
  - **Next Step**: Add coroutine-level concurrency stress tests per `AGENTS.md §5` pattern.

---

### Feature & Expectation Gaps (🔴 Architectural Misalignments)

The following items are missing from the current implementation compared to your explicit design expectations:

- [ ] **🔴 End Group lacks democratic voting (Expectation #2)**
  - **Status**: REOPENED — VOTE-01 through VOTE-05
  - **Evidence**: Implemented `EndGroupVoteView` and `StudyGroup.start_end_vote`. Staff/Admins (Level 3+) bypass vote and end immediately. Group Owner and Members trigger a democratic majority vote among all active group members (`(len(members) // 2) + 1`). Single-member groups end immediately.

- [x] **🔴 Votekick is unimplemented and lacks immunity rules (Expectation #3)**
  - **Status**: REOPENED — VOTE-01 through VOTE-05
  - **Evidence**: Implemented `/votekick` slash command and interactive `votekick_callback` on dashboard via `VotekickSelectView` and `VotekickView`. Staff members (Level 3+) are strictly immune. Group owners and regular members can be votekicked by member majority. Votekicking an owner automatically reassigns ownership to the next remaining member.

- [ ] **🔴 Groups are not strictly invite-only (Expectation #4)**
  - **Current State**: The `/join_group` command (line 2548 in `study_groups.py`) allows anyone in the server to join a group without an invite, provided they know the name and it isn't full.
  - **Requirement**: Disable public joining. Enforce that joining is only possible via a generated invite interaction (`send_invite`).
