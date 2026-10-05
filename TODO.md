# TODO

Updated on 2026-10-05 for the antigravity-fix branch. Historical verification counts describe earlier checkpoints.

## Resumed security and persistence scope

- [ ] Verify durable setup recovery, guild operation serialization, and ownership rechecks after awaited work.
- [ ] Verify private logs under native-authority changes, category propagation, and failed role synchronization.
- [ ] Verify async wait cancellation, replacement task ownership, and cog shutdown before SQLite closes.
- [ ] Verify non-task activity/settings isolation across guilds; guild-granted developers are Level 4, while only `.env` `BOT_DEVELOPER_ID` is global Level 5 Supreme Commander.
- [ ] Persist and hydrate validated check-in settings; keep memory consistent after failed writes and teardown.
- [ ] Persist invitation lifecycle: six-minute warning, ten-minute expiry, restart recovery, and recipient/target validation.
- [ ] Record invitations, joins, and command authorization/action outcomes in guild-scoped SQLite audit and Discord logs.
- [ ] Validate current actor IDs, guild membership, role/tier, ownership, membership, and active targets across all commands and controls.
- [ ] Add an optional saved Setup default role and optional creation; require current guild/default-role membership for invitation recipients and apply the selected guild command gate.
- [ ] After verified implementation and QA, use two GPT-6 Luna low agents to rebuild `ARCHITECTURE.md` and create `database_architecture.md` with diagrams.

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
- [ ] Keep all task commands usable in DMs. Add/list/action menus work, and `/task_purge all_tasks:true` works; default DM purge still requires a server or group.
- [x] Make ordinary task and `/create_group` success results public in active group channels and the saved commands channel. Errors, menus, DMs, and cross-group results stay private.
- [x] Combine initial group mentions, status, and controls in one dashboard message.
- [x] Persist `/set_mod_log_channel` and send group creation, ending, and purge event embeds without mentions.
- [x] Implement forced video participation with a default 60-second total wait and a warning for the final 30 seconds; members without a camera or screen sharing are relocated to the saved default VC. Microphone enforcement remains off.

## Technical debt

- [x] Move SQLite I/O off the event loop using `asyncio.to_thread` or an approved async driver.
- [x] Replace placeholder productivity hours with measured, persisted attended Pomodoro focus time. Arbitrary study-group or voice-channel time is not measured.
- [ ] Decompose complex group and Pomodoro handlers into services.
- [x] Include the standalone command matrix in pytest discovery.
- [ ] Add explicit timeouts around external resource provisioning calls.
- [x] Validate `BOT_DEVELOPER_ID` and reject placeholder or invalid values.
- [x] Add persistent retry tracking for Discord resources left behind when group cleanup lacks permissions.
- [x] Recover retained setup channels/categories within the current process, with ownership checks and exact channel-permission rollback. Restart loses recovery handles; staff-role and membership changes remain outside rollback (ARC-08).

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

- [x] Verify the 2026-10-05 QA fixes: 402 offline tests, zero Mypy errors, Ruff lint/format, and whitespace checks. Independent scoped QA passes; live Discord behavior still requires staging validation.

- [x] Prevent default task-list results from exposing group tasks; require `all_groups: true` for cross-group listing and make cross-group results ephemeral.
- [x] Scope task persistence and default listings by `guild_id`, preventing cross-server task leaks.
- [x] Keep study-group voice channels when the last member leaves; retain explicit deletion paths.
- [x] Provide a `main.py` compatibility launcher for hosting panels whose default startup command targets `python3 main.py`.
- [x] Correct unsupported completion claims and synchronize commands, architecture, and issue documentation.
- [x] Publish `v1.0.0-rc.5` as a prerelease on `Vectorphy/Chief-Productivity-Officer` and verify downloaded packages. [Release](https://github.com/Vectorphy/Chief-Productivity-Officer/releases/tag/v1.0.0-rc.5); [successful CI](https://github.com/Vectorphy/Chief-Productivity-Officer/actions/runs/37234471606). No existing tags moved or release/main merges occurred.
  - Both authorized branches include workflow correction `817cccf` and exact CI pin `10acee4`; release tags/source remain `a01656c` on both repositories. CI verified that tag with 402 tests, zero Mypy errors, and Ruff. Downloads passed digest/integrity and exact membership checks: wheel 21, sdist 26, runtime ZIP 21, GitHub source ZIP 26; package version `1.0.0rc5`. No test/internal/secret/database/cache entries. Remote authorization was restored; exact Python `3.11.17` CI and publication on crispy-octo-happiness were subsequently requested.

- [x] Publish the same immutable `v1.0.0-rc.5` source on `Vectorphy/crispy-octo-happiness`, run validation/build on Python `3.11.17`, and verify downloaded assets. [Release](https://github.com/Vectorphy/crispy-octo-happiness/releases/tag/v1.0.0-rc.5); [successful release CI](https://github.com/Vectorphy/crispy-octo-happiness/actions/runs/37235239110). Both jobs used exact 3.11.17 and tag `a01656c`; 402 tests, Mypy, Ruff, and package checks passed. Downloaded wheel 21 / sdist 26 / runtime 21 / GitHub source 26 passed integrity, digest, version, exact membership, and tagged-source comparisons. Both repositories' general CI matrices passed 3.10, 3.11.17, and 3.12. Existing Chief release preserved.

## Verification history

The checked-TODO audit covers the earlier 53 supported items with corrected scopes; downloaded release verification on both repositories adds two deployment completion ticks. Code and database maps are in `docs/`. The unused study-group backup was removed; published rc.5 packages and GitHub source archive were downloaded and validated with tests retained in Git and excluded from deployment archives.

Earlier handoffs report checkpoints of 68, 107, 224, and 281 tests. These describe past branches or test selections and are not current verification evidence. The rc4 category-based visibility policy was superseded by exact commands-channel and active-group matching. The current evidence audit is in `docs/TODO_AUDIT.md`.
