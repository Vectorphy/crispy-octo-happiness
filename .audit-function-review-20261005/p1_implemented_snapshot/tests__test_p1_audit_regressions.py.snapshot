import asyncio
import sqlite3
import time
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from cogs._access_policy import AccessCommandTree, AccessView
from cogs._invitations import InvitationService, eligible_recipient
from cogs.checkin import CheckinCog, CheckinGuildSettings, CheckinSession
from cogs.manager import Manager
from cogs.pomodoro import Pomodoro, PomodoroInvitationView, PomodoroSession
from cogs.study_groups import EndGroupVoteView, GroupInvitationView, StudyGroup, StudyGroupCog, VotekickView
from database import DBHandler
from tests.test_group_controls import environment, interaction


@pytest.fixture
async def persisted_group(tmp_path):
    db = DBHandler(str(tmp_path / "p1.sqlite"))
    await db.connect()
    cog, guild, people, *_ = environment()
    cog.bot.db = db
    cog.bot.get_guild.return_value = guild
    cog.bot.guilds = [guild]
    manager = Manager(cog.bot)
    group = StudyGroup(db, cog, 1, "audit", 5, 20, 10, [5, 6, 7, 8])
    group.guild = guild
    group.active = True
    group.text_id = 30
    group.group_role_id = 90
    group.group_info_embed = AsyncMock()
    cog._start_group_monitor = MagicMock()
    cog.active_study_groups[group.group_id] = group
    cog.bot.get_cog.side_effect = {"StudyGroupCog": cog, "Manager": manager}.get
    guild.fetch_member = AsyncMock(side_effect=people.get)
    await db.save_study_group(
        {
            "group_id": group.group_id,
            "guild_id": 1,
            "name": "audit",
            "creator_id": 5,
            "owner_id": 5,
            "member_ids": group.member_ids,
            "max_members": 10,
            "active": 1,
            "text_id": 30,
            "group_role_id": 90,
        }
    )
    yield group, people, manager
    if isinstance(getattr(cog.bot, "_invitation_service", None), InvitationService):
        await cog.bot._invitation_service.close_kind("group")
    await db.close()


@pytest.mark.asyncio
async def test_departed_votes_never_count_against_current_roster(persisted_group):
    group, people, _ = persisted_group
    group.end_group = AsyncMock()
    vote = EndGroupVoteView(group, 5)
    group.member_ids.remove(5)
    await vote.vote_yes_button.callback(interaction(group.bot, group.guild, people[6]))
    group.end_group.assert_not_awaited()
    assert vote.yes_votes == {6}
    group.member_ids = [5, 6, 7, 8]
    kick = VotekickView(group, 8, 6)
    group.member_ids.remove(6)
    await kick.vote_kick_button.callback(interaction(group.bot, group.guild, people[7]))
    assert kick.kick_votes == {7}
    assert 8 in group.member_ids


@pytest.mark.asyncio
async def test_staff_promotion_after_vote_start_prevents_removal(persisted_group):
    group, people, _ = persisted_group
    vote = VotekickView(group, 8, 5)
    await group.db.add_manager(8, 1, 4)
    await vote.vote_kick_button.callback(interaction(group.bot, group.guild, people[6]))
    assert 8 in group.member_ids
    assert 8 in await group.db.fetch_members_of_group(group.group_id)
    people[8].remove_roles.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["owner_update", "member_delete"])
