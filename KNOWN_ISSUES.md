# Known Issues and Debt (Audit Scope)

## Exhaustive source audit complete — 2026-10-05; deployment blocked

Source review is complete: 1008/1008 function bodies across 49 executable files, 50/50 lambdas and 83/83 counted module statements, plus first-party config/CI/packaging integration. Runtime/tests remain untouched. Twenty unique open finding IDs and packaging/CI limitations block deployment; detailed semantic mapping is still pending with the mapping agents.

- **INV-01 (P1, OPEN, reproduced offline):** `eligible_recipient` in `cogs/_invitations.py` catches required-role lookup failures and proceeds with `role_id=None`. Injecting a SQLite lookup failure still returns an eligible recipient. Required-role policy must fail closed.
- **INV-02 (P1, OPEN, reproduced offline):** `InvitationService.act` invokes acceptance callbacks after a rejected persistent transition when its fallback create also fails and the row remains pending. A failed CAS or database write must not authorize admission.
- **INV-03 (P1, OPEN, source verified):** Persisted pending invitations have no startup restoration caller. `get_pending_session_invitations` is unused by runtime; pending views/warning/expiration tasks are not recreated after restart. Durable-invitation completion claims are unsupported.
- **AUD-01 (P1, OPEN, source verified):** `audit_action` runtime callers are confined to invitation handling. General slash commands and dashboard controls do not write the claimed comprehensive command audit events.
- **VOTE-05 (P1, OPEN, reproduced offline):** `/votekick` database fallback can resolve a group from another guild through `get_user_group`, then call `start_votekick` without validating the group's guild. A foreign-guild manager must never obtain group authority through the invoking guild.
- **CHECK-01 (P1, OPEN, source verified):** Check-in owner selection updates only `self.owner_id`; the database session updater has no owner field. Restart restores the previous owner. Selection submission also needs fresh authorization and active-session validation.
- **POMO-02 / SEC-09 (P1, OPEN, source verified):** `_persist_session` catches persistence failure and returns normally. Invitation acceptance consequently cannot use that call's exception to roll back its new participant, and can report accepted memory-only state. Verify actual DAL failure, not merely a mocked throwing persistence helper.
- **BUILD-01 (verification constraint):** A fresh offline build was attempted in a disposable allowlisted source copy and failed because `setuptools.build_meta` is unavailable in the local environment. No build/package-validator success is claimed. General CI does not automatically target `antigravity-fix`; release dispatch defaults to the old immutable rc.5 tag.


- **GROUP-01 (P1, OPEN, reproduced offline):** Voice-channel provisioning failure leaves the previously created role/text channel behind (`cogs/study_groups.py:416–505`).
- **AUTH-01 (P1, OPEN, source verified):** Category configuration and group purge skip authorization when the Manager cog is unavailable (`cogs/study_groups.py:2384–2415,2683–2759`).
- **AUTH-02 (P1, OPEN, source verified):** Level 3 manager grant/revoke can overwrite or delete a Level 4 target grant (`cogs/manager.py:821–900`).
- **UI-01 (P2, OPEN, reproduced offline):** Task-list rendering exceeds Discord description/aggregate limits; the boundary probe produced 7,234 description characters (`cogs/tasklist.py:78–123`).
- **UI-02 (P2, OPEN, source verified):** Group listing emits an unbounded field per group (`cogs/study_groups.py:2863–2884`).
- **NOTIFY-01 (P2, OPEN, source verified):** Manager notifications call `.get` on SQLite rows; dictionary mocks hide the resulting suppressed failure (`cogs/manager.py:653–688`).

Verified offline checks: 484 full-suite tests, 134 targeted tests, Mypy zero errors across 43 files, Ruff lint/format and whitespace pass for the current unchanged runtime. Precise tested scopes are verified; democratic vote correctness, complete serialization, durable invitation recovery and comprehensive command auditing remain OPEN or pending. Parentheses in the DATA-02 set expression are mathematically equivalent and do not constitute a behavioral fix.


## Independent audit — 2026-10-05: deployment blocked

Fresh verification of the dirty Antigravity tree passed 484 full-suite tests, 134 focused tests, Mypy across 43 files, Ruff lint/format, and whitespace checks. Adverse-order probes nevertheless reproduced the following defects; passing tests do not establish deployment readiness.

