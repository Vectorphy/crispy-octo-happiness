# Chief Productivity Officer (CPO) — Architecture & Technical Design

## 1. System Context & C4 Architecture Visualization

Source-based references: [code walkthrough](docs/CODE_WALKTHROUGH.md), [database map](docs/DATABASE_MAP.md), and [checked-TODO audit](docs/TODO_AUDIT.md). Deployment wheel, source distribution, and runtime ZIP are validated against allowlists by `.github/scripts/package_runtime.py`; QA tests and audit documentation remain in Git but are excluded from deployment packages.

The **Chief Productivity Officer (CPO)** is an asynchronous, event-driven Discord application built on `discord.py` 2.4.x and Python 3.10+. It orchestrates productivity tools, collaborative study environments, Pomodoro focus cycles, standup check-ins, and personal task management across Discord guilds.

### rc3 lifecycle and persistence changes

Study group startup migrates legacy records with additive columns and identifier backfills. Historical table names are renamed only when current tables are absent. Legacy roster IDs remain connected to the same numeric group rows, and repeated startup preserves the migration. Saving an existing group retains its primary key. Earlier records without an activity flag stay inactive, with neutral defaults for fields absent from their original schema.

Each group owns a membership lock shared by direct joins, invitation admission, voice-setting changes, and the transition into teardown. Invitations arrive by DM with recipient-only Join/Decline controls and five-minute expiry. Admission grants the role and persists the roster before changing memory; failed persistence attempts to remove the newly granted role. Teardown blocks further admission, marks the persisted group inactive, removes current roster entries and related session aliases, and stops the dashboard controls. When Discord API deletions (text channels, voice channels, or roles) fail due to missing bot permissions or transient API errors, the uncleaned resources are recorded in the `pending_resource_cleanups` table. A background task (`cleanup_retry_loop` every 10 minutes) and startup sweep in `bot.py:on_ready` automatically re-attempt deletion when permissions are granted or prune records when the resources are confirmed gone on Discord. Server managers can also trigger `/retry_cleanups` for immediate execution and status inspection.

The initial group dashboard combines mentions, the status embed, and controls. Speak and Video preserve unrelated voice permission overwrites. A failed settings write triggers a Discord rollback; a failed rollback is logged for manual recovery. With the default 60-second wait, Force Video warns members for the final 30 seconds before relocating members without camera or screen sharing to the configured default voice channel (`CPO Lobby`, `guild_settings.default_vc_id`) via `cogs/_voice_relocation.py`. If relocation is unavailable or fails, an error is logged and a private notification is sent via DM without disconnecting the member.

Task Select menus carry primary row IDs and pass the owner and exact group to `DBHandler.apply_task_action`. This prevents a legacy task number from affecting multiple rows. Task command acknowledgements follow the group/commands-channel visibility policy. Purges batch database deletion, then inspect only the current channel's latest 100 messages for bot task messages attributed to the requesting user. A Discord cleanup failure is reported privately without undoing successful database deletion.

`guild_settings.mod_log_channel_id` stores the optional destination for group lifecycle embeds. Event logs include the actor and group, suppress mentions, and tolerate missing channels or logging failures. If cleanup deletes the invocation channel and Discord returns error 10003, the final command result is sent by DM. If that DM also fails, the result is logged.

Offline verification covers these flows in pytest and executes the standalone 54-command matrix against an in-memory database. API calls are mocked; live Discord provisioning remains outside these checks.

### QA corrections, 2026-10-05

Group teardown has a separate ending state and a lock around the full operation. The background lifetime monitor waits while teardown is in progress and survives failed final persistence; duplicate calls cannot repeat deletion after the group is cleared. Discord NotFound responses count as completed cleanup. Pending deletion retries serialize and check guild, resource type, active group references, and saved setup resources. Lookup failures retain the retry record.

SQLite operations run in workers while the database lock is held. Cancellation waits for the worker to finish before releasing the lock, including repeated cancellation. Connection opening and closing use the same lock.

Pomodoro attendance responses and explicit Present status use separate sets. Focus credit requires consent, Present status, and, in voice mode, current presence in the session VC. Gateway downtime, breaks, pauses, and dropout do not earn credit. Recovery reconciles cumulative counters with saved analytics by tracking ID. A failed final accounting write pauses the session and keeps its counters for retry; group teardown does not finish until that write succeeds.

Setup recovery shares the Save lock, requires current staff authority in the correct guild, and fails closed when ownership queries fail. The durable journal captures original categories and permission overwrites for exact restoration after restart. Failed recovery retains unresolved resource IDs and intents; another `/setup` retries recovery before replacing the draft. Staff synchronization follows the settings commit, so a failed precommit Save does not mutate staff roles or memberships.

### Server setup and reply visibility

### Durable setup recovery

The remaining restart-recovery work uses a single durable journal per guild, with `guild_id` primary key, unique `operation_id`, `owner_id`, `phase` (`prepared`, `committed`, `sync_pending`), versioned `state_json`, `last_error`, and timestamps. An additive `setup_recovery_journals` table and phase index preserve existing settings. The JSON records original/desired settings, operation intents/results, created resource IDs, moved channel IDs, original categories, and permission overwrite targets with allow/deny bitfields. Recovery checks current authority and resource ownership before any rollback.

