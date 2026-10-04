# Known Issues and Debt (Audit Scope)

Verification (2026-10-04 antigravity-fix): all 277 offline tests pass, including Pomodoro recovery, default VC, focus-time DAL, help/setup regression suites, and session-controls AsyncMock fix. Mypy reports zero errors; Ruff lint and formatting pass. Live Discord provisioning has not been exercised. The existing `audioop` deprecation warning remains.

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
- **Status**: **OPEN**
- **Affected File**: `database.py`

### ARC-02: Monolithic Functions with Extreme Cyclomatic Complexity (C901)
- **Severity**: Medium (P2)
- **Status**: **OPEN**
- **Affected Files**:
  - `cogs/study_groups.py:end_group`
  - `cogs/study_groups.py:setup_group_resources`

### ARC-03: Orphaned Scratch Artifacts and Duplicate Backups in Tree
- **Severity**: Low (P2)
- **Status**: **OPEN**
- **Affected Files**:
  - `cogs/study_groups.txt`

### ARC-04: Test Suite Bifurcation (`tests/` vs `test_file.py`)
- **Severity**: Medium (P1)
- **Status**: **RESOLVED** (Pytest runs the asserted standalone command matrix through `tests/test_release_fixes.py`)
- **Affected Files**: `test_file.py`, `tests/`

### ARC-05: Failed Discord Cleanup Can Leave Resources Behind
- **Severity**: Medium (P2)
- **Status**: **OPEN**
- **Affected File**: `cogs/study_groups.py:end_group`
- **Details**: Cleanup logs Discord deletion failures and continues to retire the group. Channels or roles that could not be deleted require manual cleanup; persisted retry tracking is not implemented.

### ARC-06: Failed setup saves can retain provisioned resources
- **Severity**: Low (P2)
- **Status**: **OPEN**
- **Affected File**: `cogs/_setup_view.py`
- **Details**: Changing Discord resources and saving SQLite settings cannot share one transaction. If Save creates a category, commands channel, or logs channel and the settings write fails, those resources remain. Existing recorded channels can also remain moved to the draft category. Staff roles, membership, and permission changes can likewise outlive a failed settings save. The wizard retains channel/category resource IDs for retry, blocks changing the draft category after resource creation, and discloses created or moved resources on cancellation or expiry. Automatic deletion and restoration are not implemented.

---

## 3. Security & Reliability Risks

### SEC-01: Default Superuser ID in Configuration Template
- **Severity**: Medium (P1)
- **Status**: **OPEN**
- **Affected Files**: `.env.example`, `cogs/manager.py`

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
- **Details**: Force Video warns members after 30 seconds and gives them a 60-second grace period before disconnecting members with neither camera nor screen sharing, while Speak updates both `@everyone` and group-role microphone permissions with transactional rollback.

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
- **Details**: Implemented backward-compatible `pomodoro_runtime` table (`session_key`, `group_id`, `guild_id`, `state` JSON, `active`). `save_pomodoro_runtime` / `retire_pomodoro_runtime` / `retire_group_pomodoro_runtime` persist and clean up snapshots under the asyncio lock. `load_active_sessions_from_db` hydrates deadlines, stage, cycles, timer, pause state, consent roster, dropout list, absence counts, and focus-second accumulators on `on_ready`. Offline-elapsed time advances stages without attendance or focus credit; malformed or cross-guild/cross-UUID records are retired. Concurrent save/retire is serialized via `_runtime_lock`. Crash-loss window is at most one snapshot interval (≤15 s). Group deletion retires all group runtimes atomically. Covered by `tests/test_pomodoro_recovery.py` (9 tests).

### SEC-06: Auto-synced staff grants can outlive Discord permissions
- **Severity**: Medium (P2)
- **Status**: **RESOLVED for tracked grants; legacy provenance limitation remains**
- **Affected Files**: `cogs/manager.py`, `database.py`
- **Details**: Approved `grant_source` tracking now distinguishes `server_sync` from `explicit`. Native authority is checked at evaluation time; staff sync removes stale server-synced rows without removing explicit grants. Legacy rows migrate as explicit because their original source cannot be inferred; review old grants manually if they were originally imported from Discord permissions.

### UX-01: Default voice destination — partially implemented
- **Severity**: Low (P2)
- **Status**: **IN PROGRESS (2026-10-04)**
- **Affected Files**: `cogs/_setup_view.py`, `cogs/_voice_relocation.py`, `cogs/study_groups.py`, `database.py`
- **Details**: Setup now creates or reuses a `CPO Lobby` voice channel under the selected category and saves its ID as `default_vc_id` (backward-compatible additive column on `guild_settings`). `_voice_relocation.py` shared helper checks destination existence, guild, capacity, Connect/Move Members permissions, and member's current source before moving; failures log and DM the member without a disconnect fallback. `study_groups.py` calls the helper after the existing video grace period. Camera or screen sharing still qualifies. Microphone enforcement is intentionally disabled per user approval. Full grace-period DM notification, microphone-requirement, and retry-on-failure flow remain follow-up work. Covered by `tests/test_default_vc.py`.

Owner-approval controls, invitation consent, group naming, dashboard delegation, category permission inheritance, bounded intervals, paused expiry, Pomodoro recovery, and focus-time analytics now have offline regression coverage. Live Discord DM delivery, provisioning, and hierarchy behavior remain unverified.

### DATA-01: Productivity time is a placeholder
- **Severity**: Medium (P2)
- **Status**: **RESOLVED (2026-10-04)**
- **Affected Files**: `utils.py`, `cogs/productivity_tracker.py`, `database.py`
- **Details**: Random hours replaced with DB-measured attended Pomodoro focus time. A new `productivity_focus_time` table accumulates per-session per-user seconds with a monotonic MAX upsert; `save_productivity_focus_time` validates finite non-negative values and rejects partial writes. `get_productivity_focus_seconds` aggregates cumulative seconds by user. `ProductivityService` computes exact unrounded efficiency from measured seconds and returns zero when no focus time is recorded. The embed is labelled "measured-focus". Focus is counted only for consented + present + not-dropped-out members during active focus stages; breaks, pauses, dropout, and bot downtime are excluded. Covered by `tests/test_productivity_time.py` and `tests/test_productivity_tracker.py`.
