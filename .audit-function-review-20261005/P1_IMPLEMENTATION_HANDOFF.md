# P1 implemented batch — frozen for scoped audit

All runtime/test edits stopped. Latest user order: audit implemented delta first, debugger second. No P2 edits yet. Preserve preexisting dirty source.

## Scope and evidence

P1_SCOPE_MANIFEST.json enumerates 17 touched files,73 scoped functions with line ranges/function hashes and final raw-file hashes. p1_implemented_snapshot contains byte-exact final snapshots. The pre-P1 audit snapshot retained hashes/inventory but no complete source bytes. A byte-complete pre-edit diff cannot be supplied; HEAD diff includes preserved Antigravity edits and MUST NOT define audit scope. Review only listed implemented functions/operations and directly related regressions. Setup modal/View base inheritance and imports are explicit additional operations.

## Implemented finding linkage

- VOTE-01: prune departed ballots against current electorate in both required-vote helpers. New departed-vote regression.
- VOTE-02/04: removal returns a success outcome; owner transfer/removal and durable Pomodoro membership share one SQLite transaction. Memory changes after commit; failed DB removal compensates group-role removal. Deterministic replacement uses lowest remaining user ID. New SQLite owner-update/member-delete trigger failures verify unchanged owner/roster and role restoration; successful removal verifies durable runtime membership. Both immediate and interactive kicks share removal.
- VOTE-03: current Manager authority/fresh target membership checked inside removal before destructive action; promotion after initiation regression uses real Level4 grant.
- VOTE-05: named/channel/fallback votekick checks same guild and active group, with initiator membership check at initiation. New cross-guild fallback regression.
- SEC-10: named join admits nobody; members get already-member status, others get invitation-only guidance. Matrix now denies uninvited joining then accepts a persisted invitation. New real SQLite no-admission regression.
- INV-01: access settings failure returns ineligible. OperationalError regression.
- INV-02: no synthetic row/send fallback or synthetic CAS success; callback runs only after durable claim. In-flight accepting invitations are not reset by a second action/tick. Recovery reconciliation is startup-only. Missing-row/false-CAS and concurrent two-service regressions.
- INV-03: CPO.on_ready hydrates sessions and calls restore; restore binds original IDs/deadlines/messages, registers views/timers and catches elapsed warning/expiry in tick. Real SQLite close/reconnect regression checks restored group hydration/custom IDs/message registration/original deadlines/warning flag. Checkin/Pomodoro restore paths implemented but not separately exercised in new restart tests.
- CHECK-01: selector revalidates actor/lifecycle/current member under join lock; existing-row CAS transfer checks active guild/session/expected owner/live target in SQLite before memory. No schema addition. New selector success/revoked/ended/DB-trigger-failure/durable-target-exited cases; close/reconnect validates owner.
- POMO-02: required runtime persistence raises storage errors/inactive-session errors so invitation participant addition rolls back. Real SQLite rejecting-runtime trigger regression verifies memory, persisted participants and pending invitation.
- GROUP-01: capture text ID immediately, retain created objects independent of cache, rollback every partial role/channel acquisition and journal failed Discord deletes through existing cleanup table. New voice-create Forbidden regression proves uncached text/role deletion.
- AUTH-01: missing Manager denies category setting/purge. New both-command regressions.
- AUTH-02: guild-manager commands refuse targets at Level4/5; existing developer controls remain responsible for those grants. Real Level3/Level4 DB grant regressions.
- AUD-01: general slash dispatch, AccessView/AccessModal dispatch/errors and setup View/modals persist identity-only invoked/handled/failed/denied access events. Handled describes dispatch completion, not domain success. Setup retains its existing access policy. New command/control audit SQL regression verifies guild/actor and absence of submitted private text.

## Verification

- Full default-order offline pytest:506passed on final source, unique temp/cache.
- New adverse regressions:22passed (including corrected actual Pomodoro callback execution).
- Mypy:0issues45source files, required read-only escalation for installed aiosignal ACL.
- Ruff lint/format45files and git diff whitespace:pass.
- Expanded focused run in manually supplied file order:362passed/6failed of368. All6are manager patch assertions after standalone release matrix module loading/unloading; manager file alone7passed and default-order full suite passes. Keep this order-dependent isolation issue OPEN for scoped auditor/debugger; do not hide it behind full-suite success.
- Earlier95test adverse/release/setup targeted run passed before six final owner/runtime cases were added; final22new regressions pass. These earlier checks are not claims for later changed bytes.
- Existing Discord audioop deprecation warning remains. No live Discord/login, production mutations, build/install, remote write or deployment. Packaging/release Python3.11.17 verification pending.

## Ownership / next work

Debugger receives frozen P1 files after strictly scoped audit. Parent owns governance documents; mappers own ARCHITECTURE.md/database_architecture.md. Coder may next edit ONLY cogs/tasklist.py and new tests/test_task_embed_limits.py for UI-01 after parent acknowledgement. POMO-01,ARC-12,UI-02,NOTIFY-01 overlap frozen files and remain deferred until explicit file release. Script/CI/test-gap work requires a later explicit disjoint-file allocation.

No new manifest dependency, schema, public slash signature or hierarchy expansion introduced. Previously added public /votekick and create_group mentions still need governance reconciliation under the saved earlier signature constraint. The last owner cannot remove themselves from an active group without ending it; removal preserves owner/roster instead of leaving an ownerless active group. Group kicks remove only the group role; unrelated roles are untouched; no new voice disconnection behavior added.

Known audit limits: no byte-complete pre-edit diff; invitation accepting reconciliation on restart assumes recovery rather than a simultaneous active worker; targeted checkin/Pomodoro restart and expiry notification delivery failures were not newly exercised. Permission target checks retain existing process/DB locking rather than adding a new target grant transaction. Audit implementation was tested at generic tree/View dispatch; every domain outcome has not been exhaustively replayed.
