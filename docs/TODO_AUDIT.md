# Checked TODO implementation audit

Read-only source audit, 2026-10-05; antigravity-fix, HEAD 16d7266 plus existing local fixes. No live Discord calls or source edits. References below use TODO.md line numbers at audit start. Each original checked item is accounted for.

Initial audit of 58 checked items: 48 implemented, 5 partial, 5 unsupported as current implementation claims (historical/superseded checkpoints). Unsupported does not mean the historical run did not happen; retained dated run logs are needed to authenticate it. Implemented means active code supports the requirement with the stated offline evidence, not production verification.

Verification rerun: all 387 collected tests passed; Mypy reported no issues in 34 source files, Ruff lint passed, and Ruff format reported 34 files already formatted. Mypy notes untyped bodies are not fully checked. Pytest emitted upstream audioop deprecation and cache write-permission warnings. The tests do not prove delivery, hierarchy, or provisioning in a real guild. File-cleanup structural pass applied; no prose-humaniser skill used.

Initial recommended checklist corrections (subsequently handled in the follow-up below): uncheck line 81 until default guild listing excludes group tasks and a real-DAL regression passes; uncheck line 87 until these claims are corrected. Rewrite line 20 to identify the DM task_purge limitation; rewrite line 21 as context-dependent public success results, matching line 52. Line 24 was corrected by the coordinating agent during the audit to 60 seconds total with a final 30-second warning; retain the corrected tick. Qualify line 35 with in-memory/restart and staff-mutation limits (ARC-08). Move lines 53,78,79,86 to a dated verification-history paragraph with retained logs or label counts unverified historically; move line 83 to superseded history. No missing feature is proposed.

## Follow-up after task-scope fix and checklist corrections

Rechecked active source, the new real-SQLite fixture/assertions, and corrected TODO wording on 2026-10-05. Original TODO line references and findings above remain as the initial audit record; the following supersedes their current status.

The original 58 items now classify as 52 implemented under their corrected scope, one partial requirement moved to unchecked backlog (original line 20, default DM purge), and five historical/superseded records moved out of the checked list (original lines 53, 78, 79, 83, 86). The current TODO has **53 checked items**, all supported within their documented offline scope: 52 retained implemented items plus the new current QA-verification item. No currently checked item remains partial or unsupported. Historical test counts remain history, not reconstructed evidence.

- Original line 81 is now implemented: `database.py:1596` adds `guild_id = ? AND group_id IS NULL` when both `global_only` and `guild_id` are supplied. `cogs/tasklist.py:241,284` supplies both for outside-group menus and default listings. Explicit all-groups listing remains private and all-scope analytics queries remain unchanged.
- New `tests/test_tasklist.py:133` fixture uses real in-memory SQLite, two guilds, three groups, a DM task, server tasks, group tasks, and a second owner. Tests at lines 180, 194, 214, 227 cover four default contexts, two explicit cross-group contexts, eight completion/deletion menu contexts, and one analytics case: 15 new parametrized cases. Assertions inspect actual returned tasks/menu options and visibility, rather than only mocked DAO arguments. `tests/test_database.py:186` also checks the combined flags directly. This auditor reran `tests/test_tasklist.py` with cache disabled: all 21 cases passed.
- Original lines 21 and 35 now have implemented, accurate labels: contextual public success results and recovery within the current process, with restart/staff-change limitations stated. Original line 24 remains implemented with the corrected 60-second total timer/final 30-second warning. Original line 20 is appropriately unchecked; the existing limitation remains, and no feature was added by the audit.
- Original line 87 is now implemented as documentation synchronization: TODO, `commands.md:79,91`, `ARCHITECTURE.md:13,29`, the knowledge-graph setup/task notes, and `KNOWN_ISSUES.md` reflect default task scope, measured attended focus, video timing, and setup recovery limits. The verification-history paragraph identifies earlier counts and the superseded category policy. This tick means those audit claims are corrected; it does not certify every old documentation link or diagram.
- The new current verification tick is supported by the debugger/coordinator's recorded full 402-test pass, 92 scoped tests, zero Mypy errors, and Ruff lint/format/whitespace checks. Those full checks were not redundantly rerun in this follow-up; the auditor independently checked the changed implementation and reran the 21 task-list tests. Live Discord delivery/provisioning remains unverified.

