# Chief Productivity Officer (CPO) — Target Architecture (Post-Audit)

This document outlines the **target architecture** integrating the newly audited requirements: Strict Invite-Only Groups, Democratic End-Group Voting, and Votekick with Staff Immunity.

---

## 1. C4 Container Diagram

```mermaid
C4Context
    title C4 System Context & Container Diagram (Target State)

    Person(user, "Discord User", "A student or server member")
    Person(admin, "Staff / Manager", "Level 3+ Administrators")

    System_Boundary(cpo_boundary, "Chief Productivity Officer (CPO) System") {
        Container(gateway_router, "Bot Runtime & Router", "Python / discord.py", "Routes interactions & handles Discord Gateway")
        
        Container(cog_layer, "Cogs Layer", "discord.ext.commands.Cog", "Checkin, Study Groups, Pomodoro, Manager")
        
        Container(voting_engine, "Consensus Engine (NEW)", "Python", "Manages End Group votes and Votekick tallies")
        
        ContainerDb(sqlite_db, "Persistence Engine", "SQLite 3", "Stores study groups, members, standups, managers, and active votes")
    }

    System_Ext(discord_api, "Discord Gateway & REST API", "WebSockets / HTTPS API")

    Rel(user, discord_api, "Executes commands, votes on kicks/ends")
    Rel(admin, discord_api, "Bypasses votes, ends groups instantly")
    Rel(discord_api, gateway_router, "Dispatches Gateway payloads")
    Rel(gateway_router, cog_layer, "Dispatches command callbacks")
    Rel(cog_layer, voting_engine, "Initiates and tallies votes")
    Rel(voting_engine, sqlite_db, "Persists vote state")
    Rel(cog_layer, discord_api, "Sends interactive DM invites and View buttons")
```

---

## 2. Target Workflows & Sequences

### 2.1 Democratic End Group Voting (Expectation #2)
Instead of owners instantly ending groups, any member or owner initiates a democratic vote. Only Level 3+ staff bypass this.

```mermaid
sequenceDiagram
    autonumber
    actor Member as Group Member/Owner
    actor Staff as Level 3+ Staff
    participant Bot as CPO Bot
    participant UI as Group Channel / UI

    alt Staff ends group
        Staff->>Bot: /end_group or clicks End button
        Bot->>Bot: Verify Level >= 3
        Bot->>UI: Closes group instantly
    else Member/Owner ends group
        Member->>Bot: Clicks End button
        Bot->>Bot: Verify Level < 3
        Bot->>UI: Broadcast "End Group Vote Started (0/N)"
        loop Until majority reached or timeout
            Member->>UI: Clicks "Vote Yes"
            UI->>Bot: Tally Vote
            Bot->>UI: Update Tally "End Group Vote (X/N)"
        end
        alt Majority Reached
            Bot->>UI: Vote passed, closing group
            Bot->>Bot: Execute Teardown
        else Timeout
            Bot->>UI: Vote failed, group remains active
        end
    end
```

### 2.2 Votekick with Staff Immunity (Expectation #3)
Members can vote to kick any participant (including the group owner). However, Level 3+ Staff are strictly immune to votekicks.

```mermaid
stateDiagram-v2
    [*] --> VotekickInitiated: /votekick @user
    
    state VotekickInitiated {
        [*] --> CheckImmunity
        CheckImmunity --> Immune: Target is Level 3+ (Staff)
        ImmunityFailed: Reply "Staff cannot be kicked."
        Immune --> ImmunityFailed
        
        CheckImmunity --> Eligible: Target is Level 0-2 (Including Owner)
        Eligible --> ActiveVote: Broadcast Vote View
        
        state ActiveVote {
            [*] --> Tallying
            Tallying --> Tallying: Members click "Kick"
        }
    }
    
    ImmunityFailed --> [*]
    ActiveVote --> KickExecuted: Majority Reached
    ActiveVote --> VoteFailed: Timeout / Not enough votes
    KickExecuted --> [*]: User removed & Discord permissions revoked
    VoteFailed --> [*]
```

### 2.3 Strict Invite-Only Group Admission (Expectation #4)
The current `/join_group` command is removed/disabled. Users can only join via explicit invitations (mentions during creation or `/invite` command).

```mermaid
sequenceDiagram
    autonumber
    actor Creator as Group Creator
    actor Invitee as Target Member
    participant Bot as CPO Bot
    participant DB as SQLite DB

    Creator->>Bot: /create_group mentions: @TargetMember
    Bot->>DB: Save Group & Creator
    Bot->>Invitee: DM: StudyGroupInvitationView (Join/Decline)
    
    alt Invitee Clicks Join
        Invitee->>Bot: Interaction (Join)
        Bot->>DB: Add to active roster
        Bot->>Bot: Grant Channel Permissions
        Bot->>Creator: Ephemeral notify "Target joined"
    else Invitee Clicks Decline or Timeout
        Invitee->>Bot: Interaction (Decline)
        Bot->>Creator: Ephemeral notify "Target declined"
    end
    
    note over Creator, DB: Public /join_group is entirely disabled.
```

---

## 3. Asynchronous Non-Blocking Processing
Commands maintain Discord API compliance (the 3-second rule) using immediate ephemeral acknowledgements (`acknowledge_interaction`), avoiding the need for heavy cross-process IPC architectures.

```mermaid
sequenceDiagram
    actor User
    participant Discord
    participant CPO as Bot Process
    
    User->>Discord: Slash Command
    Discord->>CPO: Interaction Payload
    CPO->>Discord: Instant deferral ("Processing...")
    note right of CPO: 3-second limit bypassed natively. Bot has 15 minutes.
    CPO->>CPO: Async processing (DB, Permissions, API)
    CPO->>Discord: followup.send(Final Result) + delete deferred message
```