- **VOTE-01 (P1, OPEN):** End-group voting retains votes from departed members while recalculating the majority from the current roster. A departed initiator plus one current voter can end a two-member group without its current majority (`cogs/study_groups.py:130–158`). Filter votes against current eligible membership before evaluating the outcome.
- **VOTE-02 (P1, OPEN):** Owner votekick changes the in-memory owner before the database transfer succeeds, catches transfer failure, and continues removing the owner (`cogs/study_groups.py:254–266`). A failed write must preserve ownership and membership; successful transfer and removal need consistent persistence.
- **VOTE-03 (P1, OPEN):** Votekick staff immunity is checked at initiation but not at execution. A target promoted to administrator during voting can still be removed (`cogs/study_groups.py:228–266`). Revalidate current target authority immediately before removal, including the immediate-vote path.
- **SEC-10 remains OPEN:** `/join_group` still admits users by group name without an invitation (`cogs/study_groups.py:2888` onward). This does not meet the saved invite-only expectation.

- **VOTE-04 (P1, OPEN):** `remove_member` catches role/database removal failures and returns no success result (`cogs/study_groups.py:641–701`); both votekick paths then announce success regardless. Removal attempts only the group's role, roster, and database membership; it does not explicitly disconnect voice or retire that user's Pomodoro/check-in participation.
- **POMO-01 (P2, OPEN):** Dropped participants are told to use `/resume_pomodoro` (`cogs/pomodoro.py:300–305`), but the new owner/manager gate rejects ordinary participants (`1395–1407`). The recovery instructions and supported action must agree.
- **Audit scope corrections:** Session locks do not cover all attendance, dashboard pause, or retirement paths; comprehensive ARC-12 serialization is unverified. The DATA-02 set expressions are mathematically equivalent, so parentheses alone do not prove an accounting fix. `/votekick` and optional `/create_group mentions` change public slash signatures despite the saved unchanged-signature constraint; reconcile authorization before release.

Packaging allowlists were inspected. A later fresh offline build attempt failed because setuptools.build_meta is unavailable; the package validator did not run. The default release dispatch checks out the existing rc.5 tag, not the dirty working tree.

Runtime source remains unchanged by this audit. Live Discord behavior and current-source Python 3.11.17 CI are not verified by the local Python 3.12.14 checks. Existing rc.5 tags/assets remain immutable and do not contain these dirty changes.

Verification (2026-10-05 antigravity-fix): all 484 offline tests pass. Previous checkpoint was `codex checkpoint` (`8e9e298`), followed by intermediate `antigravty checkpoint` (`f9a3981`). Current uncommitted Antigravity changes have evidence-scoped offline verification; reopened defects and unsupported claims remain pending. The final exhaustive audit report governs readiness. Mypy reports zero errors across 43 source files; Ruff lint, formatting, and whitespace checks pass. Live Discord provisioning has not been exercised. The existing `audioop` deprecation warning remains.

## 1. Functional & Technical Deficiencies

### AD-01: Aggressive `.gitignore` Blocking Documentation
- **Severity**: Low (P3)
- **Status**: **RESOLVED** (Fixed during audit)
- **Affected Files**: `.gitignore`, `tests/test_new_features.py`

### AD-02: Environmental State Bleed in Standalone Test Suite (`test_file.py`)
- **Severity**: High (P1)
- **Status**: **RESOLVED** (The runner replaces the database with `DBHandler(":memory:")` before connecting and closes the bot in `finally`)
- **Affected Files**: `test_file.py`, `bot_database.sqlite`

### AD-03: Dangling Unused MongoDB Dependencies in Manifests
- **Severity**: Low (P2)
- **Status**: **RESOLVED**
- **Affected Files**: `requirements.txt`, `pyproject.toml`

### AD-04: Mypy Incompatible Type Argument Inconsistencies
- **Severity**: Medium (P1)
- **Status**: **RESOLVED** (Fixed during audit)
- **Affected Files**: `cogs/pomodoro.py`, `cogs/study_groups.py`

### AD-05: Unawaited Coroutine Mock Warnings in Test Suites
- **Severity**: Low (P2)
- **Status**: **RESOLVED** (Used `MagicMock` for synchronous `InteractionResponse.is_done()` checks and `AsyncMock` only for awaited Discord calls)
- **Affected Files**: `tests/test_new_features.py`, `test_file.py`

