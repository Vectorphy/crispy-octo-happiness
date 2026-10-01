# TODO

Verified on 2026-10-01 against the rc3 candidate based on `c7bdca3`. Checked items have implementation and regression evidence.

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
- [ ] Implement forced camera participation; Video currently allows or denies camera and screen sharing.

## Technical debt

- [ ] Move SQLite I/O off the event loop using `asyncio.to_thread` or an approved async driver.
- [ ] Decompose complex group and Pomodoro handlers into services.
- [x] Include the standalone command matrix in pytest discovery.
- [ ] Add explicit timeouts around external resource provisioning calls.
- [ ] Validate `BOT_DEVELOPER_ID` and reject placeholder or invalid values.
- [ ] Add persistent retry tracking for Discord resources left behind when group cleanup lacks permissions.

## Release audit findings

- [x] Restore standalone success assertions, real task IDs, and mandatory dashboard callback execution.
- [x] Isolate `test_file.py` with an in-memory database and close the bot in `finally`.
- [x] Replace the destructive migration with additive schema changes; preserve rows, legacy roster references, and stable primary keys.
- [x] Cover the earliest schema, historical table names, partially migrated IDs, and repeated startup.
- [x] Remove ended groups from active lookups and remove related Pomodoro aliases during cleanup.
- [x] Check permission denial, malformed selections, missing resources, failed API calls, and persistence rollback.

## Release verification

- [x] Verify the candidate: 60 pytest tests, the asserted 54-flow standalone runner, mypy, Ruff lint, and Ruff formatting on Python 3.12.
- [x] Correct unsupported completion claims and synchronize commands, architecture, and issue documentation.
- [ ] Publish the verified commit, move the existing tag with an explicit lease, refresh the prerelease, and verify downloaded packages. This automation's GitHub network access is blocked.
