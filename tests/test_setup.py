import asyncio
import sqlite3
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock

import discord
import pytest

from cogs._setup_view import DurationModal, NewCategoryModal, SetupView, VoiceSelect
from cogs.manager import Manager, PermissionLevel


@pytest.fixture(autouse=True)
def isolate_staff_role_sync(monkeypatch):
    async def sync_staff_roles(bot, guild, category):
        return category

    monkeypatch.setitem(SetupView._save_locked.__globals__, "sync_staff_roles", AsyncMock(side_effect=sync_staff_roles))


def make_interaction(guild: discord.Guild, user_id: int = 5) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = guild
    interaction.guild_id = guild.id
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


def make_setup(category_id: int | None = 10, channel_id: int | None = 20):
    guild = MagicMock(spec=discord.Guild)
    guild.id = 1
    guild.me = MagicMock(spec=discord.Member)
    guild.me.id = 100
    guild.me.guild = guild
    guild.members = []
    perms = MagicMock()
    perms.manage_channels = True
    perms.view_channel = True
    perms.send_messages = True
    perms.embed_links = True
    guild.me.guild_permissions = perms

    category = MagicMock(spec=discord.CategoryChannel)
    category.id = 10
    category.guild = guild
    category.overwrites = {}
    category.permissions_for.return_value = perms
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 20
    channel.guild = guild
    channel.overwrites = {}
    channel.category_id = category_id
    channel.permissions_synced = True
    channel.permissions_for.return_value = perms
    channel.edit = AsyncMock(return_value=None)
    log_channel = MagicMock(spec=discord.TextChannel)
    log_channel.id = 30
    log_channel.guild = guild
    log_channel.overwrites = {}
    log_channel.category_id = category_id
    log_channel.permissions_synced = True
    log_channel.permissions_for.return_value = perms
    log_channel.edit = AsyncMock(return_value=None)
    voice = MagicMock(spec=discord.VoiceChannel)
    voice.id = 50
    voice.guild = guild
    voice.overwrites = {}
    voice.category_id = category_id
    voice.permissions_synced = True
    voice.edit = AsyncMock(return_value=None)
    guild.get_channel.side_effect = lambda identifier: {10: category, 20: channel, 30: log_channel, 50: voice}.get(
        identifier
    )
    guild.create_voice_channel = AsyncMock(return_value=voice)
    guild.create_category = AsyncMock(return_value=category)
    guild.create_text_channel = AsyncMock(return_value=channel)
    guild.default_role = MagicMock(spec=discord.Role)
    guild.default_role.id = 1
    guild.default_role.guild = guild
    guild.get_member.return_value = MagicMock(spec=discord.Member)
    guild.roles = []

    bot = MagicMock()
    bot.fetch_channel = AsyncMock(side_effect=lambda identifier: guild.get_channel(identifier))
    bot.db = AsyncMock()
    bot.db.get_group_category.return_value = category_id
    bot.db.get_commands_channel.return_value = channel_id
    bot.db.get_mod_log_channel.return_value = 30
    bot.db.get_default_max_members.return_value = 10
    bot.db.get_default_group_duration.return_value = 86400
    bot.db.get_default_pomodoro_duration.return_value = 86400
    bot.db.get_default_vc.return_value = None
    bot.db.get_default_role.return_value = None
    bot.db.get_all_study_groups.return_value = []

    async def fetched(identifier):
        resource = guild.get_channel(identifier)
        if resource is not None and resource.edit.await_args is not None:
            options = resource.edit.await_args.kwargs
            if "overwrites" in options:
                resource.overwrites = options["overwrites"]
            if "category" in options:
                resource.category_id = options["category"].id if options["category"] else None
        for create in (guild.create_text_channel, guild.create_voice_channel):
            if create.await_args is not None and create.return_value is resource:
                resource.overwrites = create.await_args.kwargs.get("overwrites", {})
                resource.category_id = create.await_args.kwargs["category"].id
        return resource

    bot.fetch_channel.side_effect = fetched
    manager = Manager(bot)
    setattr(manager, "get_permission_level", AsyncMock(return_value=PermissionLevel.MODERATOR))
    return manager, guild, category, channel