No further checkbox correction is recommended. No source file was edited by this auditor.

## Initial item-by-item audit

### Immediate refactoring

- **TODO.md:7 — Implemented.** Correct awaited Discord mocks and keep synchronous `InteractionResponse.is_done()` checks as `MagicMock`.
  Evidence: test_file.py:165 mock factory; tests/test_release_fixes.py:25 and tests/test_session_controls.py use synchronous MagicMock is_done.

- **TODO.md:8 — Implemented.** Fix the `/create_vc` dictionary lookup regression.
  Evidence: cogs/voice_channels.py:35 uses dict.get; standalone create_vc flows and tests/test_shared_controls.py:238 cover creation and storage rollback.

- **TODO.md:9 — Implemented.** Handle Discord error 10003 after `/purge_groups` deletes the invocation channel, with a DM result fallback.
  Evidence: cogs/study_groups.py:1920 _send_cleanup_result handles Unknown Channel and DM fallback; tests/test_release_fixes.py:365.

- **TODO.md:10 — Implemented.** Restore `InteractionResponse.is_done()` calls and test fresh interaction acknowledgement.
  Evidence: cogs/pomodoro.py:1284 calls is_done(); tests/test_new_features.py:97 checks fresh acknowledgement; standalone response factory tracks completion.

## Feature requirements

- **TODO.md:14 — Implemented.** Reject `/resume_pomodoro` when the session is already running.
  Evidence: cogs/pomodoro.py:1304 rejects not-paused sessions. Standalone pause/resume exercises success; direct rejection has source evidence but no dedicated regression identified.

- **TODO.md:15 — Implemented.** Support cross-group task listing through `/task_list all_groups`.
  Evidence: cogs/tasklist.py:255 list_tasks accepts all_groups; tests/test_release_fixes.py:255 verifies explicit cross-group query and private reply.

- **TODO.md:16 — Implemented.** Implement persisted Speak and Video on/off controls, preserve unrelated overwrites, and roll back after failed database writes.
  Evidence: cogs/study_groups.py:1148 _set_voice_permission snapshots/restores overwrites and persists; tests/test_release_fixes.py:110,629,643.

- **TODO.md:17 — Implemented.** Batch task purges and clean matching bot task messages owned by the invoker among the latest 100 messages in the current channel.
  Evidence: cogs/tasklist.py:343,394 and database purge methods batch record deletion and scan limit=100; tests/test_release_fixes.py:339,616.

- **TODO.md:18 — Implemented.** Provide owner-checked Select menus for completion and deletion, with exact row and group checks.
  Evidence: cogs/tasklist.py:13,64 and database.apply_task_action enforce owner and exact row/group; tests/test_release_fixes.py:216,560,590.

- **TODO.md:19 — Implemented.** Send recipient-only invitation DMs with Join/Decline controls, expiry, lifecycle and capacity checks, and serialized admission.
  Evidence: cogs/study_groups.py:34,332,1634 plus atomic DAL admission; tests/test_release_fixes.py:169,188,470,490,511.

- **TODO.md:20 — Partial.** Keep task commands usable in DMs.
  Evidence: cogs/tasklist.py guards absent guild/channel in add/list/menu handlers; tests/test_release_fixes.py:242 verifies DM deletion menu. Default task_purge requires server/group; only all_tasks=True works in DMs, so blanket task-command wording is too broad.

- **TODO.md:21 — Partial.** Make task results and `/create_group` results public.
  Evidence: cogs/tasklist.py and cogs/study_groups.py:1972 use should_use_ephemeral. Public only in active group/exact commands channel; errors, menus and sensitive/all-group results remain private. Original unconditional wording is superseded by TODO52.

