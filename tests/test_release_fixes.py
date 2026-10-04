import asyncio
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from cogs.study_groups import GroupInvitationView, StudyGroup, StudyGroupCog
from cogs.tasklist import TaskActionView, TaskList
from cogs.voice_channels import VoiceChannels
from database import DBHandler
from test_file import run_all_feature_tests


def interaction(user_id=123):
    result = AsyncMock(spec=discord.Interaction)
    result.channel_id = None
    result.guild_id = 99
    result.guild = MagicMock(spec=discord.Guild)
    result.guild.id = 99
    result.response = AsyncMock(spec=discord.InteractionResponse)
    result.followup = AsyncMock(spec=discord.Webhook)
    result.user = AsyncMock(spec=discord.Member)
    result.user.id = user_id
    result.response.is_done = MagicMock(return_value=False)
    return result


def group_fixture():
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_user_created_group_count = AsyncMock(return_value=0)
    bot.db.get_user_joined_group_count = AsyncMock(return_value=0)
    cog = StudyGroupCog(bot)
    group = StudyGroup(bot.db, cog, 99, "Physics", 123, 20, 5, [123])
    group.active = True
    group.guild = MagicMock()
    group.guild.id = 99
    group.vc_id = 40
    group.text_id = 30
    group.group_role_id = 50
    group.group_info_embed = AsyncMock()
    role = MagicMock(spec=discord.Role)
    channel = AsyncMock(spec=discord.VoiceChannel)
    channel.overwrites_for = MagicMock(return_value=discord.PermissionOverwrite(connect=True))
    group.guild.get_channel.return_value = channel
    group.guild.get_role.return_value = role
    return group, channel, role


@pytest.mark.asyncio
@pytest.mark.parametrize("schema", ["missing_id", "partial", "legacy_names"])
async def test_legacy_migration_preserves_groups_and_rosters(schema):
    db = DBHandler(":memory:")
    db.conn = sqlite3.connect(":memory:")
    db.conn.row_factory = sqlite3.Row
    async with db.lock:
        db.conn.execute(
            "CREATE TABLE study_groups (id INTEGER PRIMARY KEY, guild_id INTEGER, name TEXT, creator_id INTEGER, owner_id INTEGER, category_id INTEGER, max_members INTEGER, group_role_id INTEGER, vc_id INTEGER, text_id INTEGER, speak_enabled BOOLEAN, video_mode TEXT, video_timer INTEGER, start_time REAL, end_time REAL, duration INTEGER, active BOOLEAN)"
        )
        db.conn.execute(
            "INSERT INTO study_groups VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (7, 99, "Legacy", 123, 123, 20, 5, 50, 40, 30, 1, "off", 10, 100, 200, 100, 1),
        )
        db.conn.execute(
            "CREATE TABLE study_groups_members (group_id INTEGER, user_id INTEGER, PRIMARY KEY(group_id, user_id))"
        )
        db.conn.execute("INSERT INTO study_groups_members VALUES (?, ?)", (7, 123))
        if schema == "partial":
            db.conn.execute("ALTER TABLE study_groups ADD COLUMN group_id TEXT")
        elif schema == "legacy_names":
            db.conn.execute("ALTER TABLE study_groups RENAME TO study_groups_db")
            db.conn.execute("ALTER TABLE study_groups_members RENAME TO study_group_members_db")
        db.conn.commit()
    try:
        await db.create_tables()
        await db.create_tables()
        group = await db.get_study_group_by_channel(30)
        assert group is not None
        assert group["id"] == 7 and group["group_id"] == "7"
        assert group["name"] == "Legacy" and group["start_time"] == 100
        assert await db.fetch_members_of_group("7") == [123]
        await db.delete_study_group("7")
        assert await db.get_study_group_by_channel(30) is None
        async with db.lock:
            assert db.conn.execute("SELECT active FROM study_groups WHERE id = ?", (7,)).fetchone()[0] == 0
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_mod_log_setting_survives_migration_and_can_be_disabled():
    db = DBHandler(":memory:")
    await db.connect()
    try:
        await db.update_group_category(99, 20)
        await db.set_mod_log_channel(99, 50)
        await db.create_tables()
        assert await db.get_mod_log_channel(99) == 50
        assert await db.get_group_category(99) == 20
        assert await db.get_mod_log_channel(100) is None
        await db.set_mod_log_channel(99, None)
        assert await db.get_mod_log_channel(99) is None
    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", ["speak", "stream"])