def button(view: SetupView, label: str) -> discord.ui.Button:
    return next(item for item in view.children if isinstance(item, discord.ui.Button) and item.label == label)


@pytest.mark.asyncio
async def test_setup_duration_editor_stages_and_saves_defaults():
    manager, guild, _, _ = make_setup()
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    editor = DurationModal(view)
    editor.group_duration._value = "1d 12h"
    editor.pomodoro_duration._value = "48 hours"
    await editor.on_submit(make_interaction(guild))
    assert (view.group_duration, view.pomodoro_duration) == (129600, 172800)
    manager.bot.db.save_setup.assert_not_awaited()
    await button(view, "Save").callback(make_interaction(guild))
    manager.bot.db.save_setup.assert_awaited_once_with(
        1,
        10,
        20,
        10,
        30,
        default_group_duration=129600,
        default_pomodoro_duration=172800,
        default_vc_id=50,
        journal_operation_id=ANY,
        default_role_id=None,
        update_default_role=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("duration", ["0h", "invalid", "-1h", "999999999999999999h"])
async def test_setup_rejects_invalid_lifetimes_without_changing_draft(duration):
    manager, guild, _, _ = make_setup()
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    editor = DurationModal(view)
    editor.group_duration._value = duration
    editor.pomodoro_duration._value = "24h"
    interaction = make_interaction(guild)
    await editor.on_submit(interaction)
    assert (view.group_duration, view.pomodoro_duration) == (86400, 86400)
    interaction.response.send_message.assert_awaited_once()
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True
    manager.bot.db.save_setup.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("setting", ["get_default_group_duration", "get_default_pomodoro_duration"])
async def test_setup_rejects_stale_lifetimes_before_provisioning(setting):
    manager, guild, _, _ = make_setup()
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    getattr(manager.bot.db, setting).return_value = 172800
    interaction = make_interaction(guild)
    await button(view, "Save").callback(interaction)
    assert "settings changed" in interaction.followup.send.call_args.args[0]
    guild.create_text_channel.assert_not_awaited()
    manager.bot.db.save_setup.assert_not_awaited()


@pytest.mark.asyncio
async def test_setup_stages_options_without_writing_until_save():
    manager, guild, category, channel = make_setup()
    interaction = make_interaction(guild)
    interaction.followup.send.return_value = AsyncMock()

    await Manager.setup.callback(manager, interaction, max_members=25, category=category)

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    view = manager._setup_views[guild.id]
    assert view.max_members == 25
    assert view.category_id == category.id
    assert view.snapshot == (10, 20, 30, 10, 86400, 86400, None)
    manager.bot.db.save_setup.assert_not_awaited()
    guild.create_text_channel.assert_not_awaited()

    save_interaction = make_interaction(guild)
    await button(view, "Save").callback(save_interaction)

    manager.bot.db.save_setup.assert_awaited_once_with(
        1,
        10,
        20,
        25,
        30,
        default_group_duration=86400,
        default_pomodoro_duration=86400,
        default_vc_id=50,
        journal_operation_id=ANY,
        default_role_id=None,
        update_default_role=True,
    )
    assert guild.id not in manager._setup_views
    assert all(item.disabled for item in view.children)
    assert save_interaction.followup.send.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_setup_rejects_other_users_on_callbacks():
    manager, guild, _, _ = make_setup()
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    other = make_interaction(guild, user_id=6)

    assert await view.interaction_check(other) is False
    other.response.send_message.assert_awaited_once()
    manager.bot.db.save_setup.assert_not_awaited()


@pytest.mark.asyncio
async def test_setup_cancel_leaves_settings_unchanged():
    manager, guild, _, _ = make_setup()
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    interaction = make_interaction(guild)

    await button(view, "Cancel").callback(interaction)

    manager.bot.db.save_setup.assert_not_awaited()
    guild.create_category.assert_not_awaited()
    guild.create_text_channel.assert_not_awaited()
    assert "No settings changed" in interaction.response.edit_message.call_args.kwargs["content"]


@pytest.mark.asyncio
async def test_setup_rejects_stale_settings_before_discord_mutation():
    manager, guild, _, _ = make_setup()
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    manager.bot.db.get_group_category.return_value = 11

    await button(view, "Save").callback(make_interaction(guild))

    manager.bot.db.save_setup.assert_not_awaited()
    guild.create_category.assert_not_awaited()
    guild.create_text_channel.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_save_reuses_created_channel_and_reports_its_id():
    manager, guild, _, channel = make_setup(channel_id=None)
    view = SetupView(manager, guild, 5, 10, None, 10, 30)
    manager._setup_views[guild.id] = view
    manager.bot.db.save_setup.side_effect = [RuntimeError("storage unavailable"), None]
    first = make_interaction(guild)

    await button(view, "Save").callback(first)

    assert view.created_channel_id == channel.id
    assert "commands channel ID 20" in first.followup.send.call_args.args[0]
    assert manager._setup_views[guild.id] is view

    await button(view, "Save").callback(make_interaction(guild))

    guild.create_text_channel.assert_awaited_once()
    assert manager.bot.db.save_setup.await_count == 2
    guild.create_voice_channel.assert_awaited_once()


@pytest.mark.asyncio
async def test_default_vc_is_created_with_category_permissions():
    manager, guild, category, _ = make_setup()
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    await button(view, "Save").callback(make_interaction(guild))
    guild.create_voice_channel.assert_awaited_once_with(
        "CPO Lobby", category=category, overwrites=category.overwrites, reason=ANY
    )
    assert view.default_vc_id == 50


@pytest.mark.asyncio
async def test_recorded_default_vc_moves_and_syncs_without_duplicate_creation():
    manager, guild, category, _ = make_setup()
    manager.bot.db.get_default_vc.return_value = 50
    voice = guild.get_channel(50)
    voice.category_id = 99
    voice.permissions_synced = False
    view = SetupView(manager, guild, 5, 10, 20, 10, 30, default_vc_id=50)
    manager._setup_views[guild.id] = view
    await button(view, "Save").callback(make_interaction(guild))
    voice.edit.assert_awaited_once_with(category=category, overwrites=category.overwrites, reason=ANY)
    guild.create_voice_channel.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_default_vc_setting_prevents_discord_changes():
    manager, guild, _, _ = make_setup()
    manager.bot.db.get_default_vc.return_value = 60
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    await button(view, "Save").callback(make_interaction(guild))
    manager.bot.db.save_setup.assert_not_awaited()
    guild.create_voice_channel.assert_not_awaited()


@pytest.mark.asyncio
async def test_recorded_channel_move_syncs_category_permissions():
    manager, guild, _, channel = make_setup()
    channel.category_id = 99
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view

    await button(view, "Save").callback(make_interaction(guild))

    channel.edit.assert_awaited_once()
    assert channel.edit.call_args.kwargs["overwrites"] == guild.get_channel(10).overwrites
    manager.bot.db.save_setup.assert_awaited_once_with(
        1,
        10,
        20,
        10,
        30,
        default_group_duration=86400,
        default_pomodoro_duration=86400,
        default_vc_id=50,
        journal_operation_id=ANY,
        default_role_id=None,
        update_default_role=True,
    )


@pytest.mark.asyncio
async def test_setup_creates_synced_log_channel_and_reuses_it_on_retry():
    manager, guild, _, _ = make_setup()
    log_channel = guild.get_channel(30)
    manager.bot.db.get_mod_log_channel.return_value = None
    guild.create_text_channel = AsyncMock(return_value=log_channel)
    manager.bot.db.save_setup.side_effect = [RuntimeError("storage unavailable"), None]
    view = SetupView(manager, guild, 5, 10, 20, 10, None)
    manager._setup_views[guild.id] = view
    first = make_interaction(guild)

    await button(view, "Save").callback(first)

    assert view.created_log_channel_id == 30
    assert "log channel ID 30" in first.followup.send.call_args.args[0]
    options = guild.create_text_channel.call_args.kwargs
    overwrites = options["overwrites"]
    assert options["category"].id == 10
    assert overwrites[guild.default_role].view_channel is False
    assert overwrites[guild.me].view_channel is True
    manager.bot.db.save_setup.assert_awaited_once_with(
        1,
        10,
        20,
        10,
        30,
        default_group_duration=86400,
        default_pomodoro_duration=86400,
        default_vc_id=50,
        journal_operation_id=ANY,
        default_role_id=None,
        update_default_role=True,
    )

    await button(view, "Save").callback(make_interaction(guild))

    guild.create_text_channel.assert_awaited_once()
    assert manager.bot.db.save_setup.await_count == 2


@pytest.mark.asyncio
async def test_cancel_during_save_cannot_claim_no_settings_changed():
    manager, guild, _, _ = make_setup()
    log_channel = guild.get_channel(30)
    manager.bot.db.get_mod_log_channel.return_value = None
    entered = asyncio.Event()
    release = asyncio.Event()

    async def create_log_channel(*args, **kwargs):
        entered.set()
        await release.wait()
        return log_channel

    guild.create_text_channel = AsyncMock(side_effect=create_log_channel)
    view = SetupView(manager, guild, 5, 10, 20, 10, None)
    manager._setup_views[guild.id] = view
    save = asyncio.create_task(button(view, "Save").callback(make_interaction(guild)))
    await asyncio.wait_for(entered.wait(), timeout=2)
    cancel_interaction = make_interaction(guild)

    await button(view, "Cancel").callback(cancel_interaction)

    cancel_interaction.response.edit_message.assert_not_awaited()
    assert "Save is in progress" in cancel_interaction.response.send_message.call_args.args[0]
    release.set()
    await asyncio.wait_for(save, timeout=2)
    manager.bot.db.save_setup.assert_awaited_once_with(
        1,
        10,
        20,
        10,
        30,
        default_group_duration=86400,
        default_pomodoro_duration=86400,
        default_vc_id=50,
        journal_operation_id=ANY,
        default_role_id=None,
        update_default_role=True,
    )


@pytest.mark.asyncio
async def test_category_selector_rejects_unresolvable_channel_id():
    manager, guild, _, _ = make_setup()
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    selector = next(item for item in view.children if isinstance(item, discord.ui.ChannelSelect))
    selector._values = [SimpleNamespace(id=999)]
    interaction = make_interaction(guild)

    await selector.callback(interaction)

    assert view.category_id == 10
    interaction.response.send_message.assert_awaited_once_with("Choose a category in this server.", ephemeral=True)


@pytest.mark.asyncio
async def test_log_creation_failure_keeps_pending_commands_id_for_cancel_report():
    manager, guild, _, channel = make_setup(channel_id=None)
    manager.bot.db.get_mod_log_channel.return_value = None
    guild.create_text_channel = AsyncMock(side_effect=[channel, RuntimeError("log unavailable")])
    view = SetupView(manager, guild, 5, 10, None, 10, None)
    manager._setup_views[guild.id] = view
    save_interaction = make_interaction(guild)

    await button(view, "Save").callback(save_interaction)

    assert view.created_channel_id == 20
    assert view.created_log_channel_id is None
    assert "commands channel ID 20" in save_interaction.followup.send.call_args.args[0]
    manager.bot.db.save_setup.assert_not_awaited()

    cancel_interaction = make_interaction(guild)
    await button(view, "Cancel").callback(cancel_interaction)
    assert "commands channel ID 20" in cancel_interaction.response.edit_message.call_args.kwargs["content"]


@pytest.mark.asyncio
async def test_recorded_log_channel_move_syncs_category_permissions():
    manager, guild, _, _ = make_setup()
    log_channel = guild.get_channel(30)
    log_channel.category_id = 99
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view

    await button(view, "Save").callback(make_interaction(guild))

    log_channel.edit.assert_awaited_once()
    assert log_channel.edit.call_args.kwargs["overwrites"][guild.default_role].view_channel is False
    guild.create_text_channel.assert_not_awaited()
    manager.bot.db.save_setup.assert_awaited_once_with(
        1,
        10,
        20,
        10,
        30,
        default_group_duration=86400,
        default_pomodoro_duration=86400,
        default_vc_id=50,
        journal_operation_id=ANY,
        default_role_id=None,
        update_default_role=True,
    )


@pytest.mark.asyncio
async def test_new_category_modal_stages_then_creates_category_and_both_channels_once():
    manager, guild, category, commands = make_setup(category_id=None, channel_id=None)
    manager.bot.db.get_mod_log_channel.return_value = None
    category.id = 40
    commands.id = 21
    logs = guild.get_channel(30)
    logs.id = 31
    channels = {40: category, 21: commands, 31: logs}
    guild.get_channel.side_effect = lambda identifier: channels.get(identifier)
    guild.create_category = AsyncMock(return_value=category)
    guild.create_text_channel = AsyncMock(
        side_effect=lambda name, **kwargs: channels[21 if name == "cpo-commands" else 31]
    )
    view = SetupView(manager, guild, 5, None, None, 10, None)
    manager._setup_views[guild.id] = view
    open_interaction = make_interaction(guild)

    await button(view, "Create category").callback(open_interaction)
    modal = open_interaction.response.send_modal.call_args.args[0]
    assert isinstance(modal, NewCategoryModal)
    modal.name._value = "Study rooms"
    await modal.on_submit(make_interaction(guild))

    assert view.new_category_name == "Study rooms"
    guild.create_category.assert_not_awaited()
    manager.bot.db.save_setup.assert_not_awaited()

    await button(view, "Save").callback(make_interaction(guild))

    guild.create_category.assert_awaited_once_with("Study rooms", reason=ANY)
    assert [call.args[0] for call in guild.create_text_channel.await_args_list] == ["cpo-commands", "cpo-logs"]
    manager.bot.db.save_setup.assert_awaited_once_with(
        1,
        40,
        21,
        10,
        31,
        default_group_duration=86400,
        default_pomodoro_duration=86400,
        default_vc_id=50,
        journal_operation_id=ANY,
        default_role_id=None,
        update_default_role=True,
    )
    assert view.new_category_name is None


@pytest.mark.asyncio
async def test_new_category_modal_rejects_empty_name_privately():
    manager, guild, _, _ = make_setup()
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    modal = NewCategoryModal(view)
    modal.name._value = "   "
    interaction = make_interaction(guild)

    await modal.on_submit(interaction)

    interaction.response.send_message.assert_awaited_once_with("Enter a category name.", ephemeral=True)
    assert view.new_category_name is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "level", [PermissionLevel.REGULAR_USER, PermissionLevel.GROUP_MEMBER, PermissionLevel.GROUP_OWNER]
)
async def test_revoked_setup_permission_blocks_callback(level):
    manager, guild, _, _ = make_setup()
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    setattr(manager, "get_permission_level", AsyncMock(return_value=level))
    interaction = make_interaction(guild)

    assert await view.interaction_check(interaction) is False
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True
    manager.bot.db.save_setup.assert_not_awaited()


