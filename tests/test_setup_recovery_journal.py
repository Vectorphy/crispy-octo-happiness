import asyncio
import sqlite3
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from cogs._setup_view import SetupView
from cogs._staff_roles import StaffRoleSyncError, log_overwrites, sync_staff_roles
from cogs.manager import Manager
from cogs.study_groups import GroupInvitationView, StudyGroup, StudyGroupCog
from cogs.tasklist import TaskList
from database import DBHandler
from tests.test_group_controls import environment, interaction
from tests.test_setup import button, make_interaction, make_setup


@pytest.fixture
async def db(tmp_path):
    database = DBHandler(str(tmp_path / "recovery.sqlite"))
    await database.connect()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_dm_purge_keeps_all_nonpersonal_scopes_and_other_users(db):
    await db.add_task(5, "personal")
    await db.add_task(6, "other personal")
    await db.add_task(5, "server", guild_id=1)
    await db.add_task(5, "legacy group", group_id="legacy")
    await db.add_task(5, "guild group", group_id="group", guild_id=2)
    assert await db.purge_personal_tasks(5) == 1
    assert {row["description"] for row in await db.get_user_tasks(5)} == {"server", "legacy group", "guild group"}
    assert len(await db.get_user_tasks(6)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("all_tasks,remaining", [(False, 2), (True, 0)])
async def test_dm_purge_callback_routes_personal_and_explicit_global_requests(db, all_tasks, remaining):
    for description, group_id, guild_id in (("personal", None, None), ("server", None, 1), ("group", "legacy", None)):
        await db.add_task(5, description, group_id=group_id, guild_id=guild_id)
    await db.add_task(6, "other personal")
    bot = MagicMock(db=db)
    request = make_interaction(MagicMock(id=1))
    request.guild = None
    request.guild_id = None
    request.channel = MagicMock(spec=discord.DMChannel)
    request.channel_id = 55
    request.response.is_done = MagicMock(return_value=False)
    await TaskList.purge_tasks.callback(TaskList(bot), request, all_tasks=all_tasks)
    assert len(await db.get_user_tasks(5)) == remaining
    assert len(await db.get_user_tasks(6)) == 1


@pytest.mark.asyncio
async def test_settings_commit_requires_matching_journal_and_survives_restart(db):
    await db.save_setup(1, 10, 20, 7, 30)
    state = {"version": 1, "mutations": {}}
    await db.create_setup_recovery_journal(1, "operation", 5, state)
    with pytest.raises(RuntimeError):
        await db.save_setup(1, 11, 21, 25, 31, journal_operation_id="wrong")
    assert await db.get_default_max_members(1) == 7
    assert (await db.get_setup_recovery_journal(1))["phase"] == "prepared"
    await db.save_setup(1, 11, 21, 25, 31, journal_operation_id="operation")
    await db.close()
    await db.connect()
    assert await db.get_default_max_members(1) == 25
    assert (await db.get_setup_recovery_journal(1))["phase"] == "committed"
    with pytest.raises(RuntimeError):
        await db.update_setup_recovery_journal(1, "operation", state, phase="prepared")


async def moved_journal(db):
    manager, guild, category, channel = make_setup()
    manager.bot.db = db
    await db.save_setup(1, 10, 20, 10, 30, default_vc_id=50)
    original_acl = {guild.default_role: discord.PermissionOverwrite(view_channel=False, send_messages=True)}
    channel.overwrites = original_acl
    channel.category_id = None
    view = SetupView(manager, guild, 5, 10, 20, 10, 30, default_vc_id=50)
    await view.prepare_journal()
    await view.provision_channel("channel", 20, category, "cpo-commands")
    channel.overwrites = category.overwrites
    channel.category_id = category.id
    await db.close()
    await db.connect()
    guild.get_role.side_effect = lambda identifier: guild.default_role if identifier == guild.default_role.id else None
    restarted = Manager(manager.bot)
    restarted.get_permission_level = AsyncMock(return_value=3)
    return restarted, guild, channel, original_acl


@pytest.mark.asyncio
async def test_restart_restores_exact_original_acl_and_uncategorized_channel(db):
    manager, guild, channel, original_acl = await moved_journal(db)
    assert await manager._resume_setup_locked(guild) is False
    channel.edit.reset_mock()
    assert await manager._resume_setup_locked(guild, make_interaction(guild)) is True
    options = channel.edit.await_args.kwargs
    assert options["category"] is None
    assert SetupView.encode_acl(options["overwrites"]) == SetupView.encode_acl(original_acl)
    assert await db.get_setup_recovery_journal(1) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("conflict", ["acl", "settings", "ownership", "authority", "missing_role", "fetch"])
async def test_restart_recovery_fails_closed_on_uncertainty(db, conflict):
    manager, guild, channel, _ = await moved_journal(db)
    if conflict == "acl":
        channel.overwrites = {guild.default_role: discord.PermissionOverwrite(send_messages=False)}
        manager.bot.fetch_channel = AsyncMock(return_value=channel)
    elif conflict == "settings":
        await db.save_setup(1, 10, 20, 19, 30, default_vc_id=50)
    elif conflict == "ownership":
        db.get_all_study_groups = AsyncMock(side_effect=sqlite3.OperationalError("busy"))
    elif conflict == "authority":
        manager.get_permission_level.return_value = 0
    elif conflict == "missing_role":
        guild.get_role.return_value = None
        guild.get_role.side_effect = None
    else:
        manager.bot.fetch_channel = AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403), "denied"))
    channel.edit.reset_mock()
    assert await manager._resume_setup_locked(guild, make_interaction(guild)) is False
    channel.edit.assert_not_awaited()
    assert await db.get_setup_recovery_journal(1) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("proof", ["unique", "duplicate", "other_bot", "unavailable"])