- **TODO.md:22 — Implemented.** Combine initial group mentions, status, and controls in one dashboard message.
  Evidence: cogs/study_groups.py:652 send_welcome_message; tests/test_release_fixes.py:653 asserts one message combines mentions/embed/view.

- **TODO.md:23 — Implemented.** Persist `/set_mod_log_channel` and send group creation, ending, and purge event embeds without mentions.
  Evidence: cogs/study_groups.py:1880,1898 and database mod-log setting; tests/test_release_fixes.py:92,381,601,677. AllowedMentions.none prevents pings.

- **TODO.md:24 — Implemented.** Implement forced video participation with a default 60-second total wait and a warning for the final 30 seconds; members without a camera or screen sharing are relocated to the saved default VC. Microphone enforcement remains off.
  Evidence: cogs/study_groups.py:1245 and _voice_relocation.py:11; tests/test_release_fixes.py:130, tests/test_group_controls.py:404,420. Default timer is 60 seconds total: warning after 30, then 30 more. Coordinating agent corrected the checklist timing wording during this audit; no behavior change.

## Technical debt

- **TODO.md:28 — Implemented.** Move SQLite I/O off the event loop using `asyncio.to_thread` or an approved async driver.
  Evidence: database.py:22 _run_in_thread uses asyncio.to_thread and retains lock through cancellation; tests/test_database.py:469,487,499.

- **TODO.md:29 — Implemented.** Replace placeholder productivity hours with measured, persisted attended Pomodoro focus time. Arbitrary study-group or voice-channel time is not measured.
  Evidence: database productivity_focus_time DAL; utils.ProductivityService; cogs/pomodoro.py:552 accrual; tests/test_productivity_time.py, test_productivity_tracker.py:37,50, test_pomodoro_recovery.py:267,309,326,338.

- **TODO.md:31 — Implemented.** Include the standalone command matrix in pytest discovery.
  Evidence: tests/test_release_fixes.py:396 invokes run_all_feature_tests and asserts (54,54); collected in this audit full-suite run.

- **TODO.md:33 — Implemented.** Validate `BOT_DEVELOPER_ID` and reject placeholder or invalid values.
  Evidence: bot.py:19 validation via utils.validate_bot_developer_id; tests/test_bot_developer_id.py covers placeholders, invalid types, snowflake boundaries and bot initialization.

- **TODO.md:34 — Implemented.** Add persistent retry tracking for Discord resources left behind when group cleanup lacks permissions.
  Evidence: database.py:310,558 persists pending_resource_cleanups; cogs/study_groups.py:1679,1690 retries; tests/test_cleanup_retries.py and test_release_fixes.py:750 cover retry and ownership uncertainty.

- **TODO.md:35 — Partial.** Add recovery for setup resources retained after failed saves, with explicit ownership checks before resource deletion.
  Evidence: cogs/_setup_view.py:629 recovery and manager retained-draft handling; tests/test_setup.py:581,642,672,693,712,754,782,799. Implemented within process only; restart loses provenance; staff-role/membership changes are outside rollback (ARC-08).

## Release audit

- **TODO.md:39 — Implemented.** Restore standalone success assertions, real task IDs, and mandatory dashboard callback execution.
  Evidence: test_file.py command assertions, real returned task IDs and mandatory dashboard callbacks; tests/test_release_fixes.py:396 asserts all 54 flows.

- **TODO.md:40 — Implemented.** Isolate `test_file.py` with an in-memory database and close the bot in `finally`.
  Evidence: test_file.py run_all_feature_tests constructs DBHandler(":memory:") and finally closes bot; tests/test_release_fixes.py:396 executes this path.

- **TODO.md:41 — Implemented.** Replace the destructive migration with additive schema changes; preserve rows, legacy roster references, and stable primary keys.
  Evidence: database.py:create_tables additive migration, no DROP TABLE; tests/test_release_fixes.py:53,401,439 verify rows/rosters/IDs.

- **TODO.md:42 — Implemented.** Cover the earliest schema, historical table names, partially migrated IDs, and repeated startup.
  Evidence: tests/test_release_fixes.py:53 parametrizes missing_id/partial/legacy_names; :401 earliest schema and repeat startup.