---

## 2. Architectural Debt

### ARC-01: Blocking Synchronous SQLite I/O in Async Event Loop
- **Severity**: High (P1)
- **Status**: **RESOLVED (2026-10-05 offline QA)**
- **Affected File**: `database.py`
- **Details**: SQLite work runs through `asyncio.to_thread` under the database lock. Cancelled callers drain workers before releasing that lock, including repeated cancellation; connection opening and closing share the lock. Legacy test connections use `check_same_thread=False` rather than synchronous fallback. Regression checks cover thread execution, cancellation, and concurrent close.

### ARC-02: Monolithic Functions with Extreme Cyclomatic Complexity (C901)
- **Severity**: Medium (P2)
- **Status**: **OPEN**
- **Affected Files**:
  - `cogs/study_groups.py:end_group`
  - `cogs/study_groups.py:setup_group_resources`

### ARC-03: Orphaned Scratch Artifacts and Duplicate Backups in Tree
- **Severity**: Low (P2)
- **Status**: **RESOLVED (2026-10-05)**
- **Affected Files**:
  - `cogs/study_groups.txt`
- **Details**: Removed the inactive duplicate. Release packages use an allowlist and exclude development/test artifacts while retaining regression tests in Git.

### ARC-04: Test Suite Bifurcation (`tests/` vs `test_file.py`)
- **Severity**: Medium (P1)
- **Status**: **RESOLVED** (Pytest runs the asserted standalone command matrix through `tests/test_release_fixes.py`)
- **Affected Files**: `test_file.py`, `tests/`

### ARC-05: Failed Discord Cleanup Can Leave Resources Behind
- **Severity**: Medium (P2)
- **Status**: **RESOLVED (2026-10-04)**
- **Affected Files**: `cogs/study_groups.py`, `database.py`, `bot.py`
- **Details**: Implemented persistent retry tracking via `pending_resource_cleanups` table. Failed deletions of text channels, voice channels, and roles during `end_group` (or its database fallback) are recorded with error context and status='pending'. A background task (`cleanup_retry_loop`, 10-minute cadence) and bot `on_ready` sweep re-attempt deletion when Discord permissions are granted, or prune entries when resources are confirmed deleted. Staff can also manually trigger `/retry_cleanups` for immediate execution and status reporting. Covered by `tests/test_cleanup_retries.py` (8 tests).

### ARC-06: Failed setup saves can retain provisioned resources
- **Severity**: Low (P2)
- **Status**: **RESOLVED (2026-10-04)**
- **Affected File**: `cogs/_setup_view.py`, `cogs/manager.py`
- **Details**: Added explicit setup resource recovery via interactive `Recover` button on `SetupView` and programmatic `recover_retained_resources` method. Enforces strict explicit ownership checks before resource deletion: verifies resources were created in the active session, verifies IDs are not saved in active database settings (`group_category_id`, `commands_channel_id`, `mod_log_channel_id`, `default_vc_id`), verifies channels do not belong to active study groups, checks that created categories are empty before deletion, reverts moved channels back to their previous categories without deletion, and requires current staff authority in the same guild. Superseded setup sessions in `Manager.setup` automatically recover uncommitted resources. Covered by 6 dedicated unit tests in `tests/test_setup.py`.

---

## 3. Security & Reliability Risks

### SEC-07: Log access can outlive native staff authority
- **Severity**: High (P1)
- **Status**: **VERIFIED OFFLINE for native revocation and category/log sealing scenarios (tests/test_staff_roles.py); live Discord pending**
- **Affected Files**: `cogs/_staff_roles.py`, `cogs/manager.py`
- **Details**: The debugger added native-authority event reconciliation, explicit CPO-role log denies, and sealing before category mutations and after failures. Core regression checks passed; independent QA must rerun the original revocation and category-propagation findings after the remaining feature work.

### SEC-08: Non-task activity and command-granted developer scope span guilds
- **Severity**: High (P1)
- **Status**: **Fix implemented; independent resumed QA pending**
- **Affected Files**: `database.py`, `utils.py`, `cogs/manager.py`, `cogs/checkin.py`, `cogs/productivity_tracker.py`, `cogs/study_groups.py`
- **Details**: Focus-time aggregation, participation counts, settings, and command-granted Level 4 developers now use the current guild. Only the developer ID configured in `.env` confers global Level 5 Supreme Commander authority. Legacy null-guild and stored Level 5 rows remain inert. Tracking/session provenance checks reject cross-guild identity collisions. Explicit task cross-scope behavior stays available. Core regression checks passed; independent QA remains pending.

