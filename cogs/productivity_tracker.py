import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils import ProductivityService, acknowledge_interaction, send_response, should_use_ephemeral

logger = logging.getLogger(__name__)


class ProductivityTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.productivity_service = ProductivityService(bot.db)
        logger.info("ProductivityTracker cog initialized")

    @app_commands.command(name="productivity", description="Display your productivity metrics")
    async def productivity(self, interaction: discord.Interaction):
        await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        user_id = interaction.user.id
        metrics = await self.productivity_service.get_productivity_metrics(user_id, interaction.guild_id)

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Productivity Metrics",
            color=discord.Color.green(),
        )
        embed.add_field(name="Tasks Completed", value=str(metrics["tasks_completed"]), inline=False)
        embed.add_field(
            name="Attended Focus Time (hours)",
            value=f"{metrics['time_spent']:.4f}".rstrip("0").rstrip("."),
            inline=False,
        )
        embed.add_field(
            name="Efficiency Score (tasks/hour)",
            value=str(metrics["efficiency_score"]),
            inline=False,
        )

        await send_response(interaction, embed=embed, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(ProductivityTracker(bot))
    logger.info("Loaded ProductivityTracker cog")