- **TODO.md:43 — Implemented.** Remove ended groups from active lookups and remove related Pomodoro aliases during cleanup.
  Evidence: database.py active lookup predicates/retirement; cogs/study_groups.py cleanup and cogs/pomodoro.py:772 alias removal; tests/test_release_fixes.py:439,523,705 and test_session_controls.py:374.

- **TODO.md:44 — Implemented.** Check permission denial, malformed selections, missing resources, failed API calls, and persistence rollback.
  Evidence: tests/test_release_fixes.py:156,590,643,629,616 and test_setup.py persistence failures exercise these cases; this is test coverage, not exhaustive live API verification.

## Setup and reply visibility

- **TODO.md:48 — Implemented.** Open an invoker-owned private setup wizard on every `/setup` invocation, with existing-category selection and a new-category name modal.
  Evidence: cogs/manager.py:348 and _setup_view.py:18,83,302; tests/test_setup.py:143,170,401,499.

- **TODO.md:49 — Implemented.** Keep all settings staged until Save; Cancel and expiry leave the stored configuration unchanged. Reject Cancel while Save is in progress.
  Evidence: _setup_view.py:349,599,612 stages/save-lock; tests/test_setup.py:182,316,485. Stored settings stay unchanged on cancellation/expiry; provisioned Discord/staff mutations can remain after failed Save.

- **TODO.md:50 — Implemented.** Create or reuse `#cpo-commands` and `#cpo-logs` in the chosen category and save their IDs with the category and default member limit.
  Evidence: _setup_view.py:359 _save_locked and database.save_setup; tests/test_setup.py:143,287,401.

- **TODO.md:51 — Implemented.** Synchronize new and reused logs channels with category permissions and use the existing moderator activity log destination.
  Evidence: _setup_view.py provisioning/sync of logs channel and mod-log setting; tests/test_setup.py:287,383.

- **TODO.md:52 — Implemented.** Make normal slash success replies public in active study-group channels and the exact stored commands channel; keep threads, other channels, DMs, errors, and sensitive results private.
  Evidence: utils.py:19 should_use_ephemeral and acknowledge/send_response; tests/test_utils.py:12,33; tests/test_tasklist.py:32,65,84,106; test_release_fixes.py:301.

- **TODO.md:53 — Unsupported as current claim; historical/superseded.** Verify wizard ownership, persistence failures, legacy migration, exact-channel visibility, and unchanged operational message destinations with offline regressions (107 tests; mypy and Ruff pass on 2026-10-04).
  Evidence: Historical checkpoint: current ownership/failure/migration/visibility tests exist (test_setup.py, test_database.py, test_utils.py, test_new_features.py:175). Current run cannot establish the dated 107-test count or historical Mypy/Ruff result.

- **TODO.md:55 — Implemented.** Show newly added guild managers and bot developers immediately in `/list_managers`, without duplicate people or truncating large lists.
  Evidence: cogs/manager.py:785 list_managers includes stored grants, deduplicates/paginates; tests/test_shared_controls.py:281,314.

## Consent and session controls

- **TODO.md:59 — Implemented.** Add creator-only initial rosters and recipient Join/Decline invitations for groups, check-ins, and Pomodoros.
  Evidence: StudyGroup creator roster plus GroupInvitationView; CheckinInvitationView and PomodoroInvitationView; tests/test_group_controls.py:114 and test_session_controls.py:49,73,126,188.

- **TODO.md:60 — Implemented.** Remove voice auto-start and limit attendance, pings, and moves to opted-in Pomodoro participants.
  Evidence: cogs/pomodoro.py consent_members gating in presence/timer/invitations; no voice join auto-start listener; tests/test_new_features.py:43 and test_session_controls.py:126, test_pomodoro_recovery.py attendance regressions.

- **TODO.md:61 — Implemented.** Validate check-in intervals and Pomodoro stages at 2–240 minutes.
  Evidence: utils.py MIN_STAGE_MINUTES/MAX_STAGE_MINUTES and checkin/Pomodoro validation; tests/test_session_controls.py:26,224 and short-focus test :18.

