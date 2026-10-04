# CPO implementation handoff

Updated 2026-10-04 for release/v1.0.0-rc.4 in the current workspace.

## Completed behavior

- Private staged setup selects or creates a category, creates/reuses commands and logs channels, and saves default member limits and group/Pomodoro lifetimes. Both lifetimes default to 86400 seconds. Created channels inherit category permissions; recorded setup channels synchronize on save.
- Normal replies are public only in active group channels or the exact configured commands channel. Help, errors, setup, and sensitive menus stay private. Other channels, threads, and DMs receive private replies. Operational dashboards, reminders, logs, and invitation DMs retain their destinations.
- Groups, check-ins, and Pomodoros initially admit only their creator. Added participants receive recipient-only DM Join/Decline invitations. Voice entry does not start or join Pomodoros.
- Pomodoro stages and check-in intervals are bounded at 2-240 minutes. UTC Pomodoro expiry continues during pause; an hour-left warning offers renewal by 24 hours from the current deadline.
- Current owners and staff end directly. Participants send the current owner a DM approval request; outsiders cannot request. Approval rechecks activity and ownership.
- Serialized per-guild group creation keeps UUIDs, uses username/session-number defaults, and suffixes duplicate names. Invitations resolve trimmed case-insensitive names and text/voice context, hydrating active persisted groups after cache misses.
- Force Video accepts camera or screen sharing. Group dashboards retain statuses but remove check-in/Pomodoro action buttons. Standalone channel/voice/role maintenance commands are excluded from the public tree.
- Authorization selects 4 Bot Developer > 3 Manager/Admin/Mod > 2 contextual Owner > 1 contextual Group Member > 0 Server Member. Profiles use a fixed title and only the invocation channel's group. Bot-added staff display Manager; native/server-synced staff display Admin or Mod.
- Manager listing immediately includes uncached users and configured/global developers, deduplicates by highest grant, and handles large lists within embed limits.
- CPO Manager/Bot Developer roles mirror grants and category/channel access without guild-wide permissions. Staff command runtime guards enforce authorization without default picker restrictions that hide commands from explicit Managers.
- Approved additive migrations store lifetime defaults and manager grant provenance. Staff sync removes stale server-synced rows while preserving explicit grants. Legacy staff level 2 normalizes to 3; legacy grants remain explicit because provenance cannot be reconstructed.
- Existing task CRUD, owner-checked menus, pagination, server/group scope, global opt-in lists/purges, and moderator event logging remain available.

## Agent responsibilities

- Design: group/dashboard flows, invitation lookup, naming, video handling, category inheritance, and staff roles.
- Coding: Pomodoro/check-in consent, bounds, lifetime/renewal, and session ownership.
- Database: approved migrations, atomic settings/staff synchronization, scope/rollback/migration tests.
- Feature rundown (GPT-5.6 Luna, low): read-only feature inventory and limitations.
- Debugger (GPT-6.1 Sol, extra high): final code/test failures, guards, picker metadata, stale native role access, and full verification.
- Root: utilities, manager/setup integration, approval controls, help, docs, final review, and Git operations.

## Remaining work and limits

- Default VC creation during setup and relocation after video/microphone enforcement are backlog tasks in TODO.md. Force Video currently disconnects members. Microphone participation enforcement is not enabled.
- Running Pomodoro state is memory-only and does not survive restart. Saved lifetime defaults persist. A runtime persistence schema remains to be agreed.
- Productivity task counts use stored tasks; time spent is a random placeholder and efficiency is not measured analytics.
- SQLite operations are synchronous under an async lock. External provisioning timeouts and persistent cleanup retries remain debt.
- Discord changes cannot be transactional with SQLite. Failed setup saves may retain resources, roles, membership, or permissions. Failed group deletion may leave resources for manual cleanup.
- Legacy explicit grant provenance may need manual review. Live Discord DM delivery, role hierarchy, and provisioning remain untested.

## Verification and publishing

Final verification: 224 offline tests pass, including the standalone command matrix. Full Mypy reports zero errors; Ruff lint/format and Git whitespace validation pass. Tests use offline mocks and in-memory SQLite; no production resources were changed. Only the upstream audioop deprecation warning remains.

The first batch is pushed as eff178b642b7d5be14d0c9d71877c60dbad02e9e. Both remotes point to https://github.com/Vectorphy/crispy-octo-happiness.git. The user authorized commit/push of this completed batch. No merge with main, tag move, release publication, or PR is part of this checkpoint.

Read AGENTS.md, KNOWLEDGE_GRAPH.md, and KNOWN_ISSUES.md before further edits. Exclude database/cache/environment artifacts. The ignored repaired venv runs bundled Python 3.12.14 and Discord.py 2.7.1. The upstream audioop warning remains.