### SEC-09: Pomodoro invitation acceptance precedes group admission
- **Severity**: High (P1)
- **Status**: **Fix in progress during invitation integration**
- **Affected File**: `cogs/pomodoro.py`
- **Details**: Invitation review found participant persistence occurring before study-group admission. A full group or failed admission could leave a Pomodoro participant who never joined the group. The coding agent is moving participant commit after successful admission and adding failure-boundary regressions. Independent QA must verify both admission and subsequent persistence failure.

### SEC-01: Default Superuser ID in Configuration Template
- **Severity**: Medium (P1)
- **Status**: **RESOLVED (configuration validation)**
- **Affected Files**: `.env.example`, `cogs/manager.py`
- **Details**: Startup validates `BOT_DEVELOPER_ID` and rejects the template placeholder, malformed values, and invalid bounds. An invalid value yields no configured developer authority. Offline validation tests cover these cases.

### SEC-02: Missing Timeout Wrappers on Discord API Calls
- **Severity**: Medium (P1)
- **Status**: **OPEN**
- **Affected Files**: `cogs/study_groups.py`, `cogs/checkin.py`

### SEC-03: SQLite Single-File Reliability in Containerized Environments
- **Severity**: Medium (P2)
- **Status**: **OPEN**
- **Affected Files**: `database.py`, `bot_database.sqlite`

### SEC-04: Upstream Python 3.13 `audioop` Deprecation
- **Severity**: Low (P2)
- **Status**: **OPEN**
- **Affected File**: `.venv/Lib/site-packages/discord/player.py`

## Release audit (2026-10-01)

### AD-09: Standalone tests disable success assertions
- **Severity**: High (P1)
- **Status**: **RESOLVED**
- **Affected File**: `test_file.py`
- **Details**: Restored assertions, real task IDs, and mandatory dashboard callback execution. All 54 flows pass against an in-memory database; the matrix is also a pytest regression.

### AD-10: Feature completion claims exceed the implementation
- **Severity**: Medium (P2)
- **Status**: **RESOLVED**
- **Affected Files**: `cogs/study_groups.py`, `cogs/tasklist.py`, `TODO.md`
- **Details**: Implemented persisted voice permission toggles, invitation DMs, moderator logs, task Select menus, scoped task-message purging, public task/group results, one initial dashboard, and deleted-channel response fallback. Regression checks cover state, authorization, races, malformed selections, missing resources, and API/database failures. Forced video participation is implemented and now accepts camera or screen sharing.

### SEC-05: Legacy schema migration can discard study groups
- **Severity**: High (P1)
- **Status**: **RESOLVED**
- **Affected File**: `database.py:create_tables`
- **Details**: Removed the table drop. Additive migration preserves groups, rosters, role/channel IDs, and current numeric primary keys. Tests cover the earliest schema, historical table names, partial identifier migration, and repeat startup. Early records lacking an activity flag default to inactive. If historical and current table names coexist, migration leaves the historical tables intact rather than merging potentially conflicting records; inspect that case before deployment.

## Verified fixes and release checks

### AD-14: Task list scope leaked group tasks by default
- **Severity**: High (P1)
- **Status**: **RESOLVED**
- **Affected Files**: `cogs/tasklist.py`, `database.py`, `tests/test_release_fixes.py`, `tests/test_database.py`
- **Details**: Default task listing now shows only global tasks outside a group. Cross-group results require an explicit `all_groups: true` value and are sent ephemerally.

### AD-13: Force Video and strict Speak controls
- **Severity**: Medium (P2)
- **Status**: **RESOLVED**
- **Affected Files**: `cogs/study_groups.py`, `tests/test_release_fixes.py`
- **Details**: Force Video uses a default 60-second total wait, warns for the final 30 seconds, and relocates members with neither camera nor screen sharing, while Speak updates both `@everyone` and group-role microphone permissions with transactional rollback.

### AD-12: Study-group voice channels were deleted when empty
- **Severity**: Medium (P2)
- **Status**: **RESOLVED**
- **Affected File**: `cogs/voice_channels.py`
- **Details**: Removed the voice-state listener that deleted a study-group voice channel when its last member disconnected. Manual `/delete_vc` and group-ending cleanup remain available.