Intent is persisted before each Discord mutation and its result before the next mutation. Settings and the journal's committed phase are written atomically. Staff synchronization follows that commit; failed settings writes therefore cannot mutate staff roles or memberships. Failed staff synchronization becomes durable pending reconciliation rather than rollback of committed settings. `/setup` and readiness handling resume pending work under the existing guild lock.

Configuration and group allocation share a per-bot guild operation lock with recovery. Recovery checks current settings and active resource ownership again after recording rollback intent and before changing Discord resources. Staff synchronization and log ACL updates use a separate staff lock, acquired after the guild lock when both are needed. Discord member, role, and ownership events reconcile native authority changes. Log overwrites explicitly deny CPO staff-role visibility so category permission changes cannot reopen access through stale membership.

A crash between Discord resource creation and saving its returned ID leaves an uncertain intent. Recovery retains that intent and requires a unique matching bot audit entry before resolving the resource ID; it never identifies resources by name. Missing or ambiguous audit evidence keeps recovery pending. This design adds no public command or permission tier. The user approved the additive recovery table on 2026-10-05.

`/setup` opens an ephemeral wizard on every invocation. Its existing `max_members` and `category` options seed a draft. The invoker can select an existing guild category or enter a new category name, then review the draft before Save. Controls belong to the invoker. Cancel and expiry discard the draft.

Save resolves the chosen category and creates `cpo-commands` and `cpo-logs` text channels or reuses their recorded channels, alongside creating or reusing the `CPO Lobby` default voice channel. Commands and lobby channels synchronize with the selected category. Logs use separate overwrites: default and other role/member access is denied, current staff receive direct member grants, and the bot retains required access. Stale CPO staff-role membership cannot grant log visibility. The logs channel receives group creation, ending, and purge events; runtime logs continue through the Python logger.

The database stores the category ID, commands channel ID, moderator log channel ID, default voice channel ID (`default_vc_id`), default member limit, and default group/Pomodoro lifetimes together. The lifetime editor accepts positive durations; both settings initially store 86400 seconds and affect new sessions. The approved migration adds these columns without replacing existing settings. The stale-draft snapshot includes both lifetimes and default VC destination. The logs channel uses the existing `guild_settings.mod_log_channel_id` field. Startup adds the nullable `guild_settings.commands_channel_id` and `guild_settings.default_vc_id` columns to existing databases; null values preserve existing defaults until setup is saved.

Discord provisioning and the SQLite write are separate operations. If a Save attempt creates resources and later fails, the wizard retains their IDs for a retry and prevents switching the draft to another category. Existing recorded channels can also remain moved after a failed settings write. Cancel and expiry disclose created or moved resource IDs for review. Created resources are not automatically deleted, and moved channels are not automatically restored.

Normal slash success replies are public in active study-group channels and the exact saved commands channel. Threads, other channels, and DMs use ephemeral replies. An unset commands channel still permits public replies in active groups. Errors, sensitive results, and the setup wizard are always private. The category controls study group placement; it does not grant public reply visibility. Dashboards, reminders, Pomodoro announcements, moderator logs, and invitation DMs keep their operational destinations.

Commands acknowledge the interaction privately before processing. A separate follow-up carries the final success or error with its own visibility, then removes the temporary acknowledgement. This avoids Discord's first deferred follow-up inheriting an earlier public response flag.

### Consent, ending, and lifetime controls

### Check-in configuration persistence

The additive `checkin_guild_settings` table (`guild_id INTEGER PRIMARY KEY`, `state_json TEXT NOT NULL`, and `updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`) persists validated per-guild check-in policies. Versioned JSON stores `max_members`, `min_duration`, `max_duration`, `max_absences`, `max_breaks`, `max_user_sessions`, `permission_mode`, and channel/role allow and deny lists. Existing session tables remain intact. Locked parameterized getters and saves validate identities, durations, bounds, and list values. Startup loads each guild's saved configuration; settings commands commit the candidate before replacing memory. Failed writes preserve both the stored configuration and the active in-memory settings.

### Durable invitations and command audit

The additive `session_invitations` and `command_audit_events` tables provide durable invitation tracking and immutable audit trails. Invitations store a stable invitation ID, guild and target session identity/type, recipient and owner IDs, DM channel/message IDs, creation/warning/expiry timestamps, lifecycle status, and notification flags. Invitations are stored with 360-second warning and 600-second expiry deadlines; interactions attempt to recheck expiry and target state. The DAL can read pending rows, but startup restoration is not wired (`INV-03`). Acceptance/decline use lifecycle transitions, with failed-transition fallback correctness still open (`INV-02`).

Audit rows store guild identity, actor ID, permission tier, target identity, action, outcome, and timestamp. The audited runtime records invitation actions through `audit_action`, but general command/control call-site coverage is incomplete (`AUD-01`). IDs establish identity; usernames only label displays. Guild/resource provenance, current permission tier, ownership, membership, and active lifecycle checks are handler-specific and have open exceptions recorded in the audit report.

### Optional default role

