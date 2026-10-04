import asyncio
import logging
from collections.abc import Awaitable, Callable

import discord

from utils import acknowledge_interaction, send_response

logger = logging.getLogger(__name__)


class EndRequestView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        label: str,
        is_active: Callable[[], bool],
        on_confirm: Callable[[discord.Interaction], Awaitable[None]],
    ):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.label = label
        self.is_active = is_active
        self.on_confirm = on_confirm
        self.decided = False
        self.lock = asyncio.Lock()
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Only the session owner can answer this request.", ephemeral=True)
        return False

    async def close(self, content: str) -> None:
        self.decided = True
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        self.stop()
        if self.message:
            try:
                await self.message.edit(content=content, view=self)
            except discord.HTTPException:
                logger.exception("Could not close end request owner_id=%s", self.owner_id)

    @discord.ui.button(label="End session", style=discord.ButtonStyle.danger)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await acknowledge_interaction(interaction)
        async with self.lock:
            if interaction.user.id != self.owner_id:
                await send_response(interaction, "Only the session owner can answer this request.")
                return
            if self.decided or self.is_finished() or not self.is_active():
                await send_response(interaction, "This request is no longer active.")
                return
            await self.close(f"End request approved for {self.label}.")
            await self.on_confirm(interaction)

    @discord.ui.button(label="Keep running", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await acknowledge_interaction(interaction)
        async with self.lock:
            if interaction.user.id != self.owner_id:
                await send_response(interaction, "Only the session owner can answer this request.")
                return
            if self.decided or self.is_finished():
                await send_response(interaction, "This request has already been answered.")
                return
            await self.close(f"{self.label} will keep running.")
            await send_response(interaction, "The session will keep running.")

    async def on_timeout(self):
        async with self.lock:
            if not self.decided:
                await self.close("This end request expired. The session was not ended.")


async def request_session_end(
    interaction: discord.Interaction,
    owner_id: int,
    label: str,
    is_active: Callable[[], bool],
    on_confirm: Callable[[discord.Interaction], Awaitable[None]],
) -> None:
    if not interaction.response.is_done():
        await acknowledge_interaction(interaction)
    guild = interaction.guild
    if guild is None or not is_active():
        await send_response(interaction, "This session is no longer active.")
        return
    try:
        owner = guild.get_member(owner_id) or await guild.fetch_member(owner_id)
        view = EndRequestView(owner_id, label, is_active, on_confirm)
        view.message = await owner.send(
            f"{interaction.user.display_name} would like to end **{label}**. Do you want to end it?",
            view=view,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.HTTPException:
        logger.exception("Could not send end request guild_id=%s owner_id=%s", guild.id, owner_id)
        await send_response(interaction, "I couldn't message the owner. The session will keep running.")
        return
    await send_response(interaction, "I asked the session owner. It will keep running unless they approve.")