async def test_sqlite_removal_failure_preserves_owner_roster_and_role(persisted_group, failure):
    group, people, _ = persisted_group
    statement = (
        "CREATE TRIGGER reject_owner BEFORE UPDATE OF owner_id ON study_groups BEGIN SELECT RAISE(ABORT, 'blocked'); END"
        if failure == "owner_update"
        else "CREATE TRIGGER reject_remove BEFORE DELETE ON study_groups_members BEGIN SELECT RAISE(ABORT, 'blocked'); END"
    )
    async with group.db.lock:
        await group.db._run_in_thread(group.db._execute_commit_sync, statement)
    request = interaction(group.bot, group.guild, people[6])
    assert not await group.remove_member(request, 5, votekick=True)
    assert group.owner_id == 5 and 5 in group.member_ids
    assert await group.db.fetch_owner_of_group(group.group_id) == 5
    assert 5 in await group.db.fetch_members_of_group(group.group_id)
    people[5].remove_roles.assert_awaited_once()
    people[5].add_roles.assert_awaited_once()
    assert "Votekick passed" not in str(request.followup.send.call_args_list)


@pytest.mark.asyncio
async def test_owner_removal_commits_runtime_and_roster_together(persisted_group):
    group, people, _ = persisted_group
    await group.db.save_pomodoro_runtime(
        "timer", group.group_id, 1, {"participants": [5, 6], "present_members": [5], "absent_counts": {"5": 1}}
    )
    assert await group.remove_member(interaction(group.bot, group.guild, people[6]), 5, votekick=True)
    assert group.owner_id == 6
    assert await group.db.fetch_owner_of_group(group.group_id) == 6
    runtime = (await group.db.get_active_pomodoro_runtime())[0]["state"]
    assert runtime["participants"] == [6] and runtime["present_members"] == []
    assert runtime["absent_counts"] == {}


@pytest.mark.asyncio
async def test_foreign_guild_fallback_and_uninvited_named_join_are_denied(persisted_group):
    group, people, _ = persisted_group
    request = interaction(group.bot, group.guild, people[6])
    foreign = MagicMock(spec=discord.Guild, id=2)
    request.guild = foreign
    request.guild_id = 2
    group.start_votekick = AsyncMock()
    with patch.object(group.db, "get_user_group", AsyncMock(return_value={"group_id": group.group_id, "guild_id": 1})):
        await StudyGroupCog.votekick.callback(group.cog, request, people[8])
    group.start_votekick.assert_not_awaited()
    await group.db.remove_member_from_study_group_db(group.group_id, 8)
    group.member_ids.remove(8)
    await StudyGroupCog.join_group.callback(group.cog, interaction(group.bot, group.guild, people[8]), "audit")
    assert 8 not in await group.db.fetch_members_of_group(group.group_id)
    people[8].add_roles.assert_not_awaited()


@pytest.mark.asyncio
async def test_role_settings_failure_denies_invitation_recipient(persisted_group):
    group, people, _ = persisted_group
    with patch.object(group.db, "get_default_role", AsyncMock(side_effect=sqlite3.OperationalError("unavailable"))):
        assert await eligible_recipient(group.bot, 1, 8, fallback_guild=group.guild, member=people[8]) is None


@pytest.mark.asyncio
async def test_two_services_cannot_reclaim_an_inflight_invitation(persisted_group):
    group, people, _ = persisted_group
    view = GroupInvitationView(group, 8)
    await group.db.create_session_invitation(view.invitation_id, 1, "group", group.group_id, 8, 5, time.time())
    first, second = InvitationService(group.bot), InvitationService(group.bot)
    started, release = asyncio.Event(), asyncio.Event()

    async def join(request):
        started.set()
        await release.wait()

    callback = AsyncMock(side_effect=join)
    request = interaction(group.bot, group.guild, people[8])
    task = asyncio.create_task(first.act(view, request, "join", callback))
    await started.wait()
    await second.act(view, request, "join", callback)
    assert callback.await_count == 1
    release.set()
    await task
    row = await group.db.get_session_invitation(1, view.invitation_id)
    assert row["status"] == "accepted"