The nullable `guild_settings.default_role_id` column and durable journal tracking for a Setup-created role provide strict access gating. Setup offers an existing role picker and optional role creation when none is selected. No members are automatically enrolled. A null role leaves guild use unrestricted. With a selected role, guild commands and controls require current membership in it, including staff; authorized Setup configuration/recovery remains available to prevent lockout. Invitation recipients must be current guild members and hold the selected role without a staff bypass. Role selection commits with the other settings. Newly created roles use intent/result journaling and conservative recovery ownership checks.

Group creation allocates a name under a per-guild lock and holds that lock through provisioning. Historical names and live sessions prevent reuse: unnamed groups use a username and session number, while custom-name collisions append a numeric suffix. Each group retains its UUID independently of the display name.

Creators join automatically. Mentioned users receive recipient-only DM Join/Decline controls before admission. Pomodoros maintain a separate opted-in participant roster for attendance, pings, and voice moves. The voice-state listener no longer starts sessions. Group dashboards retain session status fields, with check-in and Pomodoro action buttons confined to their session controls.

Staff grants carry `explicit` or `server_sync` provenance. Native staff synchronize at Level 3; sync removes stale native grants and preserves explicit grants. Older grants are migrated as explicit because their source cannot be inferred. `/user_level` uses only the active group in the invocation channel for owner/member levels and selects the highest applicable level.

`cogs/_staff_roles.py` creates or reuses CPO Manager and CPO Bot Developer roles with no guild-wide permissions, synchronizes their membership, and merges their access into the configured category and its children. New channels inherit that category's permissions. Existing children retain unrelated overwrites, including intentional Speak/Video settings. Manage Roles and role hierarchy failures leave database grants intact and return an actionable warning.

### 6-Tier Authorization Model

Global bot developer superuser authority (Tier 5: Supreme Commander) is anchored exclusively to `.env` `BOT_DEVELOPER_ID`. Command-granted developer permissions are Tier 4 (Bot Developer) and strictly guild-scoped; no command can assign Level 5. All non-task activity and settings remain guild-isolated, including operations by the Supreme Commander. To prevent accidental privilege escalation or import-time crashes from template configurations, `utils.validate_bot_developer_id` strictly validates Discord snowflakes (17–20 digits, positive 64-bit integer) and rejects known dummy IDs (`123456789012345678`), documentation strings (`your_discord_user_id_here`), generic placeholders (`placeholder`, `changeme`, `none`), repetitive digits, floats, and booleans. Invalid startup values log a structured warning and fall back safely to `None`.

Current group/session owners and guild staff end directly. Other current participants request the current owner's approval by DM. Shared controls serialize End/Keep running decisions and expire after five minutes; confirmation rechecks activity and captured ownership. Persisted group fallback rechecks the latest database record before cleanup. Outsiders cannot request ending, and failed owner DMs leave sessions running.

Pomodoros use UTC deadlines. The timer checks expiry before pause state, offers renewal with one hour left, and offers a new prompt for each renewed deadline. Renew adds 24 hours to the existing deadline. Each stage and check-in reminder interval is 2–240 minutes. Auto-calculated Pomodoro breaks use the 5:1:3 ratio with a two-minute minimum.

Pomodoro runtime state is persisted in SQLite (`pomodoro_runtime`) via periodic JSON snapshots (a 15-second target interval when writes succeed) serialized through `_runtime_lock`. Upon bot reboot, `load_active_sessions_from_db()` hydrates active sessions, advances stages offline if deadlines elapsed during bot downtime (without granting unearned focus credit), restores paused/running states, and resumes background tick loops. Ending or group teardown retires runtime records, preventing zombie session resurrection. Attended focus time is tracked in `productivity_focus_time` with monotonic cumulative seconds for opted-in participants present in voice during active focus stages, powering real unrounded efficiency metrics.

### 1.1 C4 Container Diagram

```mermaid
C4Context
    title C4 System Context & Container Diagram for Chief Productivity Officer

    Person(user, "Discord User", "A student, developer, or server member using slash commands and UI buttons.")
    Person(admin, "Server Admin / Manager", "Manages server settings, study groups, and elevated permissions.")

    System_Boundary(cpo_boundary, "Chief Productivity Officer (CPO) System") {
        Container(gateway_router, "Bot Runtime & Router", "Python / discord.py", "Maintains gateway connection, handles event loops, dynamically loads cogs, routes interactions.")

        Container(cog_layer, "Cogs / Extensions Layer", "discord.ext.commands.Cog", "Checkin, Study Groups, Pomodoro, TaskList, ProductivityTracker, Manager, VoiceChannels.")

        Container(domain_services, "Utils & Domain Logic", "Python", "Parameter validation, regex duration parsers, mention resolution, efficiency calculation.")

        ContainerDb(sqlite_db, "Persistence Engine", "SQLite 3 / asyncio.to_thread / asyncio.Lock()", "Stores study groups, members, standups, managers, guild settings, and user tasks off the main event loop.")
    }

    System_Ext(discord_api, "Discord Gateway & REST API", "WebSockets / HTTPS API for Discord interactions, voice states, channels, and embeds.")

    Rel(user, discord_api, "Executes slash commands, clicks UI buttons, enters voice channels")
    Rel(admin, discord_api, "Configures bot managers and guild constraints")
    Rel(discord_api, gateway_router, "Dispatches Gateway payloads and interaction events", "WSS/HTTPS")
    Rel(gateway_router, cog_layer, "Dispatches command callbacks & component interactions")
    Rel(cog_layer, domain_services, "Invokes validation, formatting, and metrics calculation")
    Rel(cog_layer, sqlite_db, "Reads/writes state models via thread-safe DAL", "async/await")
    Rel(cog_layer, discord_api, "Provisions text/voice channels, assigns roles, updates embeds", "REST API")
```