async def test_voice_toggle_preserves_connect_and_persists(permission):
    group, channel, role = group_fixture()
    group.can_control = AsyncMock(return_value=True)
    request = interaction()
    await group._toggle_voice_permission(request, permission)
    request.response.defer.assert_awaited_once()
    overwrite = channel.set_permissions.call_args.kwargs["overwrite"]
    assert overwrite.connect is True
    assert getattr(overwrite, permission) == (permission == "stream")
    group.db.update_study_group_by_id.assert_awaited_once()
    assert channel.set_permissions.await_count == (2 if permission == "speak" else 1)
    if permission == "stream":
        assert group.video_mode == "force"
    else:
        targets = {call.args[0] for call in channel.set_permissions.await_args_list}
        assert targets == {role, group.guild.default_role}
        assert all(call.kwargs["overwrite"].speak is False for call in channel.set_permissions.await_args_list)


@pytest.mark.asyncio
async def test_force_video_relocates_member_after_timer(monkeypatch):
    group, channel, _ = group_fixture()
    group.active = True
    group.video_mode = "force"
    group.video_timer = 60
    channel.id = group.vc_id
    member = MagicMock(spec=discord.Member)
    member.id = 456
    member.voice = MagicMock(channel=channel, self_video=False)
    relocation = AsyncMock()
    monkeypatch.setitem(group._enforce_video.__globals__, "relocate_to_default_vc", relocation)

    with patch("cogs.study_groups.asyncio.sleep", new=AsyncMock()) as sleep:
        await group._enforce_video(member)

    assert sleep.await_args_list[0].args == (30,)
    assert sleep.await_args_list[1].args == (30,)
    member.send.assert_awaited_once_with(
        f"Please turn on your camera or screen sharing in **{group.name}** within 30 seconds, "
        "or you will be moved to the server's default voice channel."
    )
    relocation.assert_awaited_once_with(member, group.db, group.vc_id, group.group_id)
    assert member.id not in group.video_enforcement_tasks


@pytest.mark.asyncio
async def test_voice_toggle_rejects_non_owner_and_discord_failure():
    group, channel, role = group_fixture()
    group.can_control = AsyncMock(return_value=False)
    await group.speak_toggle_callback(interaction(456))
    channel.set_permissions.assert_not_awaited()
    group.can_control.return_value = True
    channel.set_permissions.side_effect = discord.Forbidden(MagicMock(status=403), "denied")
    await group.speak_toggle_callback(interaction())
    assert group.speak_enabled is True
    group.db.update_study_group_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_invitation_adds_only_after_recipient_accepts():
    group, channel, role = group_fixture()
    group.guild.get_member.return_value = AsyncMock(spec=discord.Member)
    request = interaction(456)
    invited = AsyncMock(spec=discord.Member)
    invited.id = 456
    await group.send_invite(interaction(), invited)
    assert 456 not in group.member_ids
    view = invited.send.call_args.kwargs["view"]
    assert not await view.interaction_check(interaction(789))
    assert 456 not in group.member_ids
    await view.join_button.callback(request)
    assert 456 in group.member_ids
    group.db.add_member_to_study_group_db.assert_awaited_once_with(group.group_id, 456)
    assert view.is_finished()


@pytest.mark.asyncio
@pytest.mark.parametrize("closed", ["full", "ended", "expired"])
async def test_invitation_rechecks_capacity_lifecycle_and_expiry(closed):
    group, channel, role = group_fixture()
    view = GroupInvitationView(group, 456)
    if closed == "full":
        group.max_members = 1
    elif closed == "ended":
        group.active = False
    else:
        view.stop()
    await view.join_button.callback(interaction(456))
    assert 456 not in group.member_ids
    group.db.add_member_to_study_group_db.assert_not_awaited()
    view.stop()