@pytest.mark.asyncio
async def test_false_cas_and_missing_row_never_invoke_admission(persisted_group):
    group, people, _ = persisted_group
    view = GroupInvitationView(group, 8)
    callback = AsyncMock()
    service = InvitationService(group.bot)
    request = interaction(group.bot, group.guild, people[8])
    await service.act(view, request, "join", callback)
    callback.assert_not_awaited()
    await group.db.create_session_invitation(view.invitation_id, 1, "group", group.group_id, 8, 5, time.time())
    with patch.object(group.db, "transition_session_invitation", AsyncMock(return_value=False)):
        await service.act(view, request, "join", callback)
    callback.assert_not_awaited()


@pytest.mark.asyncio
async def test_restart_restores_custom_ids_and_original_deadlines(persisted_group):
    group, _, _ = persisted_group
    created_at = time.time() - 400
    row = await group.db.create_session_invitation("restore-me", 1, "group", group.group_id, 8, 5, created_at)
    await group.db.bind_session_invitation_message(1, "restore-me", 200, 300)
    await group.db.close()
    await group.db.connect()
    group.cog.active_study_groups.clear()
    service = InvitationService(group.bot)
    await service.restore()
    restored = service.views["restore-me"]
    assert restored.invitation_created_at == created_at
    assert restored.children[0].custom_id == "cpo:invitation:restore-me:join"
    group.bot.add_view.assert_called_with(restored, message_id=300)
    saved = await group.db.get_session_invitation(1, "restore-me")
    assert saved["warn_at"] == row["warn_at"] and saved["expires_at"] == row["expires_at"]
    assert saved["warned"] == 1
    await service.close_kind("group")


@pytest.mark.asyncio
async def test_partial_provisioning_failure_deletes_uncached_resources(persisted_group):
    group, people, _ = persisted_group
    category = group.guild.get_channel(20)
    text = category.create_text_channel.return_value
    group.guild.get_channel.side_effect = {20: category}.get
    category.create_voice_channel.side_effect = discord.Forbidden(MagicMock(status=403), "blocked")
    assert "Failed" in await group.setup_group_resources(interaction(group.bot, group.guild, people[5]))
    text.delete.assert_awaited_once()
    group.guild.create_role.return_value.delete.assert_awaited_once()
    assert not group.active


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["set_group_category", "purge_groups"])
async def test_missing_manager_fails_closed(persisted_group, command):
    group, people, _ = persisted_group
    group.bot.get_cog.return_value = None
    group.bot.get_cog.side_effect = None
    args = [group.guild.get_channel(20)] if command == "set_group_category" else []
    with (
        patch.object(group.db, "update_group_category", AsyncMock()) as save,
        patch.object(group.db, "get_all_study_groups", AsyncMock()) as fetch,
    ):
        await getattr(group.cog, command).callback(group.cog, interaction(group.bot, group.guild, people[5]), *args)
    save.assert_not_awaited()
    fetch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["add_guild_manager", "remove_guild_manager"])
async def test_level_three_cannot_demote_level_four(persisted_group, command):
    group, people, manager = persisted_group
    await group.db.add_manager(5, 1, 3)
    await group.db.add_manager(8, 1, 4)
    await getattr(manager, command).callback(manager, interaction(group.bot, group.guild, people[5]), people[8])
    assert (await group.db.get_manager(8, 1))["permission_level"] == 4


@pytest.mark.asyncio
async def test_general_command_and_control_dispatch_record_identity_only(persisted_group):
    group, people, _ = persisted_group
    request = interaction(group.bot, group.guild, people[6])
    request.data = {"name": "task_add", "options": [{"value": "private task text"}]}
    request.command_failed = False
    client = discord.Client(intents=discord.Intents.none())
    tree = AccessCommandTree(client)
    tree.client.db = group.db
    tree.client.get_cog = group.bot.get_cog
    tree.client.get_guild = group.bot.get_guild
    with patch("discord.app_commands.CommandTree._call", AsyncMock()):
        await tree._call(request)
    view = AccessView()
    view.guild_id = 1
    with (
        patch("cogs._access_policy.require_guild_access", AsyncMock(return_value=True)),
        patch("discord.ui.View._scheduled_task", AsyncMock()),
    ):
        await view._scheduled_task(MagicMock(), request)
    async with group.db.lock:
        rows = await group.db._run_in_thread(group.db._fetchall_sync, "SELECT * FROM command_audit_events")
    actions = {row["action"] for row in rows}
    assert "command.task_add" in actions and "control.AccessView" in actions
    assert "private task text" not in str([dict(row) for row in rows])
    assert all(row["guild_id"] == 1 and row["actor_id"] == 6 for row in rows)