@pytest.mark.asyncio
async def test_category_permission_denial_does_not_save_or_create_channels():
    manager, guild, category, _ = make_setup()
    category.permissions_for.return_value.manage_channels = False
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    interaction = make_interaction(guild)

    await button(view, "Save").callback(interaction)

    manager.bot.db.save_setup.assert_not_awaited()
    guild.create_text_channel.assert_not_awaited()
    assert interaction.followup.send.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_setup_timeout_does_not_change_settings():
    manager, guild, _, _ = make_setup()
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view
    view.message = AsyncMock()

    await view.on_timeout()

    manager.bot.db.save_setup.assert_not_awaited()
    assert guild.id not in manager._setup_views
    assert all(item.disabled for item in view.children)


@pytest.mark.asyncio
async def test_new_setup_session_invalidates_older_wizard():
    manager, guild, _, _ = make_setup()
    first = make_interaction(guild)
    second = make_interaction(guild)

    await Manager.setup.callback(manager, first)
    older = manager._setup_views[guild.id]
    await Manager.setup.callback(manager, second)
    assert manager._setup_views[guild.id] is not older

    await button(older, "Save").callback(make_interaction(guild))

    manager.bot.db.save_setup.assert_not_awaited()


@pytest.mark.asyncio
async def test_setup_with_default_vc_parameter():
    manager, guild, _, _ = make_setup()
    voice = MagicMock(spec=discord.VoiceChannel, id=77, guild=guild)
    interaction = make_interaction(guild)

    await Manager.setup.callback(manager, interaction, default_vc=voice)

    view = manager._setup_views[guild.id]
    assert view.default_vc_id == 77