@pytest.mark.asyncio
async def test_undeliverable_invitation_does_not_add_member():
    group, channel, role = group_fixture()
    invited = AsyncMock(spec=discord.Member)
    invited.id = 456
    invited.send.side_effect = discord.Forbidden(MagicMock(status=403), "DM disabled")
    await group.send_invite(interaction(), invited)
    assert 456 not in group.member_ids
    group.db.add_member_to_study_group_db.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["complete", "delete"])
async def test_task_menus_are_scoped_to_group_and_owner(action):
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_study_group_by_channel.return_value = {"id": 1, "group_id": "group-a"}
    bot.db.get_user_tasks.return_value = [
        {"id": 5, "task_id_str": "AB12", "description": "Read", "completed": 0, "group_id": "group-a"}
    ]
    request = interaction()
    request.channel_id = 30
    cog = TaskList(bot)
    command = cog.complete_task if action == "complete" else cog.delete_task
    await command.callback(cog, request)
    bot.db.get_user_tasks.assert_awaited_once_with(123, group_id="group-a")
    view = request.followup.send.call_args.kwargs["view"]
    assert not await view.interaction_check(interaction(456))
    assert await view.interaction_check(interaction())
    select = view.children[0]
    assert select.options[0].value == "5"
    assert "AB12" in select.options[0].label
    select._values = ["5"]
    await select.callback(interaction())
    bot.db.apply_task_action.assert_awaited_once_with(123, 5, "group-a", action)
    view.stop()


@pytest.mark.asyncio
async def test_task_delete_empty_menu_and_dm_public_acknowledgement():
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_user_tasks.return_value = []
    request = interaction()
    request.guild = None
    cog = TaskList(bot)
    await cog.delete_task.callback(cog, request)
    request.response.send_message.assert_awaited_once_with("Processing your request…", ephemeral=True)
    request.followup.send.assert_awaited_once_with("You have no tasks to delete.", ephemeral=True)


@pytest.mark.asyncio
async def test_task_list_defaults_to_global_scope_and_true_lists_all_groups():
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_study_group_by_channel.return_value = None
    bot.db.get_user_tasks.return_value = [
        {"id": 1, "description": "Global", "completed": 0, "group_id": None},
    ]
    bot.db.get_commands_channel.return_value = 600
    request = interaction()
    request.channel_id = 600
    request.channel.category_id = 20
    cog = TaskList(bot)

    # In the commands channel, all_groups=False limits tasks to guild and is public
    await cog.list_tasks.callback(cog, request, all_groups="false")
    bot.db.get_user_tasks.assert_awaited_once_with(123, guild_id=99)
    request.response.send_message.assert_awaited_once_with("Processing your request…", ephemeral=True)

    # In other categories outside the group category, all_groups=False is ephemeral
    bot.db.get_user_tasks.reset_mock()
    request_other = interaction()
    request_other.channel.category_id = 999
    await cog.list_tasks.callback(cog, request_other, all_groups="false")
    request_other.response.send_message.assert_awaited_once_with("Processing your request…", ephemeral=True)

    # In DM (no guild), all_groups=False defaults to global tasks and is ephemeral
    bot.db.get_user_tasks.reset_mock()
    request_dm = interaction()
    request_dm.guild = None
    request_dm.channel_id = None
    await cog.list_tasks.callback(cog, request_dm, all_groups="false")
    bot.db.get_user_tasks.assert_awaited_once_with(123, global_only=True)
    request_dm.response.send_message.assert_awaited_once_with("Processing your request…", ephemeral=True)

    # all_groups=True fetches all tasks across all groups/servers and is ephemeral
    bot.db.get_user_tasks.reset_mock()
    request.response.send_message.reset_mock()
    request.followup.send.reset_mock()
    await cog.list_tasks.callback(cog, request, all_groups=True)
    bot.db.get_user_tasks.assert_awaited_once_with(123)
    request.response.send_message.assert_awaited_once_with("Processing your request…", ephemeral=True)
    request.followup.send.assert_awaited_once()
    assert request.followup.send.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_voice_command_errors_are_private_in_commands_channel():
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.get_commands_channel.return_value = 600
    bot.db.get_study_group.return_value = None
    cog = VoiceChannels(bot)

    # Errors in other channels stay private
    req_outside = interaction()
    req_outside.guild.id = 99
    req_outside.channel = MagicMock()
    req_outside.channel.category_id = 10
    await cog.create_vc.callback(cog, req_outside)
    req_outside.response.send_message.assert_awaited_once_with("Processing your request…", ephemeral=True)
    req_outside.followup.send.assert_awaited_once_with("No study group exists in this server.", ephemeral=True)

    # Errors in the commands channel stay private
    req_inside = interaction()
    req_inside.guild.id = 99
    req_inside.channel = MagicMock()
    req_inside.channel.category_id = 50
    req_inside.channel_id = 600
    await cog.create_vc.callback(cog, req_inside)
    req_inside.response.send_message.assert_awaited_once_with("Processing your request…", ephemeral=True)
    req_inside.followup.send.assert_awaited_once_with("No study group exists in this server.", ephemeral=True)

    # Delete commands outside category -> ephemeral=True
    req_delete = interaction()
    req_delete.guild.id = 99
    req_delete.channel = MagicMock()
    req_delete.channel.category_id = 10
    dummy_vc = MagicMock(spec=discord.VoiceChannel)
    await cog.delete_vc.callback(cog, req_delete, dummy_vc)
    req_delete.response.send_message.assert_awaited_once_with("Processing your request…", ephemeral=True)
    req_delete.followup.send.assert_awaited_once_with("No study group exists for this server.", ephemeral=True)


