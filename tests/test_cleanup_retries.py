from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from cogs.study_groups import StudyGroup, StudyGroupCog
from database import DBHandler


@pytest.fixture
async def in_memory_db():
    db = DBHandler(":memory:")
    await db.connect()
    yield db
    await db.close()


class TestDatabaseCleanupRetries:
    """Test DAL methods for pending resource cleanup retry tracking."""

    @pytest.mark.asyncio
    async def test_record_and_get_pending_cleanups(self, in_memory_db):
        cleanup_id = await in_memory_db.record_pending_cleanup(
            guild_id=123,
            group_id="group-uuid-1",
            resource_type="text_channel",
            resource_id=1001,
            last_error="Forbidden: 403 Missing Permissions",
        )
        assert cleanup_id > 0

        cleanups = await in_memory_db.get_pending_cleanups(guild_id=123)
        assert len(cleanups) == 1
        rec = cleanups[0]
        assert rec["id"] == cleanup_id
        assert rec["guild_id"] == 123
        assert rec["group_id"] == "group-uuid-1"
        assert rec["resource_type"] == "text_channel"
        assert rec["resource_id"] == 1001
        assert rec["retry_count"] == 0
        assert "403 Missing Permissions" in rec["last_error"]
        assert rec["status"] == "pending"

    @pytest.mark.asyncio
    async def test_record_pending_cleanup_deduplication(self, in_memory_db):
        id1 = await in_memory_db.record_pending_cleanup(
            guild_id=123,
            group_id="group-uuid-1",
            resource_type="voice_channel",
            resource_id=2002,
            last_error="First error",
        )
        # Record same resource again while still pending
        id2 = await in_memory_db.record_pending_cleanup(
            guild_id=123,
            group_id="group-uuid-1",
            resource_type="voice_channel",
            resource_id=2002,
            last_error="Updated error",
        )
        assert id1 == id2
        cleanups = await in_memory_db.get_pending_cleanups(guild_id=123)
        assert len(cleanups) == 1
        assert cleanups[0]["last_error"] == "Updated error"

    @pytest.mark.asyncio
    async def test_update_cleanup_retry_and_delete(self, in_memory_db):
        cleanup_id = await in_memory_db.record_pending_cleanup(
            guild_id=123,
            group_id="group-uuid-1",
            resource_type="role",
            resource_id=3003,
            last_error="Initial fail",
        )
        await in_memory_db.update_cleanup_retry(
            cleanup_id=cleanup_id,
            status="pending",
            last_error="Second attempt fail",
            increment_retry=True,
        )
        cleanups = await in_memory_db.get_pending_cleanups(guild_id=123)
        assert cleanups[0]["retry_count"] == 1
        assert cleanups[0]["last_error"] == "Second attempt fail"

        # Count helper
        count = await in_memory_db.get_pending_cleanup_count(guild_id=123)
        assert count == 1

        # Delete when resolved
        await in_memory_db.delete_pending_cleanup(cleanup_id)
        cleanups_after = await in_memory_db.get_pending_cleanups(guild_id=123)
        assert len(cleanups_after) == 0
        assert await in_memory_db.get_pending_cleanup_count(guild_id=123) == 0


class TestGroupCleanupLacksPermissions:
    """Test that failed resource deletions in StudyGroup.end_group are recorded."""

    @pytest.mark.asyncio
    async def test_end_group_records_failed_deletions(self, in_memory_db):
        bot = MagicMock()
        bot.db = in_memory_db
        bot.get_cog.return_value = None

        guild = MagicMock(spec=discord.Guild)
        guild.id = 555
        guild.members = []

        # Text channel that fails with Forbidden
        text_channel = MagicMock(spec=discord.TextChannel)
        text_channel.id = 1111
        text_channel.name = "study-text"
        text_channel.delete = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Missing manage_channels"))

        # Voice channel that fails with HTTPException
        vc = MagicMock(spec=discord.VoiceChannel)
        vc.id = 2222
        vc.name = "study-voice"
        vc.delete = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "Discord 500"))

        # Role that fails with Forbidden
        role = MagicMock(spec=discord.Role)
        role.id = 3333
        role.name = "study-role"
        role.delete = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Missing manage_roles"))

        def get_channel_mock(ch_id):
            if ch_id == 1111:
                return text_channel
            if ch_id == 2222:
                return vc
            return None

        guild.get_channel = MagicMock(side_effect=get_channel_mock)
        guild.get_role = MagicMock(return_value=role)

        cog = MagicMock()
        cog.bot = bot
        cog.log_mod_action = AsyncMock()

        group = StudyGroup(
            db=in_memory_db,
            cog=cog,
            guild_id=555,
            name="test-failing-cleanup-group",
            creator_id=99,
            category_id=0,
            max_members=5,
            member_ids=[99],
        )
        group.guild = guild
        group.text_id = 1111
        group.vc_id = 2222
        group.group_role_id = 3333
        group.active = True

        # Save to DB so delete_study_group has a row
        await in_memory_db.save_study_group(
            {
                "guild_id": 555,
                "name": "test-failing-cleanup-group",
                "group_id": group.group_id,
                "category_id": 0,
                "max_members": 5,
                "member_ids": [99],
                "creator_id": 99,
                "owner_id": 99,
                "group_role_id": 3333,
                "text_id": 1111,
                "vc_id": 2222,
                "info_embed_id": None,
                "start_time": "2026-10-04T00:00:00",
                "duration": 3600,
                "end_time": "2026-10-04T01:00:00",
                "speak_enabled": True,
                "video_mode": False,
                "video_timer": 0,
                "active": True,
            }
        )

        # Trigger end_group with delay=0
        await group.end_group(delete_text_channel=True, delay=0, actor_id=99)

        # Verify that all 3 failed resources were recorded in pending_resource_cleanups!
        pending = await in_memory_db.get_pending_cleanups(guild_id=555)
        assert len(pending) == 3
        types_recorded = {item["resource_type"] for item in pending}
        assert types_recorded == {"text_channel", "voice_channel", "role"}

        for item in pending:
            assert item["retry_count"] == 0
            assert item["status"] == "pending"