@pytest.mark.asyncio
async def test_setup_rejects_foreign_default_vc():
    manager, guild, _, _ = make_setup()
    foreign_guild = MagicMock(id=99)
    foreign_voice = MagicMock(spec=discord.VoiceChannel, id=88, guild=foreign_guild)
    interaction = make_interaction(guild)

    await Manager.setup.callback(manager, interaction, default_vc=foreign_voice)

    assert guild.id not in manager._setup_views
    assert "Choose a voice channel in this server." in interaction.followup.send.call_args.args[0]


@pytest.mark.asyncio
async def test_setup_voice_select_stages_default_vc_and_renders_move_notice():
    manager, guild, _, _ = make_setup()
    other_voice = MagicMock(spec=discord.VoiceChannel, id=88, category_id=99, guild=guild)
    guild.get_channel.side_effect = lambda identifier: {88: other_voice}.get(identifier)
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    voice_select = next(item for item in view.children if isinstance(item, VoiceSelect))

    voice_select._values = [MagicMock(id=88)]
    interaction = make_interaction(guild)
    interaction.response.edit_message = AsyncMock()

    await voice_select.callback(interaction)

    assert view.default_vc_id == 88
    interaction.response.edit_message.assert_awaited_once()
    embed = interaction.response.edit_message.call_args.kwargs["embed"]
    assert any(field.name == "Default VC move" for field in embed.fields)


