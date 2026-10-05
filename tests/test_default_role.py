from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from cogs._access_policy import AccessCommandTree, AccessView, require_guild_access
from cogs._setup_view import DefaultRoleSelect, SetupView
from database import DBHandler
from tests.test_setup import make_interaction, make_setup


@pytest.fixture
async def db(tmp_path):
    database = DBHandler(str(tmp_path / "role.sqlite"))
    await database.connect()
    yield database
    await database.close()


def role_environment(db):
    manager, guild, _, _ = make_setup()
    manager.bot.db = db
    manager.bot.get_guild.return_value = guild
    manager.bot.get_cog.return_value = manager
    member = MagicMock(spec=discord.Member, id=5, guild=guild)
    member.roles = []
    guild.fetch_member = AsyncMock(return_value=member)
    role = MagicMock(spec=discord.Role, id=70, guild=guild, name="CPO Member")
    role.name = "CPO Member"
    role.permissions = discord.Permissions.none()
    role.mentionable = False
    role.managed = False
    role.is_default.return_value = False
    role.delete = AsyncMock()
    guild.fetch_roles = AsyncMock(return_value=[role])
    guild.create_role = AsyncMock(return_value=role)
    guild.get_role.side_effect = lambda identifier: (
        role if identifier == role.id else guild.default_role if identifier == guild.default_role.id else None
    )
    return manager, guild, member, role


@pytest.mark.asyncio
async def test_default_role_nullable_setting_is_guild_scoped_and_persisted(db):
    await db.save_setup(1, 10, 20, 10, default_role_id=70, update_default_role=True)
    await db.save_setup(2, 10, 20, 10)
    await db.close()
    await db.connect()
    assert await db.get_default_role(1) == 70
    assert await db.get_default_role(2) is None
    await db.save_setup(1, 10, 20, 12)
    assert await db.get_default_role(1) == 70
    await db.save_setup(1, 10, 20, 12, update_default_role=True)
    assert await db.get_default_role(1) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", [0, 3, 4, 5])
async def test_role_gate_has_no_staff_or_supreme_bypass_but_setup_is_authorized(db, tier):
    manager, guild, member, role = role_environment(db)
    await db.save_setup(1, 10, 20, 10, default_role_id=70, update_default_role=True)
    manager.get_permission_level.return_value = tier
    request = make_interaction(guild)
    request.user = member
    assert await require_guild_access(manager.bot, request) is False
    assert await require_guild_access(manager.bot, request, setup_exempt=True) is (tier >= 3)
    member.roles = [role]
    assert await require_guild_access(manager.bot, request) is True
    member.roles = []
    assert await require_guild_access(manager.bot, request) is False


@pytest.mark.asyncio
async def test_disappeared_role_and_departed_dm_recipient_fail_closed(db):
    manager, guild, member, role = role_environment(db)
    await db.save_setup(1, 10, 20, 10, default_role_id=70, update_default_role=True)
    member.roles = [role]
    guild.get_role.side_effect = None
    guild.get_role.return_value = None
    request = make_interaction(guild)
    request.user = member
    assert await require_guild_access(manager.bot, request) is False
    request.guild = None
    request.guild_id = None
    request.user = MagicMock(spec=discord.User, id=5)
    guild.fetch_member.side_effect = discord.NotFound(MagicMock(status=404), "departed")
    assert await require_guild_access(manager.bot, request, guild_id=1) is False
    assert await require_guild_access(manager.bot, request) is True


@pytest.mark.asyncio
async def test_role_revocation_during_settings_read_is_rechecked_before_dispatch(db, monkeypatch):
    manager, guild, member, role = role_environment(db)
    await db.save_setup(1, 10, 20, 10, default_role_id=70, update_default_role=True)
    member.roles = [role]
    request = make_interaction(guild)
    request.user = member
    current_member = MagicMock(spec=discord.Member, id=5, guild=guild)
    current_member.roles = []
    original = db.get_default_role

    async def revoke_during_read(guild_id):
        result = await original(guild_id)
        guild.fetch_member.return_value = current_member
        return result

    monkeypatch.setattr(db, "get_default_role", revoke_during_read)
    assert await require_guild_access(manager.bot, request) is False
    guild.fetch_member.assert_awaited_once_with(5)


@pytest.mark.asyncio
async def test_tree_and_component_gates_deny_before_callbacks(db):
    manager, guild, member, _ = role_environment(db)
    await db.save_setup(1, 10, 20, 10, default_role_id=70, update_default_role=True)
    request = make_interaction(guild)
    request.user = member
    request.client = manager.bot
    request.response.is_done = MagicMock(return_value=False)
    request.data = {"name": "add_bot_dev"}
    assert await AccessCommandTree.interaction_check(MagicMock(client=manager.bot), request) is False
    request.data = {"name": "setup"}
    assert await AccessCommandTree.interaction_check(MagicMock(client=manager.bot), request) is True
    view = AccessView()
    view.guild_id = 1
    item = MagicMock()
    item.callback = AsyncMock()
    await view._scheduled_task(item, request)
    item.callback.assert_not_awaited()
    view.stop()