### AD-11: Hosting default entrypoint mismatch
- **Severity**: High (P1)
- **Status**: **RESOLVED**
- **Affected File**: `main.py`
- **Details**: Some hosting panels start the service with `python3 /home/container/main.py`, while the project previously exposed only `bot.py`. The new compatibility launcher delegates to the existing bot startup path.

### AD-15: Cross-Server Task Bleed and Global Ephemeral Visibility Uniformity
- **Severity**: High (P1)
- **Status**: **RESOLVED**
- **Affected Files**: `cogs/tasklist.py`, `database.py`, `utils.py`, `cogs/study_groups.py`, `cogs/pomodoro.py`, `cogs/checkin.py`, `cogs/manager.py`, `cogs/productivity_tracker.py`, `cogs/voice_channels.py`
- **Details**: Tasks previously lacked strict server isolation, allowing tasks from one guild to appear in another when queried. Scoped task storage and queries by `guild_id` and added `guild_id` column migration. The rc4 release introduced category-based reply visibility; the current setup work replaces that policy with active-group or exact commands-channel matching.

### AD-16: Public error replies inherit command context
- **Severity**: Medium (P2)
- **Status**: **RESOLVED**
- **Affected Files**: `cogs/voice_channels.py`, `cogs/tasklist.py`, `cogs/checkin.py`, `utils.py`
- **Details**: Commands now acknowledge privately before sending independently visible final replies. Voice and task validation failures remain private, mixed task-action failures and purge cleanup warnings force private results, and check-in personal acknowledgements remain private. Normal slash success replies are public in active group channels and the exact saved commands channel. Category membership alone does not make replies public.

The rc3 candidate builds on `c7bdca3`. On bundled Python 3.12.14 with the original virtual environment's packages, all 68 pytest tests pass, including the standalone 54-flow matrix. Mypy and Ruff lint/format checks pass. The upstream `audioop` deprecation warning remains.

`davey 0.1.6` is installed in the original virtual environment and declared in both runtime manifests. The five-tier permission implementation is preserved. Checks use mocked Discord APIs; this run does not verify live provisioning. Historical automation publishing failures do not describe the current local branch push; release/tag publication remains separate follow-up work.


## Session-control review (2026-10-04)

### ARC-07: Pomodoro runtime state is lost on restart
- **Severity**: Medium (P2)
- **Status**: **RESOLVED (2026-10-04)**
- **Affected Files**: `cogs/pomodoro.py`, `database.py`
- **Details**: Implemented backward-compatible `pomodoro_runtime` table (`session_key`, `group_id`, `guild_id`, `state_json` JSON, `active`). `save_pomodoro_runtime` / `retire_pomodoro_runtime` / `retire_group_pomodoro_runtime` persist and clean up snapshots under the asyncio lock. `load_active_sessions_from_db` hydrates deadlines, stage, cycles, timer, pause state, consent roster, dropout list, absence counts, and focus-second accumulators on `on_ready`. Offline-elapsed time advances stages without attendance or focus credit; malformed or cross-guild/cross-UUID records are retired. Concurrent save/retire is serialized via `_runtime_lock`. Snapshots target a 15-second interval when writes succeed; failed writes can widen the crash-loss window. Group deletion retires all group runtimes atomically. Covered by recovery, timing, downtime, and final-write regressions in `tests/test_pomodoro_recovery.py`.

### SEC-06: Auto-synced staff grants can outlive Discord permissions
- **Severity**: Medium (P2)
- **Status**: **RESOLVED for tracked grants; legacy provenance limitation remains**
- **Affected Files**: `cogs/manager.py`, `database.py`
- **Details**: Approved `grant_source` tracking now distinguishes `server_sync` from `explicit`. Native authority is checked at evaluation time; staff sync removes stale server-synced rows without removing explicit grants. Legacy rows migrate as explicit because their original source cannot be inferred; review old grants manually if they were originally imported from Discord permissions.