---

## 2. Component Topology & Structural Visualizations

```mermaid
graph TB
    subgraph Client ["🌐 Discord Client / Gateway"]
        DC[Discord App / User Client]
        Gateway[Discord Gateway Event Broker]
    end

    subgraph CoreBot ["🤖 CPO Core (bot.py)"]
        BotInit[CPO Bot Instance]
        Hook[setup_hook Extension Loader]
        Sync[AppCommand Tree Sync]
        ErrorHandler[Global Error Handlers]
    end

    subgraph FeatureCogs ["🧩 Extension Modules (cogs/)"]
        Checkin[CheckinCog]
        StudyGroup[StudyGroupCog]
        Pomodoro[Pomodoro]
        Manager[Manager]
        TaskList[TaskList]
        ProdTracker[ProductivityTracker]
        VoiceChan[VoiceChannels]
    end

    subgraph DomainCore ["⚙️ Domain & Validation Layer (utils.py)"]
        Val[validate_parameters]
        ParseDur[parse_duration / parse_seconds_to_hms]
        ParseMent[parse_mentions]
        ProdServ[ProductivityService]
        PermChecks[check_manager / is_group_creator]
    end

    subgraph Persistence ["💾 Persistence Layer (database.py)"]
        Lock[asyncio.Lock Concurrency Controller]
        DB[DBHandler SQLite DAL]
        Tables[(SQLite Database: bot_database.sqlite)]
    end

    DC -->|Slash Commands & UI Clicks| Gateway
    Gateway -->|Dispatches Events| BotInit
    BotInit --> Hook
    Hook -->|Loads| FeatureCogs
    BotInit --> Sync
    BotInit --> ErrorHandler

    Checkin --> Val
    Checkin --> ParseDur
    Checkin --> ParseMent
    StudyGroup --> Val
    StudyGroup --> ParseMent
    ProdTracker --> ProdServ
    VoiceChan --> PermChecks

    FeatureCogs -->|Asynchronous CRUD| DB
    DB --> Lock
    Lock --> Tables
```

---

## 3. Runtime Event & Interaction Pipelines

### 3.1 Slash Command Execution & Middleware Pipeline

```mermaid
sequenceDiagram
    autonumber
    actor User as Discord Member
    participant Discord as Discord API / Gateway
    participant Router as CPO Bot (Command Tree)
    participant Guard as Manager Decorators (@is_member, @check_user_groups)
    participant Cog as Feature Cog Callback
    participant Val as Utils Validator
    participant DAL as DBHandler (asyncio.Lock)
    participant Storage as SQLite (bot_database.sqlite)

    User->>Discord: Trigger Slash Command (e.g. /create_group name: "Python Group" max_size: 5)
    Discord->>Router: Interaction Payload (app_commands)
    Router->>Guard: Pre-execution Decorator Checks
    alt User reached session/group capacity
        Guard-->>Discord: Reject (Ephemeral Embed: "Limit reached")
        Discord-->>User: Display limit message
    else Within Allowed Limits
        Guard->>Cog: Forward to Cog Command Callback
        Cog->>Discord: Private interaction acknowledgement
        Cog->>Val: validate_parameters(name, max_members, ...)
        alt Validation Failure
            Val-->>Discord: Ephemeral Warning ("Invalid duration/name")
            Discord-->>User: Display validation error
        else Validation Passed
            Val->>Cog: Validated Clean Inputs
            Cog->>Discord: Provision Discord Category, Channels, and Roles
            Discord-->>Cog: Channel IDs & Role IDs Created
            Cog->>DAL: save_study_group(payload)
            DAL->>DAL: async with self.lock:
            DAL->>Storage: Execute INSERT/UPDATE query
            Storage-->>DAL: Commit Transaction
            DAL-->>Cog: Database Success
            Cog->>Discord: Send Interactive Embed with Dashboard View
            Discord-->>User: Display Group Active View
        end
    end
```

---

## 4. State Transition Visualizations

### 4.1 Pomodoro Study Cycle State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle: Study Group Created

    state ActivePomodoro {
        [*] --> FocusState: /start_pomodoro (Default 25m)
        FocusState --> PausedFocus: /pause_pomodoro
        PausedFocus --> FocusState: /resume_pomodoro

        FocusState --> ShortBreakState: Focus Timer Expires (Cycles < 4)
        ShortBreakState --> PausedBreak: /pause_pomodoro
        PausedBreak --> ShortBreakState: /resume_pomodoro
        ShortBreakState --> FocusState: Short Break Timer Expires (Increment Cycles)

        FocusState --> LongBreakState: Focus Timer Expires (Cycles == 4)
        LongBreakState --> FocusState: Long Break Expires (Reset Cycles = 0)
    }

    FocusState --> Idle: /end_pomodoro
    ShortBreakState --> Idle: /end_pomodoro
    LongBreakState --> Idle: /end_pomodoro
    PausedFocus --> Idle: /end_pomodoro
    PausedBreak --> Idle: /end_pomodoro
    Idle --> [*]: Group Terminated