@pytest.mark.asyncio
async def test_picker_can_clear_role_without_enrolling_members(db):
    manager, guild, _, role = role_environment(db)
    view = SetupView(manager, guild, 5, 10, 20, 10, default_role_id=70)
    manager._setup_views[1] = view
    picker = next(child for child in view.children if isinstance(child, DefaultRoleSelect))
    picker._values = []
    await picker.callback(make_interaction(guild))
    assert view.default_role_id is None
    role.edit.assert_not_called()
    assert await db.get_default_role(1) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("protected", ["none", "members", "managed", "permissions", "saved", "group"])
async def test_role_journal_survives_restart_and_recovery_protects_in_use_roles(db, protected):
    manager, guild, member, role = role_environment(db)
    await db.save_setup(1, 10, 20, 10, 30)
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    view.new_role_name = "CPO Member"
    await view.prepare_journal()
    assert await view.provision_default_role() == 70
    guild.create_role.assert_awaited_once()
    member.add_roles.assert_not_called()
    await db.close()
    await db.connect()
    restarted = await SetupView.from_journal(manager, guild, await db.get_setup_recovery_journal(1))

    async def members(**kwargs):
        if protected == "members":
            member.roles = [role]
            yield member

    guild.fetch_members.side_effect = members
    if protected == "managed":
        role.managed = True
    elif protected == "permissions":
        role.permissions = discord.Permissions(manage_roles=True)
    elif protected == "saved":
        await db.save_setup(1, 10, 20, 10, 30, default_role_id=70, update_default_role=True)
    elif protected == "group":
        await db.save_study_group(
            {
                "guild_id": 1,
                "group_id": "live",
                "name": "live",
                "creator_id": 5,
                "category_id": 10,
                "max_members": 10,
                "group_role_id": 70,
                "member_ids": [],
            }
        )
    await restarted.recover_retained_resources(make_interaction(guild))
    if protected == "none":
        role.delete.assert_awaited_once()
        assert await db.get_setup_recovery_journal(1) is None
    else:
        role.delete.assert_not_awaited()
        assert await db.get_setup_recovery_journal(1) is not None


@pytest.mark.asyncio
async def test_role_created_but_result_save_failed_recovers_only_from_bot_audit(db, monkeypatch):
    manager, guild, _, role = role_environment(db)
    await db.save_setup(1, 10, 20, 10, 30)
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    view.new_role_name = "CPO Member"
    await view.prepare_journal()
    update = db.update_setup_recovery_journal
    writes = 0

    async def fail_result(*args, **kwargs):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise RuntimeError("result write failed")
        await update(*args, **kwargs)

    monkeypatch.setattr(db, "update_setup_recovery_journal", fail_result)
    with pytest.raises(RuntimeError):
        await view.provision_default_role()
    row = await db.get_setup_recovery_journal(1)
    assert row["state"]["mutations"]["role"]["id"] is None
    assert await db.get_default_role(1) is None
    monkeypatch.setattr(db, "update_setup_recovery_journal", update)
    await db.close()
    await db.connect()
    restarted = await SetupView.from_journal(manager, guild, await db.get_setup_recovery_journal(1))
    manager.bot.user.id = 100

    async def audit(**kwargs):
        assert kwargs["action"] == discord.AuditLogAction.role_create
        yield MagicMock(reason=f"CPO setup {view.operation_id} role", user=manager.bot.user, target=MagicMock(id=70))

    guild.audit_logs.side_effect = audit
    await restarted.identify_created_intents()
    assert restarted.created_role_id == 70
    assert (await db.get_setup_recovery_journal(1))["state"]["mutations"]["role"]["id"] == 70
    role.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_role_commit_rolls_back_settings_and_journal_together(db):
    await db.save_setup(1, 10, 20, 10, default_role_id=70, update_default_role=True)
    await db.create_setup_recovery_journal(1, "operation", 5, {"version": 1, "mutations": {}})
    with pytest.raises(ValueError):
        await db.save_setup(
            1, 10, 20, 25, default_role_id=-1, update_default_role=True, journal_operation_id="operation"
        )
    assert await db.get_default_role(1) == 70
    assert await db.get_default_max_members(1) == 10
    assert (await db.get_setup_recovery_journal(1))["phase"] == "prepared"


@pytest.mark.asyncio
async def test_legacy_seven_field_journal_loads_without_role_metadata(db):
    manager, guild, _, _ = role_environment(db)
    state = {
        "version": 1,
        "original": [10, 20, 30, 10, 86400, 86400, None],
        "desired": [10, 20, 30, 10, 86400, 86400, None],
        "mutations": {},
    }
    await db.create_setup_recovery_journal(1, "legacy", 5, state)
    view = await SetupView.from_journal(manager, guild, await db.get_setup_recovery_journal(1))
    assert view.snapshot == tuple(state["original"])
    assert view.default_role_id is None
