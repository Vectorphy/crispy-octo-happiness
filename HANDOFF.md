# CPO handoff - in progress

Updated 2026-10-04. Current branch: codex/default-vc-pomodoro-recovery. Workspace: C:\Users\Vector\Downloads\Chief-Productivity-Officer-1.0.0-rc.3.

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

- database.py: default_vc_id migration/getter/save_setup optional keyword; pomodoro_runtime JSON snapshots plus save/load/retire methods; group deletion retires runtimes; runtime saves reject inactive/missing same-guild groups. New productivity_focus_time table with cumulative per-session/per-user seconds, monotonic MAX upsert, finite/nonnegative validation and seconds aggregate getter. Existing data preserved, queries parameterized and locked.
- cogs/_setup_view.py and manager.py: setup creates/reuses CPO Lobby under the selected category, inherits/synchronizes permissions, saves destination atomically with other settings, includes it in stale snapshots, retains resource IDs on failed saves, and displays destination and safety/privacy wording. No slash signature changes.
- cogs/_voice_relocation.py: shared relocation helper checks destination, guild, capacity, Connect/Move Members, and current source before moving. Failures log and DM member; no disconnect fallback. study_groups.py now relocates after existing video grace period. Camera OR screen sharing still qualifies.
- bot.py: on_ready invokes Pomodoro hydration. Debugger is still finalizing recovery internals and tests in cogs/pomodoro.py.
- cogs/help.py: private immediate defer, runtime-level filtering of setup/staff descriptions, report-to-staff wording. Regular members retain ordinary session/task guidance. Staff see elevated descriptions but execution permissions remain unchanged.
- utils.py and cogs/productivity_tracker.py: design agent replaced random hours with DB-measured attended focus, exact unrounded efficiency calculation, zero when untracked, labelled measured-focus embed.
- Tests: setup/relocation/helper/help fixtures updated; tests/test_default_vc.py and tests/test_productivity_time.py added. Focus storage tested for restart, monotonic repeated snapshots, multiple users, and invalid values without partial writes.

## Agents and ownership

- /root/debugger (GPT-6.1 Sol extra high): OWNS cogs/pomodoro.py and new tests/test_pomodoro_recovery.py. Finalizing recovery, awaited retirement, idempotent reconnect, state validation, multi-stage offline advancement, and analytics recording/counters. Do not edit these concurrently.
- /root/design: finished utils.py, productivity tracker, and productivity tests; 30 focused tests and scoped Mypy/Ruff pass.
- /root/recovery (GPT-5.6 Luna low), repurposed database specialist: finished analytics DAL; existing database tests and scoped Mypy/Ruff pass. Root added analytics-specific tests afterward.
- Root owns setup/manager/bot integration, VC relocation, help filtering, docs, full verification, Git.

## Required remaining work

1. Wait for debugger's completion and review its real-DB recovery and analytics tests. Verify unique tracking ID survives restart but changes for each new Pomodoro; cumulative focus seconds are counted once. Consent + Present + not dropped; no offline focus time. Save final counters before retiring. Group cleanup must not resurrect snapshots.
2. Inspect bot.py on_ready integration and existing timer/group cleanup. Test expired/inactive/foreign group records, channel access failures, paused state, stage advancement, reconnect idempotence, end retirement, and snapshot failure behavior.
3. Update CHANGELOG Unreleased, KNOWN_ISSUES ARC-07/UX-01/DATA-01, TODO, KNOWLEDGE_GRAPH, ARCHITECTURE, commands.md. They still describe old memory-only Pomodoro, disconnect behavior and random metrics. Explain 15-second snapshot crash-loss limit if still applicable; analytics measures attended Pomodoro focus, not arbitrary VC/study time.
4. Run modified-module tests and full offline suite; full Mypy, Ruff lint/format, git diff --check. Current root focused run: 91 tests passed across setup, default VC, focus-time DAL, help/shared controls and productivity. Debugger tests are not included yet. Never claim combined branch complete before all checks.
5. Commit/push new branch only after full verification and artifact review; user authorization for project commit/push persists. Do not merge release/main, move tags or publish a release. Remote origin: https://github.com/Vectorphy/crispy-octo-happiness.git.

## Commands and constraints

Read AGENTS.md, KNOWLEDGE_GRAPH.md and KNOWN_ISSUES.md first. No new dependencies; no production Discord actions. Schema approvals above are already granted; do not ask again. Keep five-tier hierarchy unchanged.

.venv/Scripts/python.exe -m pytest -p no:cacheprovider
.venv/Scripts/mypy.exe bot.py database.py utils.py cogs/ tests/
.venv/Scripts/ruff.exe check bot.py database.py utils.py cogs/ tests/
.venv/Scripts/ruff.exe format --check bot.py database.py utils.py cogs/ tests/
git diff --check

Venv uses Python 3.12.14, Discord.py 2.7.1. Upstream audioop deprecation warning is known. Git metadata writes/push need elevated tool execution under sandbox; approval already authorized, no extra user confirmation. Exclude SQLite, cache, .env and other secret artifacts. Live Discord DM delivery/provisioning remains untested; existing synchronous SQLite I/O, provisioning timeouts and cleanup-retry debt remain.