- **TODO.md:62 — Implemented.** Add UTC Pomodoro expiry, expiry during pause, and 24-hour renewal with an hour remaining.
  Evidence: PomodoroRenewView and run_timer UTC expires_at; tests/test_session_controls.py:317,336,353.

- **TODO.md:63 — Implemented.** Persist configurable group/Pomodoro default lifetimes in setup; include both in stale-draft checks.
  Evidence: database setup lifetimes and _setup_view.py DurationModal/snapshot checks; tests/test_setup.py:95,113,130 and test_database.py:454.

- **TODO.md:64 — Implemented.** Route member end requests to the current owner's DM and enforce current ownership/activity on approval.
  Evidence: _session_controls.py EndRequestView validates current owner/live state and serializes approval; tests/test_shared_controls.py:75,89,102,115, test_group_controls.py:302,321,337,361, test_session_controls.py:447,515.

- **TODO.md:65 — Implemented.** Serialize group name allocation/provisioning per guild and retain UUIDs.
  Evidence: cogs/study_groups.py:1989,2079 per-guild creation lock and UUID IDs; tests/test_group_controls.py:242,253,266; historical names checked case-insensitively.

- **TODO.md:66 — Implemented.** Add private everyday `/help`; accept camera or screen sharing for video requirements.
  Evidence: cogs/help.py:13 private level-aware help; StudyGroup.has_video accepts self_video/self_stream; tests/test_shared_controls.py:128,141 and test_group_controls.py:404.

- **TODO.md:67 — Implemented.** Persist and hydrate Pomodoro deadlines, stages, pause state, and consented participants across restarts; agree a persistence schema first.
  Evidence: database pomodoro_runtime DAL; cogs/pomodoro.py:534,717 snapshots/hydration; tests/test_pomodoro_recovery.py:80,121,164,190,220,236. Consent restored; legacy explicit Present tracking resets. 15-second crash-loss target requires successful writes. Prior schema approval is session history, not provable from active code.

- **TODO.md:68 — Implemented.** Distinguish auto-synced staff grants from explicit grants so permission removals can revoke auto-synced authority safely. Preserve legacy grants as explicit because their original source cannot be inferred.
  Evidence: database grant_source defaults legacy rows to explicit and sync_native_staff_grants; cogs/manager.py:224,279 checks current native authority; tests/test_database.py:99,128,166 and test_staff_roles.py:82.

- **TODO.md:69 — Implemented.** Use the contextual five-level profile with Server Member wording and highest-level precedence.
  Evidence: cogs/manager.py:224,477 and utils contextual group/permission helpers; tests/test_shared_controls.py:158,188,201,215,224,379.

- **TODO.md:70 — Implemented.** Synchronize CPO Manager and Bot Developer roles with category/channel access and stored staff grants.
  Evidence: _staff_roles.py:68 sync_staff_roles plus manager grant/update/setup calls; tests/test_staff_roles.py:82,100,129,145,161,173,192,204. Failure reports saved grants and may leave partial Discord changes.

- **TODO.md:71 — Implemented.** Resolve group invitations from persisted records, case-insensitive names, and text/voice channel context.
  Evidence: cogs/study_groups.py:2645 _resolve_invite_group hydrates DB records and name/channel resolution; tests/test_group_controls.py:174,188,222.

- **TODO.md:72 — Implemented.** Remove check-in/Pomodoro buttons from the group dashboard and hide standalone resource maintenance commands.
  Evidence: StudyGroup.button_view :589 omits checkin/Pomodoro controls; voice_channels.setup hides resource maintenance app commands; tests/test_shared_controls.py:339 and dashboard regression.