@pytest.mark.asyncio
async def test_task_purge_removes_only_owners_bot_task_messages():
    bot = MagicMock()
    bot.user.id = 999
    bot.db = AsyncMock()
    bot.db.purge_all_user_tasks.return_value = 2
    cog = TaskList(bot)
    request = interaction()
    request.channel = AsyncMock(spec=discord.TextChannel)
    await cog.purge_tasks.callback(cog, request, all_tasks=True)
    bot.db.purge_all_user_tasks.assert_awaited_once_with(123)
    check = request.channel.purge.call_args.kwargs["check"]
    message = MagicMock(content="Task added successfully. Task ID: AB12", embeds=[])
    message.author.id = 999
    message.interaction_metadata.user.id = 123
    assert check(message)
    message.interaction_metadata.user.id = 456
    assert not check(message)
    message.interaction_metadata.user.id = 123
    message.author.id = 123
    assert not check(message)
    message.author.id = 999
    message.content = "Unrelated bot notification"
    assert not check(message)


@pytest.mark.asyncio
async def test_deleted_channel_cleanup_result_falls_back_to_dm():
    group, channel, role = group_fixture()
    request = interaction()
    request.followup.send.side_effect = discord.NotFound(
        MagicMock(status=404), {"code": 10003, "message": "Unknown Channel"}
    )
    await group.cog._send_cleanup_result(request, "Groups purged")
    request.user.send.assert_awaited_once_with("Groups purged")
    request.followup.send.side_effect = discord.NotFound(
        MagicMock(status=404), {"code": 10015, "message": "Unknown Webhook"}
    )
    with pytest.raises(discord.NotFound):
        await group.cog._send_cleanup_result(request, "Groups purged")


@pytest.mark.asyncio
async def test_group_actions_log_without_pinging():
    group, channel, role = group_fixture()
    log_channel = AsyncMock(spec=discord.TextChannel)
    group.guild.get_channel.return_value = log_channel
    group.db.get_mod_log_channel.return_value = 60
    await group.cog.log_mod_action(group.guild, "Study group created", group.group_id, group.name, 123)
    kwargs = log_channel.send.call_args.kwargs
    assert kwargs["embed"].title == "Study group created"
    assert not kwargs["allowed_mentions"].users
    group.db.get_mod_log_channel.return_value = None
    await group.cog.log_mod_action(group.guild, "Study group ended", group.group_id, group.name, 123)
    assert log_channel.send.await_count == 1


@pytest.mark.asyncio
async def test_standalone_command_matrix_asserts_all_54_flows():
    assert await run_all_feature_tests() == (54, 54)