async def test_creation_intent_is_durable_before_rest_and_requires_unique_bot_audit_proof(db, proof):
    manager, guild, category, _ = make_setup()
    manager.bot.db = db
    view = SetupView(manager, guild, 5, None, None, 10)
    await view.prepare_journal()

    async def crash_after_creation(*args, **kwargs):
        row = await db.get_setup_recovery_journal(1)
        assert row["state"]["mutations"]["category"]["id"] is None
        assert row["state"]["mutations"]["category"]["status"] == "intent"
        raise RuntimeError("crash after Discord accepted the request")

    guild.create_category.side_effect = crash_after_creation
    with pytest.raises(RuntimeError):
        await view.provision_channel("category", None, None, "CPO")
    await db.close()
    await db.connect()
    restarted = await SetupView.from_journal(manager, guild, await db.get_setup_recovery_journal(1))
    manager.bot.user.id = 100

    async def audit_logs(**kwargs):
        if proof == "unavailable":
            raise discord.Forbidden(MagicMock(status=403), "denied")
        for identifier in (10, 11) if proof == "duplicate" else (10,):
            yield MagicMock(
                reason=f"CPO setup {view.operation_id} category",
                user=manager.bot.user if proof != "other_bot" else MagicMock(id=999),
                target=MagicMock(id=identifier),
            )

    guild.audit_logs.side_effect = audit_logs
    await restarted.identify_created_intents()
    assert restarted.created_category_id == (10 if proof == "unique" else None)
    assert restarted.has_pending_resources()
    category.delete.assert_not_called()


@pytest.mark.asyncio
async def test_saved_defaults_survive_staff_sync_failure_and_retry_restart(db, monkeypatch):
    manager, guild, _, _ = make_setup()
    manager.bot.db = db
    await db.save_setup(1, 10, 20, 10, 30)
    view = SetupView(manager, guild, 5, 10, 20, 25, 30)
    view.snapshot = (10, 20, 30, 10, 86400, 86400, None)
    manager._setup_views[1] = view
    sync = AsyncMock(side_effect=StaffRoleSyncError("role hierarchy"))
    monkeypatch.setattr("cogs._setup_view.sync_staff_roles", sync)
    await button(view, "Save").callback(make_interaction(guild))
    assert await db.get_default_max_members(1) == 25
    assert (await db.get_setup_recovery_journal(1))["phase"] == "sync_pending"
    await db.close()
    await db.connect()
    monkeypatch.setattr("cogs.manager.sync_staff_roles", AsyncMock())
    restarted = Manager(manager.bot)
    assert await restarted._resume_setup_locked(guild) is True
    assert await db.get_setup_recovery_journal(1) is None
    assert await db.get_default_max_members(1) == 25