@pytest.mark.asyncio
async def test_setup_save_requires_bot_voice_permissions():
    manager, guild, _, _ = make_setup()
    manager.bot.db.get_default_vc.return_value = 50
    voice = guild.get_channel(50)
    voice_perms = MagicMock()
    voice_perms.view_channel = True
    voice_perms.connect = False
    voice_perms.move_members = True
    voice.permissions_for.return_value = voice_perms

    view = SetupView(manager, guild, 5, 10, 20, 10, 30, default_vc_id=50)
    manager._setup_views[guild.id] = view
    interaction = make_interaction(guild)

    await button(view, "Save").callback(interaction)

    manager.bot.db.save_setup.assert_not_awaited()
    assert "Connect, and Move Members permissions" in interaction.followup.send.call_args.args[0]


@pytest.mark.asyncio
async def test_setup_recover_button_cleans_created_and_reverts_moved():
    manager, guild, _, _ = make_setup()
    manager.bot.db.get_study_group_by_channel.return_value = None

    cat = MagicMock(spec=discord.CategoryChannel, id=100, guild=guild)
    cat.channels = []
    cat.delete = AsyncMock()

    cmd = MagicMock(spec=discord.TextChannel, id=101, guild=guild)
    cmd.delete = AsyncMock()

    log_ch = MagicMock(spec=discord.TextChannel, id=102, guild=guild)
    log_ch.delete = AsyncMock()

    vc = MagicMock(spec=discord.VoiceChannel, id=103, guild=guild)
    vc.delete = AsyncMock()

    old_cat = MagicMock(spec=discord.CategoryChannel, id=99, guild=guild)
    moved_cmd = MagicMock(spec=discord.TextChannel, id=20, category_id=100, guild=guild)
    moved_cmd.edit = AsyncMock()

    channels_map = {100: cat, 101: cmd, 102: log_ch, 103: vc, 99: old_cat, 20: moved_cmd}
    guild.get_channel.side_effect = lambda cid: channels_map.get(cid)

    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    manager._setup_views[guild.id] = view

    view.created_category_id = 100
    view.created_channel_id = 101
    view.created_log_channel_id = 102
    view.created_vc_id = 103
    view.moved_channel_id = 20
    view.previous_category_id = 99
    view.previous_channel_overwrites = {}

    assert view.has_pending_resources() is True

    interaction = make_interaction(guild, user_id=5)
    await button(view, "Recover").callback(interaction)

    cmd.delete.assert_awaited_once()
    log_ch.delete.assert_awaited_once()
    vc.delete.assert_awaited_once()
    cat.delete.assert_awaited_once()
    moved_cmd.edit.assert_awaited_once_with(category=old_cat, overwrites={}, reason="CPO setup rollback")

    assert view.has_pending_resources() is False
    assert view.created_category_id is None
    assert view.created_channel_id is None
    assert view.created_log_channel_id is None
    assert view.created_vc_id is None
    assert view.moved_channel_id is None
    assert view.previous_category_id is None

    interaction.followup.send.assert_awaited_once()
    report = interaction.followup.send.call_args.args[0]
    assert "Deleted 4 uncommitted resource(s)" in report
    assert "Restored 1 moved channel(s)" in report