@pytest.mark.asyncio
async def test_earliest_schema_retains_legacy_roles_rosters_and_allows_new_groups():
    db = DBHandler(":memory:")
    db.conn = sqlite3.connect(":memory:")
    db.conn.row_factory = sqlite3.Row
    async with db.lock:
        db.conn.execute(
            "CREATE TABLE study_groups (id INTEGER PRIMARY KEY, name TEXT NOT NULL, creator_id INTEGER NOT NULL, max_size INTEGER NOT NULL, end_time REAL NOT NULL, guild_id INTEGER NOT NULL, admin_role_id INTEGER, session_role_id INTEGER, voice_channel_id INTEGER)"
        )
        db.conn.execute(
            "INSERT INTO study_groups VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (7, "Legacy", 123, 8, 200, 99, 55, 50, 40)
        )
        db.conn.execute(
            "CREATE TABLE group_members (group_id INTEGER, user_id INTEGER, PRIMARY KEY(group_id, user_id))"
        )
        db.conn.execute("INSERT INTO group_members VALUES (?, ?)", (7, 456))
        db.conn.commit()
    try:
        await db.create_tables()
        await db.create_tables()
        old = await db.fetch_study_group_by_id("7")
        assert old is not None
        assert old["id"] == 7 and old["owner_id"] == 123
        assert old["max_members"] == 8 and old["group_role_id"] == 50 and old["vc_id"] == 40
        assert old["admin_role_id"] == 55 and old["end_time"] == 200
        assert await db.fetch_members_of_group("7") == [456]
        await db.save_study_group(
            {"group_id": "new-group", "guild_id": 99, "name": "New", "creator_id": 123, "max_members": 4}
        )
        created = await db.fetch_study_group_by_id("new-group")
        assert created is not None and created["max_size"] == 4
        await db.delete_study_group("7")
        await db.create_tables()
        assert await db.fetch_members_of_group("7") == []
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_group_resave_preserves_primary_key_and_ended_groups_are_excluded():
    db = DBHandler(":memory:")
    await db.connect()
    data = {
        "group_id": "stable",
        "guild_id": 99,
        "name": "Physics",
        "creator_id": 123,
        "member_ids": [456],
        "text_id": 30,
    }
    try:
        await db.save_study_group(data)
        old = await db.fetch_study_group_by_id("stable")
        assert old is not None
        await db.save_study_group({**data, "max_members": 8})
        updated = await db.fetch_study_group_by_id("stable")
        assert updated is not None and updated["id"] == old["id"] and updated["max_members"] == 8
        assert len(await db.get_study_groups_of_user(123, 99)) == 1
        await db.delete_study_group("stable")
        assert await db.get_all_study_groups(99) == []
        assert await db.get_user_group(123, 30) is None
        assert await db.get_study_groups_of_user(123, 99) == []
        assert await db.fetch_study_group_by_name("Physics", "99") is None
        assert await db.get_study_group(99) is None
        assert await db.get_study_group_by_channel(30) is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_simultaneous_invitation_and_command_join_respect_capacity():
    group, channel, role = group_fixture()
    group.max_members = 2
    member = AsyncMock(spec=discord.Member)
    group.guild.get_member.return_value = member

    async def add_role(*args):
        await asyncio.sleep(0)

    member.add_roles.side_effect = add_role
    view = GroupInvitationView(group, 456)
    await asyncio.gather(view.join_button.callback(interaction(456)), group.add_member(789))
    assert len(group.member_ids) == 2
    assert len(set(group.member_ids)) == 2
    group.db.add_member_to_study_group_db.assert_awaited_once()
    view.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing_role", "discord", "database"])
async def test_failed_invitation_admission_leaves_roster_unchanged(failure):
    group, channel, role = group_fixture()
    member = AsyncMock(spec=discord.Member)
    group.guild.get_member.return_value = member
    if failure == "missing_role":
        group.guild.get_role.return_value = None
    elif failure == "discord":
        member.add_roles.side_effect = discord.Forbidden(MagicMock(status=403), "denied")
    else:
        group.db.add_member_to_study_group_db.side_effect = sqlite3.OperationalError("busy")
    view = GroupInvitationView(group, 456)
    await view.join_button.callback(interaction(456))
    assert group.member_ids == [123]
    if failure == "database":
        member.remove_roles.assert_awaited_once_with(role)
    else:
        group.db.add_member_to_study_group_db.assert_not_awaited()
    view.stop()