@pytest.mark.asyncio
async def test_log_acl_denies_nonstaff_roles_members_and_stale_staff_role(db):
    manager, guild, _, _ = make_setup()
    manager.bot.db = db
    guild.owner_id = 999
    guild.members = []
    outsider = MagicMock(spec=discord.Member, id=6, guild=guild)
    outsider.guild_permissions = discord.Permissions.none()
    staff = MagicMock(spec=discord.Member, id=5, guild=guild)
    staff.guild_permissions = discord.Permissions.none()
    stale_role = MagicMock(spec=discord.Role, id=90, guild=guild)
    guild.members = [staff, outsider]
    guild.get_member.side_effect = {5: staff, 6: outsider}.get
    await db.add_manager(5, 1, 3)
    original = {
        guild.default_role: discord.PermissionOverwrite(view_channel=True),
        stale_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
        outsider: discord.PermissionOverwrite(view_channel=True),
    }
    private = await log_overwrites(manager.bot, guild, original)
    assert private[staff].view_channel is True
    assert private[guild.me].view_channel is True
    for target in (guild.default_role, stale_role, outsider):
        assert private[target].view_channel is False
    assert private[stale_role].send_messages is False
    assert original[stale_role].view_channel is True


@pytest.mark.asyncio
async def test_log_is_sealed_before_staff_sync_hierarchy_failure(db):
    manager, guild, category, _ = make_setup()
    manager.bot.db = db
    await db.save_setup(1, 10, 20, 10, 30)
    guild.me.guild_permissions = discord.Permissions(manage_roles=False)
    log = guild.get_channel(30)
    log.overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=True)}
    with pytest.raises(StaffRoleSyncError):
        await sync_staff_roles(manager.bot, guild, category)
    assert log.edit.await_args.kwargs["overwrites"][guild.default_role].view_channel is False
    assert log.edit.await_args.kwargs["overwrites"][guild.me].view_channel is True


@pytest.mark.asyncio
@pytest.mark.parametrize("guild_id,override,expected", [(1, None, 25), (1, 4, 4), (2, None, 9)])
async def test_new_group_uses_saved_guild_default_after_restart_and_explicit_override(
    db, monkeypatch, guild_id, override, expected
):
    await db.save_setup(1, 20, 30, 25)
    await db.save_setup(2, 20, 30, 9)
    await db.close()
    await db.connect()
    cog, guild, people, category, text, _ = environment()
    guild.id = guild_id
    cog.bot.db = db
    real_embed = StudyGroup.group_info_embed
    monkeypatch.setattr(StudyGroup, "button_view", AsyncMock())
    monkeypatch.setattr(StudyGroup, "group_info_embed", AsyncMock())
    monkeypatch.setattr(StudyGroup, "check_end_condition", AsyncMock())
    await StudyGroupCog.create_group.callback(
        cog, interaction(cog.bot, guild, people[5]), "", name="saved", max_members=override
    )
    group = next(iter(cog.active_study_groups.values()))
    assert group.max_members == expected
    assert category.create_voice_channel.await_args.kwargs["user_limit"] == expected
    record = (await db.get_all_study_groups(guild.id))[0]
    assert record["max_members"] == expected
    assert await db.get_default_max_members(2) == 9
    await db.save_setup(1, 20, 30, 50)
    assert group.max_members == expected
    assert ((await db.get_all_study_groups(guild.id))[0])["max_members"] == expected

    group.view = discord.ui.View()
    text.send.return_value = MagicMock(id=500)
    await real_embed(group)
    embed = text.send.await_args.kwargs["embed"]
    assert next(field.value for field in embed.fields if field.name == "Max Size") == str(expected)
    group.member_ids = list(range(1000, 1000 + expected))
    invite = GroupInvitationView(group, 6)
    request = interaction(cog.bot, guild, people[6])
    await invite.join_button.callback(request)
    assert request.edit_original_response.await_args.kwargs["content"] == "This study group is full."


@pytest.mark.asyncio
@pytest.mark.parametrize("state", [{"version": 999, "mutations": {}}, {"version": 1, "mutations": []}])
async def test_malformed_journal_cannot_trigger_recovery_mutations(db, state):
    manager, guild, category, channel = make_setup()
    manager.bot.db = db
    await db.create_setup_recovery_journal(1, "malformed", 5, state)
    with pytest.raises(ValueError):
        await manager._resume_setup_locked(guild, make_interaction(guild))
    category.delete.assert_not_called()
    channel.edit.assert_not_awaited()
    assert await db.get_setup_recovery_journal(1) is not None


async def created_journal(db, key="channel"):
    manager, guild, category, channel = make_setup()
    manager.bot.db = db
    await db.save_setup(1, None, None, 10)
    view = SetupView(manager, guild, 5, None, None, 10)
    await view.prepare_journal()
    category.channels = []
    category.category_id = None
    resource = await view.provision_channel(key, None, category if key != "category" else None, "draft")
    resource.delete = AsyncMock()
    return manager, guild, view, resource


