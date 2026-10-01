# Known Issues and Debt (Audit Scope)

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
- **Details**: Implemented persisted voice permission toggles, invitation DMs, moderator logs, task Select menus, scoped task-message purging, public task/group results, one initial dashboard, and deleted-channel response fallback. Regression checks cover state, authorization, races, malformed selections, missing resources, and API/database failures. Forced camera participation remains a separate open TODO.

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
- **Details**: Force Video warns members after 30 seconds and gives them a 60-second camera grace period before disconnecting them, while Speak updates both `@everyone` and group-role microphone permissions with transactional rollback.

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

The rc3 candidate builds on `c7bdca3`. On bundled Python 3.12.14 with the original virtual environment's packages, all 60 pytest tests pass, including the standalone 54-flow matrix. Mypy and Ruff lint/format checks pass. The upstream `audioop` deprecation warning remains.

`davey 0.1.6` is installed in the original virtual environment and declared in both runtime manifests. The five-tier permission implementation is preserved. Checks use mocked Discord APIs; this run does not verify live provisioning. GitHub publishing remains pending because this automation cannot reach GitHub over the network.