@pytest.mark.asyncio
async def test_setup_recover_skips_resources_matching_active_db_settings():
    manager, guild, _, _ = make_setup()
    manager.bot.db.get_study_group_by_channel.return_value = None

    manager.bot.db.get_commands_channel.return_value = 101
    manager.bot.db.get_group_category.return_value = 100

    cat = MagicMock(spec=discord.CategoryChannel, id=100, guild=guild)
    cat.channels = []
    cat.delete = AsyncMock()

    cmd = MagicMock(spec=discord.TextChannel, id=101, guild=guild)
    cmd.delete = AsyncMock()

    guild.get_channel.side_effect = lambda cid: {100: cat, 101: cmd}.get(cid)

    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    view.created_category_id = 100
    view.created_channel_id = 101

    results = await view.recover_retained_resources()

    cat.delete.assert_not_awaited()
    cmd.delete.assert_not_awaited()
    assert 100 in results["skipped"]
    assert 101 in results["skipped"]
    assert results["deleted"] == []


@pytest.mark.asyncio
async def test_setup_recover_skips_category_with_remaining_channels():
    manager, guild, _, _ = make_setup()
    manager.bot.db.get_study_group_by_channel.return_value = None

    cat = MagicMock(spec=discord.CategoryChannel, id=100, guild=guild)
    other_channel = MagicMock(spec=discord.TextChannel, id=999)
    cat.channels = [other_channel]
    cat.delete = AsyncMock()

    guild.get_channel.side_effect = lambda cid: {100: cat}.get(cid)

    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    view.created_category_id = 100

    results = await view.recover_retained_resources()

    cat.delete.assert_not_awaited()
    assert 100 in results["skipped"]


