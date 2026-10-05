# CPO resume workflow

Saved 2026-10-05. Project work is PAUSED by explicit user request. Rule creation does not resume implementation.

## Trigger and checkpoint

On "continue with this repo", "continue", or an equivalent request to resume CPO project work, read AGENTS.md, KNOWLEDGE_GRAPH.md, KNOWN_ISSUES.md and the latest HANDOFF.md pause checkpoint. Inspect branch, HEAD, git status and the current diff. Reuse available agents; if their sessions no longer exist, recreate the same roles using the profiles below and supply the current checkpoint. Saved profiles restore instructions/settings, not inaccessible private agent history.

If the user limits "continue" to another activity, follow that narrower scope. Remain paused without an explicit resume request. No scheduled automation or background work is authorized by this workflow.

## Agent profiles

- `/root/coding`: `gpt-6.1-sol`, effort `medium`. Implement fixes and meaningful regression tests. Own the current unfinished source/test changes. Never push or publish independently.
- `/root/debugger`: `gpt-6.1-sol`, effort `xhigh`. Receive QA findings, diagnose and fix remaining defects; avoid unrelated rewrites.
- `/root/todo_audit`: `gpt-6.1-sol`, effort `low`. Read-only evidence audit of checked TODOs; report unsupported claims and exact scope limits.
- `/root/code_mapping`: `gpt-6-luna`, effort `low` (latest user override during resumed work). After implementation and QA, retrace the codebase and rebuild `ARCHITECTURE.md` with diagrams; documentation only.
- `/root/database_mapping`: `gpt-6-luna`, effort `low` (latest user override during resumed work). After implementation and QA, retrace persistence and create `database_architecture.md` with diagrams; documentation only.
- `/root/setup_qa`: inherited parent model/effort, with no explicit override recorded. Read-only setup, staff-role, log-privacy and member-limit QA.
- `/root/cleanup_db_qa`: inherited parent model/effort, with no explicit override recorded. Read-only database, teardown, retry and migration QA.
- `/root/pomodoro_qa`: inherited parent model/effort, with no explicit override recorded. Read-only timer, recovery and focus-accounting QA.
- `/root/design`: inherited parent model/effort, with no explicit override recorded. System and architecture designs only; no implementation edits.
- `/root/cicd`: inherited parent model/effort, with no explicit override recorded. CI, clean deployment artifacts, remote branch pushes and authorized release operations.

Explicit overrides above are user-selected. Inherited profiles retain the parent's configured settings when recreated; their former exact values were not exposed and must not be invented. If a requested model is unavailable, report it and ask for a replacement rather than silently substituting. Terra was unavailable earlier; Luna 5.6 low was the earlier mapping selection, superseded by the user's GPT-6 Luna low request during resumed work.

## Sequential execution

1. Resume coding's unfinished implementation from the working tree. Use design only for an unresolved architectural decision.
2. Run setup QA, database/cleanup QA and Pomodoro QA one at a time. QA reports findings and never edits code.
3. Pass QA findings to the debugger; rerun affected QA sequentially after fixes.
4. Run TODO audit and refresh code/database maps with their existing agents only where changed source invalidates evidence.
5. Complete modified-module tests, full offline pytest, Mypy, Ruff lint/format and whitespace checks. Synchronize governance documents and inspect staged artifacts.
6. Reuse CI/CD for approved remote work after verification. Confirm local/remote hashes and successful Python 3.11.17 CI. Stop rather than merge, force-push or move existing tags without explicit authorization.

Only one subagent may work at a time. Parent coordination may continue. Keep tokens conservative: targeted reads, concise findings, no new features, no redundant test reruns once the final checks pass.

## Preserved approvals and constraints

- The user approved additive `setup_recovery_journals` storage on 2026-10-05. See the design in ARCHITECTURE.md and checkpoint in HANDOFF.md; do not ask again for this approved schema.
- During resumed work, the user approved additive `checkin_guild_settings` storage on 2026-10-05 for validated per-guild configuration and permission lists, startup hydration, and database commit before memory updates. See ARCHITECTURE.md; do not ask again for this approved schema.
- The user also approved additive `session_invitations` and `command_audit_events` tables on 2026-10-05. Invitations warn after 360 seconds and expire after 600 seconds; persist lifecycle/notification state for restart. Log invitations, joins, and command outcomes in guild-scoped SQLite audit alongside Discord logs. Validate current actor/target IDs, guild, permission tier, ownership/membership, and lifecycle for all commands and controls. This supersedes the original fixes-only constraint.
- The user approved nullable `guild_settings.default_role_id` plus Setup-created-role journal tracking on 2026-10-05. Optional picker/creation, no auto-enrollment; null role is unrestricted. Strict selected-role gate applies to guild commands/controls including staff, except authorized Setup configuration/recovery. Invitations require current server membership and selected-role membership, without staff bypass. Personal DM task behavior remains available.
- User requests completion of partial DM purge/setup recovery, setup member-limit propagation to NEW study groups and their voice capacity, and logs visible only to permission Levels 3–4 plus required bot access.
- Later user steering on 2026-10-05 authorizes a sixth permission tier: `.env` `BOT_DEVELOPER_ID` alone is global Level 5 Supreme Commander; command-granted Level 4 developers are guild-scoped. All non-task activity and settings remain guild-isolated, including operations by the Supreme Commander. Explicit cross-scope task operations remain available. Public slash signatures and dependencies stay unchanged. Video relocation only; microphone enforcement stays off. No humaniser skill. No production Discord actions.
- The resumed review also covers races, cancellation, async waits, background task ownership, and orderly shutdown. Use targeted regressions for confirmed defects.
- Latest pre-pause remote authorization allows verified branch pushes to both Vectorphy/crispy-octo-happiness and Vectorphy/Chief-Productivity-Officer. The stop request suspends all work until resume; more recent user instructions override this checkpoint.
- Both existing `v1.0.0-rc.5` tags/releases are immutable at `a01656c77c637bbf831624fa9b917d19961ae2b1`. Later partial fixes are not in those releases. Do not move those tags or replace their assets as part of a branch fix.
- Keep regression tests in Git, but exclude tests, audits, internal automation, redundant backups, secrets, databases and caches from deployment packages/source archives. Maintain packaging allowlists and export-ignore.

On the next stop, interrupt active agents, update HANDOFF.md with actual edits/checks and remaining work, preserve local files, and end the turn. Do not commit/push the pause checkpoint unless separately requested.