@pytest.mark.asyncio
async def test_declined_invitation_cannot_be_accepted():
    group, channel, role = group_fixture()
    owner = AsyncMock(spec=discord.Member)
    group.guild.get_member.return_value = owner
    view = GroupInvitationView(group, 456)
    await view.decline_button.callback(interaction(456))
    await view.join_button.callback(interaction(456))
    assert group.member_ids == [123]
    group.db.add_member_to_study_group_db.assert_not_awaited()


@pytest.mark.asyncio
async def test_group_cleanup_blocks_join_and_removes_every_pomodoro_alias():
    group, channel, role = group_fixture()
    group_id = group.group_id
    group.cog.active_study_groups[group_id] = group
    group.cog.log_mod_action = AsyncMock()
    group.guild.members = []
    role.delete = AsyncMock()
    session = MagicMock(group_id=7, text_id=30)
    unrelated = MagicMock(group_id=8, text_id=31)
    pomo = MagicMock()
    pomo.sessions = {7: session, group_id: session, 8: unrelated}
    group.bot.get_cog.side_effect = lambda name: pomo if name == "Pomodoro" else None
    view = GroupInvitationView(group, 456)

    async def delete_channel(*args, **kwargs):
        await view.join_button.callback(interaction(456))

    channel.delete.side_effect = delete_channel
    await group.end_group(delay=0, actor_id=123)
    assert pomo.sessions == {8: unrelated}
    assert not group.active and not group.member_ids
    assert group_id not in group.cog.active_study_groups
    group.db.add_member_to_study_group_db.assert_not_awaited()
    group.db.delete_study_group.assert_awaited_once_with(group_id)
    group.cog.log_mod_action.assert_awaited_once()
    view.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["complete", "delete"])
async def test_task_menu_database_action_targets_one_row_and_checks_owner_and_group(action):
    db = DBHandler(":memory:")
    await db.connect()
    try:
        async with db.lock:
            db.conn.executemany(
                "INSERT INTO tasks (id, user_id, description, group_id, task_number) VALUES (?, ?, ?, ?, ?)",
                [
                    (1, 123, "First", "a", 2),
                    (2, 123, "Second", "a", 1),
                    (3, 456, "Other owner", "a", 1),
                    (4, 123, "Global", None, 1),
                ],
            )
            db.conn.commit()
        assert not await db.apply_task_action(456, 1, "a", action)
        assert not await db.apply_task_action(123, 1, "b", action)
        assert not await db.apply_task_action(123, 1, None, action)
        assert await db.apply_task_action(123, 1, "a", action)
        tasks = await db.get_user_tasks(123)
        assert next(task for task in tasks if task["id"] == 2)["completed"] == 0
        assert next(task for task in tasks if task["id"] == 4)["completed"] == 0
        assert len(tasks) == (3 if action == "complete" else 2)
        with pytest.raises(ValueError):
            await db.apply_task_action(123, 2, "a", "invalid")
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_task_menu_rejects_malformed_selection():
    db = AsyncMock()
    view = TaskActionView([{"id": 1, "description": "Read", "group_id": None}], db, 123, "delete")
    select = view.children[0]
    select._values = ["invalid"]
    await select.callback(interaction())
    db.apply_task_action.assert_not_awaited()
    view.stop()


@pytest.mark.asyncio
async def test_mod_log_configuration_denies_non_manager_and_cross_guild_channel():
    group, channel, role = group_fixture()
    request = interaction(456)
    request.guild.id = 99
    with patch.dict(group.cog.set_mod_log_channel.callback.__globals__, check_manager=AsyncMock(return_value=False)):
        await group.cog.set_mod_log_channel.callback(group.cog, request)
    group.db.set_mod_log_channel.assert_not_awaited()
    foreign_channel = MagicMock(spec=discord.TextChannel)
    foreign_channel.guild.id = 100
    with patch.dict(group.cog.set_mod_log_channel.callback.__globals__, check_manager=AsyncMock(return_value=True)):
        await group.cog.set_mod_log_channel.callback(group.cog, interaction(), foreign_channel)
    group.db.set_mod_log_channel.assert_not_awaited()