### UX-01: Default voice destination
- **Severity**: Low (P2)
- **Status**: **RESOLVED (2026-10-04)**
- **Affected Files**: `cogs/_setup_view.py`, `cogs/_voice_relocation.py`, `cogs/manager.py`, `cogs/study_groups.py`, `database.py`
- **Details**: Setup supports an optional `default_vc` slash command parameter and interactive `VoiceSelect` channel picker in `SetupView`. It creates or reuses `CPO Lobby` (or the selected voice channel) under the category and saves its ID as `default_vc_id` (`guild_settings`). `SetupView.render()` alerts if the default VC will be moved across categories, and `_save_locked` validates `view_channel`, `connect`, and `move_members` bot permissions on the destination. `_voice_relocation.py` moves video-noncompliant members after the grace period and sends a DM notification on success or actionable guidance on failure without disconnecting. Microphone enforcement is intentionally disabled per user directive. Covered by `tests/test_default_vc.py` and `tests/test_setup.py` (281 total tests pass).

Owner-approval controls, invitation consent, group naming, dashboard delegation, category permission inheritance, bounded intervals, paused expiry, Pomodoro recovery, default voice relocation, and focus-time analytics now have offline regression coverage. Live Discord DM delivery, provisioning, and hierarchy behavior remain unverified.

### DATA-01: Productivity time is a placeholder
- **Severity**: Medium (P2)
- **Status**: **RESOLVED (2026-10-04)**
- **Affected Files**: `utils.py`, `cogs/productivity_tracker.py`, `database.py`
- **Details**: Random hours replaced with DB-measured attended Pomodoro focus time. A new `productivity_focus_time` table accumulates per-session per-user seconds with a monotonic MAX upsert; `save_productivity_focus_time` validates finite non-negative values and rejects partial writes. `get_productivity_focus_seconds` aggregates cumulative seconds by user. `ProductivityService` computes exact unrounded efficiency from measured seconds and returns zero when no focus time is recorded. The embed is labelled "measured-focus". Focus is counted only for consented + present + not-dropped-out members during active focus stages; breaks, pauses, dropout, and bot downtime are excluded. Covered by `tests/test_productivity_time.py` and `tests/test_productivity_tracker.py`.

## QA corrections (2026-10-05)

### CI-01: Prerelease test launcher omits repository imports
- **Severity**: Medium (P2)
- **Status**: **RESOLVED; recovery run 37234471606 succeeded**
- **Affected File**: `.github/workflows/prerelease.yml`
- **Details**: The initial rc.5 tag run passed Mypy and Ruff but the `pytest` console entrypoint failed collection for `bot` and `cogs`. The workflow now uses `python -m pytest`, matching local verification. Recovery explicitly checked out `v1.0.0-rc.5` at `a01656c` in both jobs and passed 402 tests, Mypy, Ruff, and package validation. The published prerelease and downloaded packages passed integrity, digest, membership, version, and committed-source checks. Workflow fix `817cccf` preserved the tag. Subsequent CI work pins exact Python `3.11.17` for release jobs and the 3.11 general-CI matrix entry; the other compatibility entries remain. Crispy release run 37235239110 passed 402 tests and packaging on exact 3.11.17; both repositories' full CI matrices passed. Both prereleases retain source commit `a01656c`, and downloaded archives from both were verified. Live Discord limitations remain unchanged.

### AD-17: Concurrent group teardown repeats cleanup after state is cleared
- **Severity**: High (P1)
- **Status**: **RESOLVED in offline regressions**
- **Affected Files**: `cogs/study_groups.py`, `cogs/pomodoro.py`
- **Details**: Manual teardown and the background monitor could both enter cleanup, causing repeated Unknown Channel/Role errors and dereferences of cleared guild state. An end lock and ending/ended states prevent duplicate cleanup. Final focus persistence runs before deleting resources. A failed final write reports failure privately, leaves the group active for retry, and keeps the monitor running. Real SQLite-backed failure, retry, and duplicate-end regressions pass.

### ARC-08: Setup recovery provenance was lost on restart
- **Severity**: Low (P2)
- **Status**: **Fix implemented; independent resumed QA pending**
- **Affected Files**: `cogs/_setup_view.py`, `cogs/manager.py`
- **Details**: The approved additive recovery journal stores resource intents, IDs, original categories, and exact overwrites across restart. Settings and committed phase share one transaction; staff synchronization follows the commit and remains durable pending work on failure. Missing or ambiguous audit proof, changed permissions/settings, and uncertain ownership retain resources for review. Restart regressions pass; ARC-09 tracks the remaining ownership race found during resumed QA.