- **TODO.md:73 — Implemented.** Add a default voice channel to `/setup`, create or reuse it under the selected category, and synchronize its permissions with that category. Persist its destination with a backward-compatible schema change after approval. When video participation enforcement removes a member from a study VC, move them to this default VC; handle missing destinations, full channels, and Move Members permission failures. Keep camera or screen sharing acceptable for video. (Microphone enforcement intentionally disabled per user directive).
  Evidence: _setup_view.py VoiceSelect/save and database default_vc additive migration; _voice_relocation.py handles missing/full/permission/API failure; tests/test_setup.py:232,244,515,527,540,560 and test_default_vc.py:27,37,62,70. Approval cannot be inferred from code; live hierarchy behavior remains unverified.

## Release verification and carry-over

- **TODO.md:78 — Unsupported as current claim; historical/superseded.** Verify the 2026-10-04 combined implementation: 224 offline tests, full Mypy, Ruff lint/format, and whitespace checks. Live Discord behavior still requires staging validation.
  Evidence: Historical dated 224-test checkpoint; active source cannot authenticate the old run. Current full suite and static checks pass; live staging remains absent.

- **TODO.md:79 — Unsupported as current claim; historical/superseded.** Verify the 2026-10-04 antigravity-fix batch: 281 offline tests pass (includes Pomodoro recovery, full default VC selection/relocation, focus-time DAL, help/setup regression suites, and session-controls AsyncMock fix). No new dependencies.
  Evidence: Historical dated 281-test checkpoint; active source cannot authenticate the old run. Relevant recovery/default-VC/focus/setup/session suites now pass; no dependency changes made by this audit.

- **TODO.md:81 — Partial.** Prevent default task-list results from exposing group tasks; require `all_groups: true` for cross-group listing and make cross-group results ephemeral.
  Evidence: cogs/tasklist.py:255 calls get_user_tasks(user_id,guild_id=...) outside groups; database.py:1592 guild filter does NOT exclude group_id. Default commands-channel listing can publicly expose same-server group tasks. test_release_fixes.py:255 checks mocked call only; test_database.py:186 tests global_only separately. Concrete existing bug sent for debugging.

- **TODO.md:82 — Implemented.** Scope task persistence and default listings by `guild_id`, preventing cross-server task leaks.
  Evidence: database tasks.guild_id migration/add_task and get_user_tasks guild filter; tasklist add/default-list supplies current guild. Explicit all_groups intentionally queries all owned tasks privately. Old multi-guild rows lacking provenance stay unassigned; default does not expose them.

- **TODO.md:83 — Unsupported as current claim; historical/superseded.** Implement the rc4 category-based response visibility policy. The active-group/commands-channel policy above supersedes it.
  Evidence: Historical superseded policy: utils.should_use_ephemeral now uses exact commands-channel/active-group context, not category membership. Existing tick is not evidence category policy is active.

- **TODO.md:84 — Implemented.** Keep study-group voice channels when the last member leaves; retain explicit deletion paths.
  Evidence: cogs/voice_channels.py has no empty-channel voice listener; StudyGroup voice listener enforces video only; explicit delete_vc/end cleanup remain. No dedicated empty-VC preservation regression identified; source confirms absence of deletion path.

- **TODO.md:85 — Implemented.** Provide a `main.py` compatibility launcher for hosting panels whose default startup command targets `python3 main.py`.
  Evidence: main.py delegates bot globals/startup and cpo.run(TOKEN); source verified, no hosting panel or live launcher exercised.

- **TODO.md:86 — Unsupported as current claim; historical/superseded.** Verify the candidate: 68 pytest tests, the asserted 54-flow standalone runner, mypy, Ruff lint, and Ruff formatting on Python 3.12.
  Evidence: Historical 68-test checkpoint; current test_release_fixes.py:396 confirms 54-flow matrix, but dated Python/test-count/static-check assertion cannot be reconstructed from active code.

- **TODO.md:87 — Partial.** Correct unsupported completion claims and synchronize commands, architecture, and issue documentation.
  Evidence: commands.md, ARCHITECTURE.md, KNOWLEDGE_GRAPH.md and KNOWN_ISSUES.md cover active features/limits, but TODO20,21,81 and historical checkpoint wording still overstate current evidence; documentation synchronization is partial.