@pytest.mark.asyncio
async def test_setup_recover_skips_channel_in_active_study_group():
    manager, guild, _, _ = make_setup()
    manager.bot.db.get_study_group_by_channel.return_value = {"id": 1, "group_id": "grp1", "active": 1}

    cmd = MagicMock(spec=discord.TextChannel, id=101, guild=guild)
    cmd.delete = AsyncMock()

    guild.get_channel.side_effect = lambda cid: {101: cmd}.get(cid)

    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    view.created_channel_id = 101

    results = await view.recover_retained_resources()

    cmd.delete.assert_not_awaited()
    assert 101 in results["skipped"]


@pytest.mark.asyncio
async def test_setup_recover_rejects_unauthorized_user():
    manager, guild, _, _ = make_setup()
    manager.get_permission_level.return_value = PermissionLevel.REGULAR_USER

    cmd = MagicMock(spec=discord.TextChannel, id=101, guild=guild)
    cmd.delete = AsyncMock()
    guild.get_channel.side_effect = lambda cid: {101: cmd}.get(cid)

    view = SetupView(manager, guild, owner_id=5, category_id=10, commands_channel_id=20, max_members=10)
    view.created_channel_id = 101

    interaction = make_interaction(guild, user_id=999)
    results = await view.recover_retained_resources(interaction=interaction)

    assert results["success"] is False
    assert results["error"] == "unauthorized"
    cmd.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_setup_superseded_session_recovers_uncommitted_resources():
    manager, guild, _, _ = make_setup()
    manager.bot.db.get_study_group_by_channel.return_value = None

    cmd = MagicMock(spec=discord.TextChannel, id=101, guild=guild)
    cmd.delete = AsyncMock()
    guild.get_channel.side_effect = lambda cid: {101: cmd, 10: MagicMock(spec=discord.CategoryChannel, id=10)}.get(cid)

    first_interaction = make_interaction(guild)
    await Manager.setup.callback(manager, first_interaction)
    first_view = manager._setup_views[guild.id]
    first_view.created_channel_id = 101

    second_interaction = make_interaction(guild)
    await Manager.setup.callback(manager, second_interaction)

    cmd.delete.assert_awaited_once()
    assert first_view.created_channel_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["settings", "group", "delete", "authority", "guild"])
