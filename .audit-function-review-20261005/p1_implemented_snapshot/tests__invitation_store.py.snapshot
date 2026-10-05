"""Explicit invitation persistence fixture for command tests using mocked databases."""

from unittest.mock import AsyncMock


def configure_invitations(db):
    rows = {}

    async def create(identifier, guild_id, kind, session_id, recipient_id, owner_id, created_at):
        rows[identifier] = {
            "invitation_id": identifier,
            "guild_id": guild_id,
            "session_kind": kind,
            "session_id": session_id,
            "recipient_id": recipient_id,
            "owner_id": owner_id,
            "created_at": created_at,
            "warn_at": created_at + 360,
            "expires_at": created_at + 600,
            "status": "pending",
            "warned": 0,
            "expiry_notified": 0,
            "dm_channel_id": None,
            "dm_message_id": None,
        }
        return dict(rows[identifier])

    async def get(guild_id, identifier):
        row = rows.get(identifier)
        return dict(row) if row and row["guild_id"] == guild_id else None

    async def transition(guild_id, identifier, expected, desired, *, now):
        row = rows.get(identifier)
        if not row or row["guild_id"] != guild_id or row["status"] != expected:
            return False
        if desired == "accepting" and now >= row["expires_at"]:
            return False
        row["status"] = desired
        return True

    db.create_session_invitation = AsyncMock(side_effect=create)
    db.get_session_invitation = AsyncMock(side_effect=get)
    db.transition_session_invitation = AsyncMock(side_effect=transition)
    db.get_default_role = AsyncMock(return_value=None)
    return rows