class TestProcessPendingCleanups:
    """Test retry processing in StudyGroupCog."""

    @pytest.mark.asyncio
    async def test_process_pending_cleanups_resolves_when_permission_granted(self, in_memory_db):
        bot = MagicMock()
        bot.db = in_memory_db

        guild = MagicMock(spec=discord.Guild)
        guild.id = 777

        # Channel now has manage_channels permission
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 4444
        channel.delete = AsyncMock()

        me = MagicMock(spec=discord.Member)
        me.top_role = MagicMock()
        perms = MagicMock()
        perms.manage_channels = True
        channel.permissions_for = MagicMock(return_value=perms)

        # Role now has manage_roles permission and top_role > role
        role = MagicMock(spec=discord.Role)
        role.id = 5555
        role.delete = AsyncMock()
        me.guild_permissions = MagicMock(manage_roles=True)
        me.top_role.__gt__ = MagicMock(return_value=True)
        me.top_role.__le__ = MagicMock(return_value=False)

        guild.me = me
        guild.get_channel = MagicMock(return_value=channel)
        guild.get_role = MagicMock(return_value=role)
        bot.get_guild = MagicMock(return_value=guild)

        # Pre-seed 2 pending cleanups
        await in_memory_db.record_pending_cleanup(777, "grp-1", "text_channel", 4444, "Old 403")
        await in_memory_db.record_pending_cleanup(777, "grp-1", "role", 5555, "Old 403")

        cog = StudyGroupCog(bot)
        summary = await cog.process_pending_cleanups(guild=guild)

        assert summary["resolved"] == 2
        assert summary["failed"] == 0

        # Verify channels and roles were deleted on Discord
        channel.delete.assert_called_once()
        role.delete.assert_called_once()

        # Database rows should be cleared
        remaining = await in_memory_db.get_pending_cleanups(guild_id=777)
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_process_pending_cleanups_handles_still_lacking_permission(self, in_memory_db):
        bot = MagicMock()
        bot.db = in_memory_db

        guild = MagicMock(spec=discord.Guild)
        guild.id = 888

        # Channel still lacks manage_channels
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 6666
        perms = MagicMock()
        perms.manage_channels = False
        channel.permissions_for = MagicMock(return_value=perms)

        me = MagicMock(spec=discord.Member)
        me.guild_permissions = MagicMock(manage_roles=False)
        guild.me = me
        guild.get_channel = MagicMock(return_value=channel)
        bot.get_guild = MagicMock(return_value=guild)

        await in_memory_db.record_pending_cleanup(888, "grp-2", "text_channel", 6666, "Old 403")

        cog = StudyGroupCog(bot)
        summary = await cog.process_pending_cleanups(guild=guild)

        assert summary["resolved"] == 0
        assert summary["failed"] == 1

        # Still pending, retry_count incremented
        cleanups = await in_memory_db.get_pending_cleanups(guild_id=888)
        assert len(cleanups) == 1
        assert cleanups[0]["retry_count"] == 1
        assert "manage_channels" in cleanups[0]["last_error"]

    @pytest.mark.asyncio
    async def test_process_pending_cleanups_resolves_already_deleted_resources(self, in_memory_db):
        bot = MagicMock()
        bot.db = in_memory_db

        guild = MagicMock(spec=discord.Guild)
        guild.id = 999
        guild.get_channel = MagicMock(return_value=None)
        guild.get_role = MagicMock(return_value=None)
        bot.get_guild = MagicMock(return_value=guild)
        bot.fetch_channel = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Channel 404"))

        await in_memory_db.record_pending_cleanup(999, "grp-3", "text_channel", 7777, "Old error")
        await in_memory_db.record_pending_cleanup(999, "grp-3", "role", 8888, "Old error")

        cog = StudyGroupCog(bot)
        summary = await cog.process_pending_cleanups(guild=guild)

        assert summary["resolved"] == 2
        assert summary["failed"] == 0

        # Both records cleared because resources no longer exist on Discord
        remaining = await in_memory_db.get_pending_cleanups(guild_id=999)
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_retry_cleanups_slash_command(self, in_memory_db):
        bot = MagicMock()
        bot.db = in_memory_db

        cog = StudyGroupCog(bot)
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.guild = MagicMock()
        interaction.guild.id = 123
        interaction.response = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=True)
        interaction.followup = AsyncMock()

        # Manager check passes
        with (
            patch("cogs.study_groups.check_manager", AsyncMock(return_value=True)),
            patch("cogs.study_groups.should_use_ephemeral", AsyncMock(return_value=True)),
            patch.object(cog, "process_pending_cleanups", AsyncMock(return_value={"resolved": 3, "failed": 1})),
        ):
            await cog.retry_cleanups.callback(cog, interaction)
            interaction.followup.send.assert_called_once()
            call_args = interaction.followup.send.call_args
            response_text = call_args[0][0]
            assert "Resolved / Deleted: 3" in response_text
            assert "Failed / Still lacking permissions: 1" in response_text