async def test_setup_recovery_retains_handles_on_lookup_or_delete_failure(failure):
    import sqlite3

    manager, guild, _, channel = make_setup()
    channel.guild = guild
    channel.delete = AsyncMock()
    manager.bot.db.get_study_group_by_channel.return_value = None
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    view.created_channel_id = 20
    manager.bot.db.get_commands_channel.return_value = None
    actor = make_interaction(guild)
    if failure == "settings":
        manager.bot.db.get_group_category.side_effect = sqlite3.OperationalError("busy")
    elif failure == "group":
        manager.bot.db.get_study_group_by_channel.side_effect = sqlite3.OperationalError("busy")
    elif failure == "delete":
        channel.delete.side_effect = discord.Forbidden(MagicMock(status=403), "denied")
    elif failure == "authority":
        manager.get_permission_level.return_value = 0
    else:
        actor.guild_id = 2
    await view.recover_retained_resources(actor)
    assert view.created_channel_id == 20
    if failure != "delete":
        channel.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_setup_recovery_restores_exact_acl_in_same_category():
    manager, guild, _, channel = make_setup()
    channel.guild = guild
    view = SetupView(manager, guild, 5, 10, 20, 10, 30)
    view.moved_channel_id = 20
    view.previous_category_id = 10
    original = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    view.previous_channel_overwrites = original
    await view.recover_retained_resources(make_interaction(guild))
    channel.edit.assert_awaited_once_with(
        category=guild.get_channel(10), overwrites=original, reason="CPO setup rollback"
    )
    assert view.moved_channel_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("closed_by", ["cancel", "timeout"])
async def test_closed_setup_recovers_after_failed_setup_retry(closed_by):
    manager, guild, category, channel = make_setup()
    retained = MagicMock(spec=discord.TextChannel, id=101, guild=guild)
    retained.delete = AsyncMock()
    guild.get_channel.side_effect = lambda identifier: {10: category, 20: channel, 101: retained}.get(identifier)
    manager.bot.db.get_study_group_by_channel.return_value = None
    await Manager.setup.callback(manager, make_interaction(guild))
    prior = manager._setup_views[guild.id]
    prior.created_channel_id = retained.id
    if closed_by == "cancel":
        await button(prior, "Cancel").callback(make_interaction(guild))
    else:
        await prior.on_timeout()
    assert all(getattr(item, "disabled", False) for item in prior.children)

    manager.bot.db.get_study_group_by_channel.side_effect = sqlite3.OperationalError("busy")
    failed = make_interaction(guild)
    await Manager.setup.callback(manager, failed)
    assert manager._setup_views[guild.id] is prior
    assert prior.created_channel_id == retained.id
    retained.delete.assert_not_awaited()
    assert "Run /setup again" in failed.followup.send.call_args.args[0]
    assert failed.followup.send.call_args.kwargs["ephemeral"] is True

    manager.bot.db.get_study_group_by_channel.side_effect = None
    await Manager.setup.callback(manager, make_interaction(guild))
    retained.delete.assert_awaited_once()
    assert prior.created_channel_id is None
    assert manager._setup_views[guild.id] is not prior
    manager._setup_views[guild.id].stop()
