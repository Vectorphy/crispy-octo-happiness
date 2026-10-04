# Known Issues and Debt (Audit Scope)

Verification (2026-10-05 antigravity-fix): all 402 offline tests pass. Mypy reports zero errors across 34 files; Ruff lint, formatting, and whitespace checks pass. Live Discord provisioning has not been exercised. The existing `audioop` deprecation warning remains.

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

### ARC-08: Setup recovery provenance remains in memory
- **Severity**: Low (P2)
- **Status**: **OPEN limitation**
- **Affected Files**: `cogs/_setup_view.py`, `cogs/manager.py`
- **Details**: Cancelled, expired, or failed setup drafts retain resource IDs and original channel permissions for retry through `/setup`. Restarting the bot loses those handles, so retained resources may need manual review. Staff role, membership, and permission changes made during a failed Save are also outside channel/category rollback. No persistent recovery schema was added during QA.

Legacy runtime snapshots cannot distinguish historical Present and Absent responses. Recovery preserves consent but starts explicit Present tracking empty for such snapshots, so members must mark Present again. Snapshot intervals target 15 seconds when persistence succeeds; write failures can widen crash loss.