```

### 4.2 Checkin Standup Session State Machine

```mermaid
stateDiagram-v2
    [*] --> Initialized: /checkin duration mentions
    Initialized --> ActiveMonitoring: Start periodic reminder loop

    state ActiveMonitoring {
        [*] --> IntervalCountdown
        IntervalCountdown --> BroadcastPrompt: Interval elapsed

        state BroadcastPrompt {
            [*] --> AwaitingResponse: Send Embed with Action Buttons
            AwaitingResponse --> PresentAction: User clicks [Present]
            AwaitingResponse --> BreakAction: User clicks [Break]
            AwaitingResponse --> ExitAction: User clicks [Exit]
            AwaitingResponse --> TimeoutAction: No response before deadline
        }

        PresentAction --> IntervalCountdown: Reset strike counter
        BreakAction --> IntervalCountdown: Set status to Break
        ExitAction --> RemovedFromSession: Clean up user from session
        TimeoutAction --> IncrementStrike: Absences += 1

        state IncrementStrike {
            [*] --> StrikeEvaluation
            StrikeEvaluation --> IntervalCountdown: Absences < max_absences
            StrikeEvaluation --> RemovedFromSession: Absences >= max_absences (Kick from session)
        }
    }

    ActiveMonitoring --> SessionComplete: Total session duration elapsed
    ActiveMonitoring --> SessionCancelled: Host / Manager ends session
    SessionComplete --> Cleanup: Remove channels/roles & persist final metrics
    SessionCancelled --> Cleanup
    Cleanup --> [*]
```

---

## 5. Security & Authorization Architecture

`Manager.get_permission_level(guild_id, user_id, member)` in [`cogs/manager.py`](cogs/manager.py) computes the highest applicable tier in the requested guild. Tier 5 comes only from the configured `BOT_DEVELOPER_ID`; persisted command grants are limited to Tier 4 and scoped to a matching guild. Guild owners and native administrators/manage-guild members are Tier 3; contextual group/session ownership and membership are Tier 2 and Tier 1. Regular users are Tier 0. A Supreme Commander’s non-task operations still use the current guild context.

```mermaid
graph TD
  L5["5 · Supreme Commander<br/>BOT_DEVELOPER_ID only"] --> L4["4 · Bot Developer<br/>explicit guild grant"]
  L4 --> L3["3 · Guild Manager<br/>native authority / synced grant"]
  L3 --> L2["2 · Group or session owner"]
  L2 --> L1["1 · Current group or session member"]
  L1 --> L0["0 · Regular server member"]
  Tree["AccessCommandTree + AccessView/AccessModal"] --> Role["Current guild membership + optional default-role check"]
  Role --> Tier["Manager.get_permission_level for command-specific authority"]
```

Guild interactions first pass the command-tree or contextual UI access gate in [`cogs/_access_policy.py`](cogs/_access_policy.py). The optional default role is checked for guild commands and UI controls, including staff; Setup has a narrow current-staff exemption. Command handlers then apply their domain-specific permission, ownership, membership, and lifecycle checks. Personal task use in DMs has no guild context.

## 6. Concurrency & Persistence Isolation Model

Because SQLite is an embedded file-based database, concurrent writes from asynchronous Discord tasks must be coordinated to prevent database lock contention.

```mermaid
graph LR
    subgraph DiscordTasks ["⚡ Asynchronous Discord Tasks"]
        T1["Checkin Ping Loop"]
        T2["Pomodoro Timer Loop"]
        T3["User Slash Interaction"]
        T4["Member Join Interaction"]
    end

    subgraph LockMechanism ["🔒 Synchronization Layer"]
        Lock{"asyncio.Lock()<br/>Thread-Safe Mutex"}
    end

    subgraph DBTransactions ["💾 DBHandler Operations"]
        Op1["execute(query, params)"]
        Op2["fetchall() / fetchone()"]
        Op3["commit()"]
    end

    subgraph StorageFile ["📁 File System"]
        File[("bot_database.sqlite")]
    end

    T1 -->|Acquires Lock| Lock
    T2 -->|Acquires Lock| Lock
    T3 -->|Acquires Lock| Lock
    T4 -->|Acquires Lock| Lock

    Lock -->|Isolated Execution| Op1
    Op1 --> Op2
    Op2 --> Op3
    Op3 --> File
    Op3 -.->|Releases Lock| Lock
