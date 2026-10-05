# Exhaustive source audit — deployment blocked

Inspected snapshot: HEAD f9a3981, antigravity-fix, current dirty source after checkpoint 8e9e298. Raw-byte SHA256 fingerprints are in snapshot.json and coverage.json. Both available checkpoint authors are Vectorphy; Gemini/Antigravity authorship cannot be independently assigned per function from these labels.

Coverage: 1008/1008 def/async-def bodies reviewed in 49 first-party executable files; 50/50 lambda expressions reviewed separately; 83/83 non-import/non-definition executable module statements reviewed separately. PowerShell script has no declared functions and was reviewed as a module. Import declarations/class static constants/decorators were considered during file review; the separate module count intentionally excludes imports, class definitions and docstrings. Empty package initializers included. Config/CI/packaging integration inspected as recorded in snapshot.json.

Source review is not dynamic coverage. Every row retains path/signature/line/outcome, source operation summary, finding IDs and known gaps. AST calls/tables/state writes/context-manager metadata are explicitly candidates, not complete semantic maps. Detailed domain-purpose and runtime-dispatch edges remain for mappers; this audit does not claim exhaustive formal proof or live Discord validation.

Verification: full offline pytest484 passed; modified-module/focused pytest134 passed. Mypy0 issues43 files; Ruff lint/format43 files and git diff whitespace passed. Tests used fresh owned basetemps/caches; initial default shared-temp ACL failures are environmental and were superseded by unique-temp success. Actual adverse-order/failure probes reproduced vote/CAS/access/scoping defects. No bot login, live Discord mutations or network deployment. Offline build --no-isolation in allowlisted disposable copy failed: setuptools.build_meta unavailable. Package member allowlists are source reviewed; no fresh successful built-archive/package-validator execution. Local Python3.12.14, release target3.11.17 remains unverified for current source.

## Actionable findings

- **VOTE-01 P1 OPEN** — `cogs/study_groups.py:120`: Departed votes remain counted against a reduced current roster. Evidence: Offline adverse-order reproduction.
- **VOTE-02 P1 OPEN** — `cogs/study_groups.py:228`: Owner changes before failed DB transfer, followed by removal. Evidence: Offline injected transfer failure.
- **VOTE-02 P1 OPEN** — `cogs/study_groups.py:1640`: Immediate kick duplicates inconsistent owner transfer. Evidence: Source inspection.
- **VOTE-03 P1 OPEN** — `cogs/study_groups.py:228`: Staff promotion after initiation is not rechecked. Evidence: Offline adverse-order reproduction.
- **VOTE-04 P1 OPEN** — `cogs/study_groups.py:641`: Removal catches failure without outcome; callers announce success. Evidence: Offline DB removal failure and source inspection.
- **VOTE-05 P1 OPEN** — `cogs/study_groups.py:3177`: Foreign-guild fallback group is accepted for votekick. Evidence: Offline cross-guild reproduction.
- **SEC-10 P1 OPEN** — `cogs/study_groups.py:2888`: Named join bypasses invitation-only policy. Evidence: Source inspection and existing matrix intentionally joins uninvited user.
- **POMO-01 P2 OPEN** — `cogs/pomodoro.py:284`: Dropped regular participants receive unusable resume guidance. Evidence: Source inspection and authorization paths.
- **POMO-01 P2 OPEN** — `cogs/pomodoro.py:1378`: Resume owner/staff gate excludes regular recovery. Evidence: Source inspection.
- **INV-01 P1 OPEN** — `cogs/_invitations.py:30`: Role settings error permits invitation eligibility. Evidence: Offline sqlite error injection.
- **INV-02 P1 OPEN** — `cogs/_invitations.py:490`: Failed CAS/create fallback still runs acceptance callback. Evidence: Offline false transition and failed create reproduction.
- **INV-03 P1 OPEN** — `cogs/_invitations.py:1`: No startup restoration of pending views/timers. Evidence: Runtime call-site review; pending DAL getter has no runtime caller.
- **AUD-01 P1 OPEN** — `cogs/_audit.py:1`: General commands and controls lack promised persistent audit coverage. Evidence: Runtime audit_action call-site review.
- **CHECK-01 P1 OPEN** — `cogs/checkin.py:1160`: Owner transfer memory-only and selector authority not revalidated. Evidence: Source inspection: owner_id write absent DAL updater.
- **POMO-02 P1 OPEN** — `cogs/pomodoro.py:420`: Persistence helper swallows error defeating acceptance rollback. Evidence: Actual DAL saver OperationalError returns normally.
- **ARC-12 P2 OPEN** — `cogs/pomodoro.py:284`: Attendance is outside session serialization. Evidence: Source inspection.
- **ARC-12 P2 OPEN** — `cogs/pomodoro.py:813`: Retirement/dashboard pause omit session lock. Evidence: Source inspection.
- **ARC-12 P2 OPEN** — `cogs/pomodoro.py:1449`: Gateway lifecycle mutates sessions outside session lock. Evidence: Source inspection.
- **GROUP-01 P1 OPEN** — `cogs/study_groups.py:416`: Partial provisioning failures orphan role/text resources. Evidence: Voice creation Forbidden: text_id=0; role/text created; text delete=0; registry empty.
- **UI-01 P2 OPEN** — `cogs/tasklist.py:78`: Task descriptions exceed embed character limits. Evidence: 15 x 450-char tasks -> description7234,total7267.
- **UI-02 P2 OPEN** — `cogs/study_groups.py:2863`: List groups adds unbounded fields. Evidence: Source: one field per active group; guild has no total group cap.
- **AUTH-01 P1 OPEN** — `cogs/study_groups.py:2384`: Missing Manager cog skips category-setting authorization. Evidence: Source branch only denies inside if manager_cog.
- **AUTH-01 P1 OPEN** — `cogs/study_groups.py:2683`: Missing Manager cog skips purge authorization. Evidence: Source branch only denies inside if manager_cog.
- **AUTH-02 P1 OPEN** — `cogs/manager.py:821`: Level3 can overwrite/remove stored Level4 through manager commands. Evidence: Source: caller level3 gate then add_manager3/remove_manager without target-tier check.
- **NOTIFY-01 P2 OPEN** — `cogs/manager.py:653`: Developer alert assumes dict but DAL returns sqlite.Row. Evidence: Source: mgr.get raises AttributeError and catches; tests use dict mocks.

