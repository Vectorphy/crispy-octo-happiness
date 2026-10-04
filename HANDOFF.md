# CPO handoff - in progress

Updated 2026-10-04. Current branch: antigravity-fix. Workspace: C:\Users\Vector\Downloads\Chief-Productivity-Officer-1.0.0-rc.3.

## Published baseline

Previous batch is committed and pushed to release/v1.0.0-rc.4 as 6b51722c7fd2bafbcd35c6916e036114a83f92e0. Remote identity was verified. That baseline passed 224 offline tests, Mypy, Ruff lint/format, and whitespace checks. No PR or tag change.

The current branch starts from that commit. New work is dirty and not committed or pushed. Do not treat baseline checks as verification of this branch.

## User scope and approvals

- Implement default VC setup and video relocation, plus Pomodoro restart recovery. User said 'Pomodoro reset'; interpreted as the restart-persistence backlog item immediately discussed before it.
- Approved backward-compatible SQLite additions for saved default VC ID and Pomodoro runtime state.
- User explicitly selected VIDEO RELOCATION ONLY. Keep microphone enforcement OFF; do not add or enable a microphone requirement.
- Added setup/help wording: replies elsewhere remain private to avoid server clutter; report malicious or unintended bot behavior to server staff immediately.
- User selected level-aware /help ONLY. Levels 0-2 should not see elevated descriptions. Staff 3-4 see all descriptions, with developer operations labelled Level 4. Do not change Discord picker visibility for this request.
- User additionally requested DATA-01 completion by design/database agents and approved additive measured-focus storage. Count attended Pomodoro focus online; exclude breaks, pauses, dropout/non-attendance, and bot downtime. Never use random hours.
- User previously requested GPT-5.6 Luna/light for light work and GPT-6.1 Sol extra high for debugging, and has little usage left. Keep further work focused.

## Current changes

- database.py: default_vc_id migration/getter/save_setup optional keyword; pomodoro_runtime JSON snapshots plus save/load/retire methods; group deletion retires runtimes; runtime saves reject inactive/missing same-guild groups. New productivity_focus_time table with cumulative per-session/per-user seconds, monotonic MAX upsert, finite/nonnegative validation and seconds aggregate getter. All SQLite queries, transactions, and schema creation/migrations moved off the asyncio event loop via asyncio.to_thread with check_same_thread=False connection configuration and main-thread fallback for legacy test fixtures. Parameterized and locked.
- cogs/_setup_view.py and manager.py: setup provides optional default_vc slash parameter and interactive VoiceSelect dropdown in SetupView; creates/reuses CPO Lobby or selected VC under category, checks connect/move_members bot permissions, alerts on cross-category VC moves, inherits/synchronizes permissions, saves destination atomically as default_vc_id, includes it in stale snapshots, retains resource IDs on failed saves, and displays destination and safety/privacy wording. Added interactive `Recover` button and `recover_retained_resources` with strict explicit ownership checks (session creation match, active DB settings protection, study group preservation, non-empty category guard, moved channel restoration without deletion, caller authorization) and superseded wizard cleanup.
- cogs/_voice_relocation.py: shared relocation helper checks destination, guild, capacity, Connect/Move Members, and current source before moving. Moves noncompliant video members after grace period, sends DM notification on success, and logs/DMs on failure; no disconnect fallback. Camera OR screen sharing qualifies. Microphone enforcement intentionally disabled per user directive.
- bot.py: on_ready invokes Pomodoro hydration.
- cogs/help.py: private immediate defer, runtime-level filtering of setup/staff descriptions, report-to-staff wording. Regular members retain ordinary session/task guidance. Staff see elevated descriptions but execution permissions remain unchanged.
- utils.py and cogs/productivity_tracker.py: design agent replaced random hours with DB-measured attended focus, exact unrounded efficiency calculation, zero when untracked, labelled measured-focus embed.
- utils.py, bot.py, and main.py: design and security update added validate_bot_developer_id rejecting known placeholder values ('123456789012345678', 'your_discord_user_id_here', 'placeholder', 'none', 'null', etc.), invalid formats (booleans, non-integer/floats, negatives, 0), repetitive sequences, non-digits, and out-of-range snowflakes (> 64-bit). CPO constructor supports allow_mock=True for test suites.
- database.py and cogs/study_groups.py: added pending_resource_cleanups table and DAL methods (record_pending_cleanup, get_pending_cleanups, update_cleanup_retry, delete_pending_cleanup, get_pending_cleanup_count). Failed channel and role deletions in StudyGroup.end_group and StudyGroupCog.end_group fallback are recorded for persistent retry tracking. StudyGroupCog runs a background task (cleanup_retry_loop, 10-minute cadence) and startup sweep in bot.py:on_ready to retry deletions when permissions are granted or prune deleted resources, and provides /retry_cleanups command for staff.
- Tests: setup/relocation/helper/help fixtures updated; tests/test_cleanup_retries.py (8 tests), tests/test_bot_developer_id.py (46 tests), tests/test_default_vc.py, tests/test_setup.py (6 new recovery tests, 39 total), tests/test_productivity_time.py, and tests/test_database.py added/extended (343 tests passing).