@pytest.mark.asyncio
async def test_task_purge_reports_discord_cleanup_failure_after_deleting_records():
    bot = MagicMock()
    bot.db = AsyncMock()
    bot.db.purge_all_user_tasks.return_value = 2
    request = interaction()
    request.channel = AsyncMock(spec=discord.TextChannel)
    request.channel.purge.side_effect = discord.Forbidden(MagicMock(status=403), "denied")
    await TaskList(bot).purge_tasks.callback(TaskList(bot), request, all_tasks=True)
    bot.db.purge_all_user_tasks.assert_awaited_once_with(123)
    assert "messages could not be cleaned up" in request.followup.send.call_args.args[0]


@pytest.mark.asyncio
async def test_voice_setting_database_failure_rolls_back_discord_permissions():
    group, channel, role = group_fixture()
    channel.overwrites_for.return_value.speak = True
    group.can_control = AsyncMock(return_value=True)
    group.db.update_study_group_by_id.side_effect = sqlite3.OperationalError("busy")
    await group.speak_toggle_callback(interaction())
    assert group.speak_enabled is True
    assert channel.set_permissions.await_count == 4
    restored = channel.set_permissions.call_args.kwargs["overwrite"]
    assert restored.connect is True and restored.speak is True
    group.group_info_embed.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_voice_channel_does_not_persist_toggle():
    group, channel, role = group_fixture()
    group.can_control = AsyncMock(return_value=True)
    group.guild.get_channel.return_value = None
    await group.video_toggle_callback(interaction())
    assert group.video_mode == "off"
    group.db.update_study_group_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_dashboard_combines_mentions_embed_and_controls_in_one_message():
    group, voice_channel, role = group_fixture()
    group.bot.get_cog.return_value = None
    text_channel = AsyncMock(spec=discord.TextChannel)
    text_channel.mention = "<#30>"
    voice_channel.mention = "<#40>"
    group.guild.get_channel.side_effect = lambda channel_id: text_channel if channel_id == 30 else voice_channel
    group.guild.get_member.return_value = None
    text_channel.send.return_value.id = 70
    await group.button_view()
    text_channel.send.assert_not_awaited()
    await StudyGroup.group_info_embed(group)
    text_channel.send.assert_awaited_once()
    kwargs = text_channel.send.call_args.kwargs
    assert kwargs["content"] == "<@123>"
    assert kwargs["embed"].title == "Physics"
    assert kwargs["view"] is group.view and group.view is not None
    assert len(kwargs["embed"].fields) <= 25
    assert len(kwargs["embed"]) <= 6000
    assert group.info_embed_id == 70
    group.view.stop()


@pytest.mark.asyncio
async def test_moderator_log_database_error_does_not_abort_lifecycle():
    group, channel, role = group_fixture()
    group.db.get_mod_log_channel.side_effect = sqlite3.OperationalError("busy")
    await group.cog.log_mod_action(group.guild, "Study group ended", group.group_id, group.name, 123)
    channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_database_admission_is_atomic_and_rejects_ended_groups():
    db = DBHandler(":memory:")
    await db.connect()
    try:
        await db.save_study_group(
            {"group_id": "limited", "guild_id": 99, "name": "Physics", "creator_id": 123, "max_members": 2}
        )
        results = await asyncio.gather(
            db.add_member_to_study_group_db("limited", 456), db.add_member_to_study_group_db("limited", 789)
        )
        assert sorted(results) == [False, True]
        assert len(await db.fetch_members_of_group("limited")) == 2
        await db.delete_study_group("limited")
        assert not await db.add_member_to_study_group_db("limited", 456)
        assert await db.fetch_members_of_group("limited") == []
    finally:
        await db.close()