## Configuration and test limits

- CI branch filters omit antigravity-fix; default release dispatch checks existing immutable rc.5. Version remains1.0.0rc5. Final source requires its own CI/build verification; do not overwrite rc.5 assets/tags.
- Gemini workflow grants write token/API secret to issue/comment mention triggers without an explicit actor-authorization condition. Source configuration risk; action runtime trust/behavior was not exercised, so no proven exploit claim. Release metadata interpolates dispatch strings directly into Bash; use environment variables before expanding shell text.
- start-agents.ps1 retains old mapper-after-QA and inherited CI/CD profile, diverging from latest user scheduling/profile. Latest user order governs; do not invoke stale script instructions unchanged.
- Standalone 54-flow runner calls command.callback directly, bypassing command-tree and decorator dispatch checks; its 100% header claim is unsupported. It opens change-owner selection but does not execute/persist owner selection.
- test_manager_roles_and_perms.py negative leave-group assertion checks remove_member_from_group, while runtime uses remove_member_from_study_group_db. Replace with actual method and durable-state assertion.
- Existing short-task pagination test checks fields/page count, not descriptions/total size; vote tests cover fixed roster happy paths, not failures. Invitation tests predominantly mocks cannot prove durable restart/CAS behavior.
- Legacy voice maintenance callbacks are loaded but removed from public slash tree; residual lifecycle limitations in these methods have lower public reachability.
- Broad exception handlers were reviewed behaviorally; no finding is based solely on stylistic pattern or authorship inference.

## Verified claims versus reopened claims

Verified offline in precise scenarios: default personal task scope and explicit private cross-scope; setup recovery ownership/ACL retention; native staff revocation/log sealing; SQLite worker cancellation/draining; group teardown idempotence/final-focus retry; fractional timer/overflow/recovery counters; nullable role persistence/gated tree/view dispatch; check-in settings restart/isolation/failed-cancelled save. Source owner/start/pause/resume gates exist, but regular dropout recovery is broken.

Reopened: democratic vote correctness/staff immunity/failure consistency; complete session serialization; durable invitation restoration/CAS; comprehensive command audit; check-in owner durability. DATA-02 parentheses change is mathematically equivalent: A & (B-C) equals (A&B)-C. No precedence-bug fix verified. Public slash changes require authorization reconciliation.

Detailed domain maps remain pending mapper work and must be refreshed after coding/debugger changes. All temporary executable probes were stdin-only or cleaned; the audit artifact directory is the intentional deliverable.