```

---

## 7. Logging & Observability Architecture

```mermaid
graph TD
    subgraph CodeModules ["📦 Codebase Modules"]
        M1[bot.py]
        M2[cogs/*.py]
        M3[database.py]
        M4[utils.py]
    end

    subgraph LoggerPipeline ["📝 Logging Pipeline (docs/LOGGING_STANDARDS.md)"]
        LInit["Module Loggers (logging.getLogger(__name__))"]
        Format["Structured Formatter: %(asctime)s - %(name)s - %(levelname)s - %(message)s"]
        Levels{"Log Level Filter"}
    end

    subgraph Sinks ["📊 Outputs & Diagnostics"]
        Console["Standard Output (Console)"]
        AppTreeError["Discord Error Embed (Interaction Ephemeral)"]
        AuditTrail["Database Table (voice_channel_logs)"]
    end

    CodeModules --> LInit
    LInit --> Format
    Format --> Levels
    Levels -->|DEBUG / INFO / WARNING / ERROR / CRITICAL| Console
    Levels -->|Unhandled AppCommand Errors| AppTreeError
    Levels -->|Voice Channel Creation Events| AuditTrail
```

---

## 8. Authorization Tiers & Slash Command Visibility Architecture

All registered guild slash commands pass through `AccessCommandTree.interaction_check`; the handler then applies feature-specific limits and authority. The shared `AccessView` and `AccessModal` dispatch wrappers apply the same current-guild access check to component and modal callbacks. Context is derived from the view, its group, study_group, or session object. Denials are private. Slash registration is global in `setup_hook`; `on_ready` clears guild-specific command registrations.

Standalone maintenance callbacks defined in `cogs/voice_channels.py` are loaded as cog methods but are excluded from public command-tree exposure; their residual lifecycle reach is lower than the registered commands.

```mermaid
flowchart LR
  D[Discord interaction] --> T[Global app-command tree]
  T --> A{current guild + configured role?}
  A -->|no| X[private denial]
  A -->|yes| H[feature handler]
  H --> P{feature authority, owner/member and active state}
  P -->|no| X
  P -->|yes| R[scoped operation]
  V[Component or modal] --> A
```

## 9. As-Built Runtime, Function & State Map

**Evidence label:** this map describes the inspected source at `antigravity-fix`, Git HEAD `f9a39815354fe3f60208513f867b1502b42fb193`. Function-level review covered 1,008/1,008 function bodies, 50/50 lambdas, and 83/83 executable module statements across 49 first-party executable files. SHA-256 fingerprints for the reviewed files are recorded in [the audit snapshot](.audit-function-review-20261005/snapshot.json); audit findings are in [findings.json](.audit-function-review-20261005/findings.json). The source files matched those fingerprints when mapping began. During mapping, active coder edits caused current-source drift in `cogs/study_groups.py` and `database.py`; this text intentionally maps the audited pre-fix snapshot and must be reconciled after coding/debugger completion. Open-finding references below describe that audited snapshot, not an assertion that intermediate dirty code still has the same behavior. The audit is source review, not dynamic coverage or live Discord validation.

### 9.1 Runtime flow and verified call edges

```mermaid
flowchart TD
  U[Discord command, button, modal or gateway event] --> B[bot.py · CPO]
  B -->|setup_hook: connect DB, discover non-underscore cog files, load, sync| C[Cogs / extension setup]
  B -->|on_ready| REC[Pomodoro restore + pending cleanup sweep + guild-command cleanup]
  B -->|close → super.close| UNLOAD[Cog unload hooks drain owned tasks] --> DB[DBHandler.close]
  C --> ACCESS[_access_policy: guild and default-role guard]
  ACCESS --> DOMAIN[Handler, view callback or listener]
  DOMAIN --> SERVICE[Shared access, invite, setup, staff, controls, voice services]
  DOMAIN --> DAL[database.py async DAL]
  SERVICE --> DAL
  DAL -->|asyncio.Lock + cancellation-drained asyncio.to_thread| SQL[(SQLite)]
  DOMAIN --> REST[Discord REST / gateway state]
  REC --> DOMAIN
```

Verified lifecycle edges: `CPO.setup_hook` opens the DAL, loads each non-underscore `cogs/*.py` extension, and globally syncs the command tree. `CPO.on_ready` restores Pomodoro runtime, retries pending Discord resource cleanup, and clears guild-specific command registrations. Cog listeners independently restore Check-in sessions and reconcile Manager grants, log privacy, setup journals, and staff-role access. `CPO.close` shields `super().close()` and closes the DAL in `finally`; cog unload hooks cancel and drain owned loops/tasks. `main.py` is a compatibility launcher importing the `bot.py` singleton.

The persistent-invitation runtime edge is send → current recipient/session checks → row create → DM → message binding → `register` → per-invitation monitor → warning/expiry/action transition → feature callback. The DAL exposes pending-invitation reads, but the audited runtime has no startup restoration caller (`INV-03`). Failed transition/create fallback can still run the acceptance callback (`INV-02`); therefore this diagram records only the intended/observed path, not a guarantee of durable lifecycle correctness. `audit_action` exists and is used by invitation paths; general command/control coverage is incomplete (`AUD-01`).

### 9.2 Module and function responsibility map

| Module | Main function/class roles and important edges | Runtime state owner / boundary |
|---|---|---|
| [`bot.py`](bot.py), [`main.py`](main.py) | `CPO.setup_hook` loads extensions; `on_ready` recovery/sync; `close` / `_close_resources` shutdown; global command error handlers; `main.py` reuses `cpo`. | Bot owns DB client and command tree; no feature-session authority. |
| [`cogs/_access_policy.py`](cogs/_access_policy.py) | `require_guild_access` → `_require_guild_access`; `AccessCommandTree.interaction_check`; `AccessView` / `AccessModal` scheduled dispatch; `deny_access`. | Rechecks current guild membership and optional selected role; Setup exemption still requires Level 3. |
| [`cogs/manager.py`](cogs/manager.py) | `get_permission_level` resolves tiers; decorators gate participation/session limits; `setup` opens/resumes wizard; `on_ready` and authority listeners sync grants/privacy/access; manager commands mutate guild grants. | `guild_operation_locks(bot)` and `_setup_views`; grants are read using `(user_id, guild_id, grant_source)`. |
| [`cogs/_setup_view.py`](cogs/_setup_view.py) | Selects/modals stage settings; `prepare_journal` / intent/result writes; `_save_locked` provisions resources and commits settings; `from_journal` / recovery restore. Called from Manager Setup/resume. | One wizard and journal per guild; uses shared guild lock; journal tracks setup ownership, mutations and rollback data. |
| [`cogs/_staff_roles.py`](cogs/_staff_roles.py) | `Manager.sync_guild_managers` persists native grants through the DAL; `sync_staff_roles`, `sync_log_privacy`, and overwrite helpers provision/reconcile roles and channel ACLs. | Staff lock per guild; native staff grants and role/channel visibility remain guild-scoped. |
| [`cogs/study_groups.py`](cogs/study_groups.py) | `StudyGroup.setup_group_resources`, `add_member`, `remove_member`, `transfer_ownership`, dashboard callbacks, vote views, voice/video listeners, `end_group` → `_end_group`; `StudyGroupCog.create_group` → `_create_group_locked`, hydrate/resolution, cleanup retry. | `active_study_groups` owns live `StudyGroup`s; each group owns roster, resource IDs, end/membership locks and video tasks. Creation/config/setup use per-guild locks. |
| [`cogs/checkin.py`](cogs/checkin.py) | `CheckinCog.start_checkin` → `_start_checkin_locked`; `CheckinSession` resource/embed/reminder cycle; status/join/leave/owner/end callbacks; settings validate, persist then commit memory. | `active_sessions`, per-guild `guild_settings`, reminder-task registry; session rows own saved owner/times and member rows own status/absence. `join_lock` serializes roster/status paths. |
| [`cogs/pomodoro.py`](cogs/pomodoro.py) | `calculate_pomodoro_ratio`; start/edit/pause/resume/end handlers; `run_timer`; attendance and invitation views; `_persist_session`, recovery/restore and productivity accounting. | `Pomodoro.sessions` owns live sessions; `session.lock`, `_start_locks`, `_runtime_lock`, `_recovery_lock` cover selected paths only. Attendance, dashboard pause, gateway and retire paths remain gaps (`ARC-12`). |
| [`cogs/_invitations.py`](cogs/_invitations.py) | `eligible_recipient`; `InvitationService.send/register/act`; `monitor` → `tick` → `reconcile` / `notification` / `finish`; feature-specific callbacks perform admission. | Service holds view/task/action registries and per-invitation locks; DB holds invitation lifecycle/deadlines/message IDs. Startup restore is not wired; CAS/fallback gaps remain (`INV-01..03`). |
| [`cogs/_session_controls.py`](cogs/_session_controls.py) | `request_session_end` sends owner a DM; `EndRequestView.approve/decline` serializes decision and calls feature-provided end callback after activity/owner checks. | View owns one pending approval and decision lock; feature session remains authoritative. |
| [`cogs/_audit.py`](cogs/_audit.py) | `audit_action` records guild/actor/action/outcome/target via DAL and optionally logs to the group cog’s configured Discord channel. | Audit rows are guild-scoped. Call-site coverage remains incomplete (`AUD-01`). |
| [`cogs/_voice_relocation.py`](cogs/_voice_relocation.py) | `relocate_to_default_vc` checks configured destination/capacity and attempts member move; called from group video enforcement. | Destination ID is per guild; source/session identity is passed explicitly. |
| [`cogs/tasklist.py`](cogs/tasklist.py) | `add_task`, completion/action menus, `list_tasks`, `delete_task`, `purge_tasks`; channel context resolves group via DAL; menus pass task row IDs and owner to `apply_task_action`. | Task ownership is user ID; optional guild/group provenance separates personal, server and group tasks. UI size limits remain open (`UI-01`). |
| [`cogs/productivity_tracker.py`](cogs/productivity_tracker.py) | `/productivity` asks `ProductivityService` for aggregates and renders the result. | Reads user focus-time provenance, optionally filtered to current guild. |
| [`cogs/voice_channels.py`](cogs/voice_channels.py) | Legacy standalone VC/role/text creation and deletion handlers. | Discord resources plus `voice_channel_logs`; methods are not exposed as public slash commands in current tree. |
| [`cogs/help.py`](cogs/help.py) | `/help` renders command guidance based on current permission level. | No persistent state. |
| [`utils.py`](utils.py) | Shared `guild_operation_locks`, cancellation-safe `complete_operation`, response/ack helpers, visibility policy, parsing/validation, permission predicates/context group lookup, `ProductivityService`, developer-ID validation. | Lock registry is bot-scoped/per guild; helpers use caller-supplied interaction and guild provenance. |
| [`database.py`](database.py) | `DBHandler.connect/create_tables/close`, `_run_in_thread` and synchronous SQLite workers; DAL methods for setup/settings, groups/rosters, check-ins, Pomodoro runtime/focus, invitations/audit, cleanup, manager grants, tasks, and voice logs. | One DAL asyncio lock serializes SQLite access; worker completion is drained before cancellation can release the lock. See [`database_architecture.md`](database_architecture.md) for schema/transaction detail. |

### 9.3 Feature call paths and state ownership

| Flow | Call path (source symbols) | Authority and scope | Durable / transient owner |
|---|---|---|---|
| Group provision/admission | `StudyGroupCog.create_group` → `_create_group_locked` → `StudyGroup.setup_group_resources`; invite `send_invite` → `InvitationService.send` → `StudyGroup.add_member` → group DAL. | Current guild and group identity; invitee current membership/default-role checked; ownership/manager or invitation controls entry. `join_group` currently has open invite-only bypass `SEC-10`. | DAL `study_groups`/members plus Discord resource IDs; `active_study_groups` runtime copy. Partial create rollback gap `GROUP-01`; vote transfer/removal gaps `VOTE-01..05`. |
| Check-in | `/checkin` → `_start_checkin_locked` → persist/register → reminder task → callbacks → member/session DAL; startup hydrates rows in `cog_load`/`on_ready`. | Guild policy, selected role, current member; owner/manager and roster context checked per action. Owner change lacks durable write/revalidation (`CHECK-01`). | `checkin_sessions` owns session/owner/timing; member table owns status/absence; settings table plus `guild_settings` memory cache. |
| Pomodoro | `/start_pomodoro` → `_resolve_group` → session create/invite → `run_timer`; lock-selected pause/edit/resume/end; timer snapshots and focus upserts; `on_ready` hydrates runtime. | Group/channel guild provenance and owner/manager gate; participant consent + Present + (voice mode) session-VC presence for focus credit. Recovery and API paths listed above. | `pomodoro_runtime` serialized session state; `productivity_focus_time` cumulative attended-focus seconds; session object and timer task in memory. Persistence swallowing and resume guidance are open (`POMO-01/02`). |
| Setup/configuration | `/setup` → `SetupView.prepare_journal` → resource intent/create/result → `_save_locked` → settings+committed journal transaction → staff reconciliation; recovery reconstructs view from journal. | Current guild Level 3+ for Setup/recovery; guild lock and current ownership/ACL checks. | `setup_recovery_journals` durable operation record; `guild_settings` committed values; ephemeral draft view while process lives. |
| Task actions | command resolves current group by channel and requests scoped DAL query/action; menus carry exact task row IDs. | Actor ID plus personal/guild/group scope; personal DM scope remains available. | `tasks` rows; no task-session runtime cache. |
| Shutdown/recovery | Cog load/ready restores Check-in and Pomodoro state; `bot.on_ready` retries cleanup; unload stops loops/services and flushes Pomodoro; `CPO.close` closes DB last. | Each persisted resource is revalidated against guild and current runtime context. | SQLite is durable authority for active session rows; Discord owns provisioned IDs; in-memory cogs are hydrated projections. |

### 9.4 Tests, tooling and source boundaries

The reviewed audit inventory includes these executable/support areas: `tests/conftest.py` supplies fixtures; focused suites cover async lifecycle, developer ID, cleanup retries, DAL, default role/default VC, group controls, guild persistence, Manager roles, command features/response policy, Pomodoro recovery/productivity, release command matrix, session/setup recovery/setup wizard, shared controls, staff roles, tasks and utilities. [`test_file.py`](test_file.py) is a legacy standalone runner; its direct callback invocation bypasses command-tree/decorator dispatch and its “100%” banner is not runtime coverage evidence.

[`scripts/start-agents.ps1`](scripts/start-agents.ps1) is an orchestration script whose saved profile/order is stale relative to the latest user workflow; do not infer current execution order from it. [`update_changelog.py`](update_changelog.py), [`.github/scripts/extract_release_notes.py`](.github/scripts/extract_release_notes.py), and [`.github/scripts/package_runtime.py`](.github/scripts/package_runtime.py) are release/documentation utilities, not bot runtime. CI/release files, manifests and project configuration are integration boundaries rather than Discord handlers.

Source inventory evidence and per-function rows remain in `.audit-function-review-20261005/coverage.csv` and `coverage.json`; those files are the exhaustive function index. Their AST call/table/state metadata are candidates only, not a proven dynamic call graph.

### 9.5 Open findings that constrain this map

The audit reports deployment blocked. Open high-priority findings include vote/electorate/owner-transfer/removal and guild-resolution defects (`VOTE-01..05`), public named join (`SEC-10`), invitation role/CAS/startup restoration (`INV-01..03`), incomplete command audit (`AUD-01`), check-in owner durability (`CHECK-01`), Pomodoro failed-save/dropout recovery (`POMO-01/02`), partial resource provisioning (`GROUP-01`), and fail-open/manager demotion authority defects (`AUTH-01/02`). Open P2s include incomplete Pomodoro serialization (`ARC-12`), task and group list embed limits (`UI-01/02`), and sqlite.Row developer-alert handling (`NOTIFY-01`). Details and reproduction evidence are in [the audit report](.audit-function-review-20261005/AUDIT_REPORT.md). Nothing in this map establishes deployment readiness or closes these findings.