### ARC-09: Setup recovery ownership can change during awaits
- **Severity**: High (P1)
- **Status**: **Fix implemented; independent resumed QA pending**
- **Affected Files**: `cogs/_setup_view.py`, `cogs/study_groups.py`
- **Details**: A real SQLite interleaving probe originally saved a recovery-created channel as the moderator-log destination during a channel fetch. Shared guild operation locks now serialize recovery, configuration, and resource allocation; recovery also refreshes ownership after journal writes before destructive mutations. Core regression checks passed; independent QA must rerun the interleaving.

### ARC-10: Reminder waits and replacement video tasks lose lifecycle ownership
- **Severity**: Medium (P1)
- **Status**: **Fix implemented; independent resumed QA pending**
- **Affected Files**: `cogs/checkin.py`, `cogs/study_groups.py`
- **Details**: Check-in reminder waits now use cancellation-safe timeout handling, and video cleanup only unregisters the task that still owns its registry entry. Cogs drain owned tasks before database shutdown. Core lifecycle/cancellation regressions passed; independent QA remains pending.

Legacy runtime snapshots cannot distinguish historical Present and Absent responses. Recovery preserves consent but starts explicit Present tracking empty for such snapshots, so members must mark Present again. Snapshot intervals target 15 seconds when persistence succeeds; write failures can widen crash loss.

## Function-Level Audit Findings (2026-10-05)

### ARC-11: Democratic Voting & Votekick Missing
- **Severity**: High (P1) - Feature/Expectation Gap
- **Status**: **REOPENED — VOTE-01 through VOTE-05; initial implementation does not establish correctness**
- **Affected Files**: `cogs/study_groups.py`
- **Details**: Implemented `EndGroupVoteView` and `StudyGroup.start_end_vote`. Staff/Admins (Level 3+) bypass vote and end immediately; members and owners trigger democratic vote requiring majority consent (`(len(members) // 2) + 1`). Implemented `/votekick` slash command and interactive `votekick_callback` via `VotekickSelectView` and `VotekickView`. Level 3+ staff are strictly immune, and owner votekick auto-reassigns ownership to the next roster member.

### SEC-10: Groups Allow Public Joining By Default
- **Severity**: High (P1) - Feature/Expectation Gap
- **Status**: **OPEN**
- **Affected Files**: `cogs/study_groups.py`
- **Details**: `/join_group` allows any server member to join a group without an explicit invitation if they know the name and the group is not full, bypassing the strict invite-only expectation.

### SEC-11: Pomodoro Session Creation Lacks Ownership Gate
- **Severity**: Critical (P0)
- **Status**: **SOURCE VERIFIED — ownership gate present; ordinary-participant recovery remains OPEN under POMO-01**
- **Affected Files**: `cogs/pomodoro.py`
- **Details**: Enforced creator/owner and Level 3+ manager check (`check_manager(interaction)`) in `/start_pomodoro`, `/pause_pomodoro`, and `/resume_pomodoro`, denying unauthorized users with `"Go away peasent"`.

### DATA-02: Pomodoro `eligible` Set Operator Precedence Bug
- **Severity**: Critical (P0)
- **Status**: **CLAIM CORRECTED — equivalent set expressions; no behavioral precedence fix**
- **Affected Files**: `cogs/pomodoro.py:run_timer`
- **Details**: Wrapped intersection in parentheses: `(session.participants & session.present_members) - session.dropped_out_members` at `cogs/pomodoro.py:1468`, preventing dropped out members from receiving focus credit.

Audit correction: `A & (B - C)` and `(A & B) - C` are equivalent; parentheses alone change no eligible members.

### ARC-12: Concurrent State Mutation in Pomodoro & Check-in
- **Severity**: Critical (P0)
- **Status**: **OPEN — partial locking; attendance, pause and retirement paths remain outside serialization**
- **Affected Files**: `cogs/pomodoro.py`, `cogs/checkin.py`
- **Details**: Added `self.lock = asyncio.Lock()` per Pomodoro session and serialized mutations in `run_timer`, pause, resume, and edit. Serialized `/start_pomodoro` per group using `_start_locks`. In Check-in, wrapped `mark_present_callback` and `start_break_callback` under `self.join_lock`, and incremented `ABSENCES` counter instead of resetting to 1.
