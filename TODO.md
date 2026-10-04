# TODO

Updated on 2026-10-04 for the antigravity-fix / codex/default-vc-pomodoro-recovery branch. Checked items have implementation and offline regression evidence; historical verification counts describe earlier checkpoints.

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
- [x] Keep task commands usable in DMs.
- [x] Make task results and `/create_group` results public.
- [x] Combine initial group mentions, status, and controls in one dashboard message.
- [x] Persist `/set_mod_log_channel` and send group creation, ending, and purge event embeds without mentions.
- [x] Implement forced video participation with a 30-second warning and 60-second grace period; members without a camera or screen sharing are disconnected.

## Technical debt

- [x] Move SQLite I/O off the event loop using `asyncio.to_thread` or an approved async driver.
- [x] Replace placeholder productivity hours with measured, persisted session/voice time before presenting efficiency as real analytics.
- [ ] Decompose complex group and Pomodoro handlers into services.
- [x] Include the standalone command matrix in pytest discovery.
- [ ] Add explicit timeouts around external resource provisioning calls.
- [x] Validate `BOT_DEVELOPER_ID` and reject placeholder or invalid values.
- [ ] Add persistent retry tracking for Discord resources left behind when group cleanup lacks permissions.
- [ ] Add recovery for setup resources retained after failed saves, with explicit ownership checks before resource deletion.

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
- [x] Verify wizard ownership, persistence failures, legacy migration, exact-channel visibility, and unchanged operational message destinations with offline regressions (107 tests; mypy and Ruff pass on 2026-10-04).

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

- [x] Verify the 2026-10-04 combined implementation: 224 offline tests, full Mypy, Ruff lint/format, and whitespace checks. Live Discord behavior still requires staging validation.
- [x] Verify the 2026-10-04 antigravity-fix batch: 281 offline tests pass (includes Pomodoro recovery, full default VC selection/relocation, focus-time DAL, help/setup regression suites, and session-controls AsyncMock fix). No new dependencies.

- [x] Prevent default task-list results from exposing group tasks; require `all_groups: true` for cross-group listing and make cross-group results ephemeral.
- [x] Scope task persistence and default listings by `guild_id`, preventing cross-server task leaks.
- [x] Implement the rc4 category-based response visibility policy. The active-group/commands-channel policy above supersedes it.
- [x] Keep study-group voice channels when the last member leaves; retain explicit deletion paths.
- [x] Provide a `main.py` compatibility launcher for hosting panels whose default startup command targets `python3 main.py`.
- [x] Verify the candidate: 68 pytest tests, the asserted 54-flow standalone runner, mypy, Ruff lint, and Ruff formatting on Python 3.12.
- [x] Correct unsupported completion claims and synchronize commands, architecture, and issue documentation.
- [ ] Publish the verified commit, move the existing tag with an explicit lease, refresh the prerelease, and verify downloaded packages. This automation's GitHub network access is blocked.