@pytest.mark.asyncio
@pytest.mark.parametrize("claim_at", ["fetch", "journal", "group"])
async def test_recovery_rechecks_delayed_created_resource_claims(db, claim_at):
    manager, guild, view, channel = await created_journal(db)
    fetch = manager.bot.fetch_channel.side_effect
    write = view.write_journal

    async def claim():
        if claim_at == "group":
            await db.save_study_group(
                {
                    "guild_id": 1,
                    "name": "claimed",
                    "group_id": "claimed",
                    "creator_id": 5,
                    "text_id": channel.id,
                    "active": 1,
                }
            )
        else:
            await db.set_mod_log_channel(1, channel.id)

    async def fetched(identifier):
        result = await fetch(identifier)
        if claim_at == "fetch":
            await claim()
        return result

    async def journal_written():
        await write()
        if claim_at in ("journal", "group"):
            await claim()

    manager.bot.fetch_channel.side_effect = fetched
    view.write_journal = journal_written
    result = await view.recover_retained_resources(make_interaction(guild))
    channel.delete.assert_not_awaited()
    assert channel.id in result["skipped"]
    assert await db.get_setup_recovery_journal(1) is not None


@pytest.mark.asyncio
async def test_moved_resource_claim_after_journal_intent_prevents_restore(db):
    manager, guild, channel, _ = await moved_journal(db)
    view = await SetupView.from_journal(manager, guild, await db.get_setup_recovery_journal(1))
    write = view.write_journal

    async def journal_written():
        await write()
        await db.save_study_group(
            {
                "guild_id": 1,
                "name": "claimed",
                "group_id": "claimed",
                "creator_id": 5,
                "text_id": channel.id,
                "active": 1,
            }
        )

    view.write_journal = journal_written
    channel.edit.reset_mock()
    result = await view.recover_retained_resources(make_interaction(guild))
    channel.edit.assert_not_awaited()
    assert channel.id in result["skipped"]


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["channel", "category"])
async def test_queued_configuration_cannot_claim_resource_deleted_by_recovery(db, monkeypatch, key):
    manager, guild, view, resource = await created_journal(db, key)
    cog = StudyGroupCog(manager.bot)
    assert manager._setup_locks is cog._creation_locks
    manager.bot.get_cog.return_value = manager
    monkeypatch.setattr("cogs.study_groups.check_manager", AsyncMock(return_value=True))
    fetched = asyncio.Event()
    release = asyncio.Event()
    removed = False
    fetch = manager.bot.fetch_channel.side_effect

    async def fetch_channel(identifier):
        if removed:
            raise discord.NotFound(MagicMock(status=404), "deleted")
        result = await fetch(identifier)
        fetched.set()
        await release.wait()
        return result

    async def delete(**kwargs):
        nonlocal removed
        removed = True

    manager.bot.fetch_channel.side_effect = fetch_channel
    resource.delete.side_effect = delete
    recovery = asyncio.create_task(view.recover_retained_resources(make_interaction(guild)))
    await fetched.wait()
    request = make_interaction(guild)
    request.client = manager.bot
    command = cog.set_mod_log_channel if key == "channel" else cog.set_group_category
    configured = asyncio.create_task(command.callback(cog, request, resource))
    await asyncio.sleep(0)
    assert not configured.done()
    release.set()
    await asyncio.wait_for(asyncio.gather(recovery, configured), timeout=2)
    assert removed
    assert await db.get_mod_log_channel(1) is None
    assert await db.get_group_category(1) is None


@pytest.mark.asyncio
async def test_cancelled_recovery_retains_intent_and_releases_guild_lock(db):
    manager, guild, view, resource = await created_journal(db)
    deleting = asyncio.Event()

    async def blocked_delete(**kwargs):
        deleting.set()
        await asyncio.Event().wait()

    resource.delete.side_effect = blocked_delete
    recovery = asyncio.create_task(view.recover_retained_resources(make_interaction(guild)))
    await deleting.wait()
    recovery.cancel()
    with pytest.raises(asyncio.CancelledError):
        await recovery
    row = await db.get_setup_recovery_journal(1)
    assert row["state"]["mutations"]["channel"]["status"] == "rollback_intent"
    assert view.has_pending_resources()
    lock = manager._setup_locks[1]
    await asyncio.wait_for(lock.acquire(), timeout=1)
    lock.release()