## Agents and ownership

- /root/debugger (GPT-6.1 Sol extra high): OWNS cogs/pomodoro.py and new tests/test_pomodoro_recovery.py. Finalizing recovery, awaited retirement, idempotent reconnect, state validation, multi-stage offline advancement, and analytics recording/counters. Do not edit these concurrently.
- /root/design: finished utils.py, productivity tracker, and productivity tests; 30 focused tests and scoped Mypy/Ruff pass.
- /root/recovery (GPT-5.6 Luna low), repurposed database specialist: finished analytics DAL; existing database tests and scoped Mypy/Ruff pass. Root added analytics-specific tests afterward.
- Root owns setup/manager/bot integration, VC relocation, help filtering, docs, full verification, Git.

## Required remaining work

1. [COMPLETED] Review real-DB recovery and analytics tests: unique tracking ID survives restart, cumulative focus seconds counted once for opted-in voice-present members, no offline focus time awarded, final counters persisted before retirement, group cleanup retires snapshots.
2. [COMPLETED] Inspect bot.py on_ready hydration and timer/group lifecycle: foreign/inactive group rejection, channel permissions, paused state, stage advancement, reconnect idempotence, and retirement verified.
3. [COMPLETED] Validate BOT_DEVELOPER_ID: added strict snowflake validation, dummy/placeholder rejection, and 46 unit tests.
4. [COMPLETED] Add persistent retry tracking for Discord resources left behind when group cleanup lacks permissions (ARC-05 resolved): added pending_resource_cleanups table, background retry loop, startup sweep, /retry_cleanups command, and 8 unit tests.
5. [COMPLETED] Add recovery for setup resources retained after failed saves (ARC-06 resolved): added Recover button, recover_retained_resources with explicit ownership checks, superseded wizard cleanup, commands.md update, and 6 unit tests.
6. [COMPLETED] Update documentation: CHANGELOG.md [Unreleased], KNOWN_ISSUES.md (ARC-05 & ARC-06 resolved), TODO.md, ARCHITECTURE.md, commands.md, KNOWLEDGE_GRAPH.md, knowledge_graph.json, and HANDOFF.md updated with 350 passing tests.
7. [COMPLETED] Run full verification: 350/350 offline tests pass (zero failures), Mypy static typing 0 errors across 34 source files, Ruff lint and format check clean, git diff --check clean.
8. [COMPLETED] Fixed integration bugs from QA **(Gemini changes yet to be tested)**: `invite_to_group` crashes when inviting bots, `transfer_ownership` silent failure, `/set_permission_level` failing to strip global Bot Developer grants, missing Pomodoro invitation syncs, and missing owner invitation DM notifications.
9. [COMPLETED] Commit/push new branch to QA **(Gemini changes yet to be tested)**: local atomic commits complete; pushed to remote QA branch `antigravity-fix` for testing. Remote origin: https://github.com/Vectorphy/crispy-octo-happiness.git.

## Commands and constraints

Read AGENTS.md, KNOWLEDGE_GRAPH.md and KNOWN_ISSUES.md first. No new dependencies; no production Discord actions. Schema approvals above are already granted; do not ask again. Keep five-tier hierarchy unchanged.

.venv/Scripts/python.exe -m pytest -p no:cacheprovider
.venv/Scripts/mypy.exe bot.py database.py utils.py cogs/ tests/
.venv/Scripts/ruff.exe check bot.py database.py utils.py cogs/ tests/
.venv/Scripts/ruff.exe format --check bot.py database.py utils.py cogs/ tests/
git diff --check

Venv uses Python 3.12.14, Discord.py 2.7.1. Upstream audioop deprecation warning is known. Git metadata writes/push need elevated tool execution under sandbox; approval already authorized, no extra user confirmation. Exclude SQLite, cache, .env and other secret artifacts. Live Discord DM delivery/provisioning remains untested; existing synchronous SQLite I/O, provisioning timeouts and cleanup-retry debt remain.
