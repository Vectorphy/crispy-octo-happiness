from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from cogs._voice_relocation import relocate_to_default_vc
from database import DBHandler


def relocation_fixture():
    guild = MagicMock(spec=discord.Guild, id=1)
    destination = MagicMock(spec=discord.VoiceChannel, id=50, guild=guild, user_limit=0)
    destination.members = []
    destination.permissions_for.return_value = discord.Permissions(connect=True, move_members=True)
    guild.get_channel.return_value = destination
    member = MagicMock(spec=discord.Member, id=5, guild=guild)
    member.voice = MagicMock(channel=MagicMock(id=40))
    member.voice.channel.permissions_for.return_value = discord.Permissions(move_members=True)
    member.send = AsyncMock()
    member.move_to = AsyncMock()
    db = AsyncMock()
    db.get_default_vc.return_value = 50
    return member, db, destination


@pytest.mark.asyncio
async def test_relocation_moves_to_saved_destination():
    member, db, destination = relocation_fixture()
    assert await relocate_to_default_vc(member, db, 40, "group")
    member.move_to.assert_awaited_once_with(destination, reason="Video required in study group group")
    member.send.assert_awaited_once()
    assert "moved to" in member.send.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "foreign", "full", "connect", "move", "source_move", "http"])
async def test_relocation_failures_leave_member_connected_and_notify(failure):
    member, db, destination = relocation_fixture()
    if failure == "missing":
        member.guild.get_channel.return_value = None
    elif failure == "foreign":
        destination.guild = MagicMock(id=2)
    elif failure == "full":
        destination.user_limit = 1
        destination.members = [MagicMock()]
    elif failure in ("connect", "move"):
        destination.permissions_for.return_value = discord.Permissions(
            connect=failure != "connect", move_members=failure != "move"
        )
    elif failure == "source_move":
        member.voice.channel.permissions_for.return_value = discord.Permissions.none()
    else:
        member.move_to.side_effect = discord.Forbidden(MagicMock(status=403), "Denied")
    assert not await relocate_to_default_vc(member, db, 40, "group")
    if failure != "http":
        member.move_to.assert_not_awaited()
    assert not any(call.args[0] is None for call in member.move_to.await_args_list)
    member.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_relocation_does_not_move_a_member_who_left_the_source():
    member, db, _ = relocation_fixture()
    member.voice.channel.id = 99
    assert not await relocate_to_default_vc(member, db, 40, "group")
    member.move_to.assert_not_awaited()


@pytest.mark.asyncio
async def test_default_vc_survives_repeat_migration_and_omitted_setting(tmp_path):
    path = str(tmp_path / "settings.sqlite")
    db = DBHandler(path)
    await db.connect()
    await db.save_setup(1, 10, 20, 10, default_vc_id=50)
    await db.save_setup(1, 10, 20, 12)
    assert await db.get_default_vc(1) == 50
    assert await db.get_default_vc(2) is None
    await db.close()
    restarted = DBHandler(path)
    try:
        await restarted.connect()
        assert await restarted.get_default_vc(1) == 50
    finally:
        await restarted.close()