@pytest.mark.asyncio
async def test_actual_runtime_storage_failure_rolls_back_invited_participant(persisted_group):
    group, people, manager = persisted_group
    cog = Pomodoro(group.bot)
    group.bot.get_cog.side_effect = {"StudyGroupCog": group.cog, "Manager": manager, "Pomodoro": cog}.get
    session = PomodoroSession(group.group_id, 25, 5, 15, guild_id=1, text_id=30, require_vc=False, owner_id=5)
    cog.sessions[group.group_id] = session
    await cog._persist_session(session, required=True)
    async with group.db.lock:
        await group.db._run_in_thread(
            group.db._execute_commit_sync,
            "CREATE TRIGGER reject_runtime BEFORE INSERT ON pomodoro_runtime BEGIN SELECT RAISE(ABORT, 'blocked'); END",
        )
    view = PomodoroInvitationView(cog, session, 8)
    await group.db.create_session_invitation(view.invitation_id, 1, "pomodoro", session.tracking_id, 8, 5, time.time())
    await view.join.callback(interaction(group.bot, group.guild, people[8]))
    assert session.participants == {5}
    assert (await group.db.get_active_pomodoro_runtime())[0]["state"]["participants"] == [5]
    assert (await group.db.get_session_invitation(1, view.invitation_id))["status"] == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["success", "revoked", "ended", "failure", "target_exited"])
async def test_checkin_owner_selection_revalidates_and_commits_before_memory(persisted_group, scenario):
    group, people, manager = persisted_group
    cog = CheckinCog(group.bot)
    group.bot.get_cog.side_effect = {"CheckinCog": cog, "Manager": manager}.get
    request = interaction(group.bot, group.guild, people[5])
    session = CheckinSession(group.db, cog, request, "owner", [5, 6, 7], 120, CheckinGuildSettings(request))
    cog.active_sessions[session.session_id] = session
    session.update_embed = AsyncMock()
    await session.setup_checkin_resources()
    with patch("cogs.checkin.send_response", AsyncMock(return_value=AsyncMock())) as respond:
        await session.change_owner_callback(request)
        view = next(call.kwargs["view"] for call in respond.call_args_list if "view" in call.kwargs)
        select = view.children[0]
        select._values = ["6"]
        if scenario == "revoked":
            session.owner_id = 7
            await group.db.update_checkin_session({"session_id": session.session_id, "owner_id": 7})
        elif scenario == "ended":
            session.end_session_event.set()
            await group.db.update_checkin_session({"session_id": session.session_id, "active": 0})
        elif scenario == "target_exited":
            await group.db.add_or_update_checkin_member(session.session_id, 6, "exited", 0)
        elif scenario == "failure":
            async with group.db.lock:
                await group.db._run_in_thread(
                    group.db._execute_commit_sync,
                    "CREATE TRIGGER reject_checkin_owner BEFORE UPDATE OF owner_id ON checkin_sessions BEGIN SELECT RAISE(ABORT, 'blocked'); END",
                )
        if scenario == "failure":
            with pytest.raises(sqlite3.IntegrityError):
                await select.callback(request)
        else:
            await select.callback(request)
    expected = 6 if scenario == "success" else 7 if scenario == "revoked" else 5
    assert session.owner_id == expected
    await group.db.close()
    await group.db.connect()
    assert (await group.db.fetch_checkin_session(session.session_id))["owner_id"] == expected
