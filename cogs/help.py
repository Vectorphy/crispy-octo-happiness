import discord
from discord import app_commands
from discord.ext import commands

from utils import send_response


class Help(commands.Cog):
    def __init__(self, bot=None):
        self.bot = bot

    @app_commands.command(name="help", description="Learn how to use study groups, timers, and tasks")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        manager = self.bot.get_cog("Manager") if self.bot else None
        level = await manager.get_permission_level(interaction.guild_id, interaction.user.id) if manager else 0
        embed = discord.Embed(
            title="How to use CPO",
            description="Type `/` and choose a command. Discord will show the details you can fill in.",
            color=discord.Color.blue(),
        )
        sections = (
            (
                "Set up your server",
                "A server moderator runs `/setup`, chooses or creates a category, and saves the bot commands and logs channels. Edit lifetimes to set how long new groups and Pomodoros run; both default to 24 hours.",
            ),
            (
                "Start a study group",
                "Use `/create_group` and mention people you want to invite. They receive a private invitation and choose whether to join. Leave the name empty to use your name and a session number.",
            ),
            (
                "Join or leave",
                "Use `/join_group` or the Join button. Use `/leave_group` or Leave to leave a group. An invitation never joins a session for you.",
            ),
            (
                "Focus and breaks",
                "In your group, use `/start_pomodoro`. Each focus and break stage must be from 2 minutes to 4 hours. Group members receive Join/Decline invitations. Entering voice alone does not join you. Use `/pause_pomodoro` and `/resume_pomodoro` to pause and continue. Choose Renew with an hour left to add 24 hours; pausing does not extend the lifetime.",
            ),
            (
                "Check in together",
                "Use `/checkin` with a name and reminder interval, such as `30m` or `2h`. Intervals must be from 2 minutes to 4 hours. Use Present, Break, or Leave on the session message.",
            ),
            (
                "Keep a task list",
                "Use `/task_add` to add a task, `/task_list` to see it, and `/task_complete` or `/task_delete` to finish or remove it. Tasks in a group stay with that group.",
            ),
            (
                "End a session",
                "The session owner or a server moderator can end it. If a member asks to end it, the owner receives a private request and decides. Server moderators can use `/purge_groups` to end all groups.",
            ),
            (
                "Who sees your replies?",
                "Normal replies are visible in study-group channels and the bot commands channel. Replies elsewhere, this help message, errors, and private task menus are visible only to you to avoid cluttering the server. Report malicious or unintended bot behavior to server staff immediately.",
            ),
        )
        for title, description in sections:
            if title == "Set up your server" and level < 3:
                continue
            if title == "End a session" and level < 3:
                description = "The session owner or server staff can end it. A participating member can ask to end it; the owner receives a private approval request and decides."
            embed.add_field(name=title, value=description, inline=False)
        if level >= 3:
            embed.add_field(
                name="Staff commands",
                value="`/setup`: configure channels and defaults. `/settings_checkin`: configure check-ins. `/purge_groups`: end server groups. `/list_managers`: view staff. `/add_guild_manager`, `/remove_guild_manager`: manage grants. `/sync_managers`: import native staff. `/sync_commands`: refresh slash commands. `/set_mod_log_channel`: configure logs. `/set_group_category`: choose group placement.",
                inline=False,
            )
            embed.add_field(
                name="Bot developer commands",
                value="`/add_bot_developer`: grant global developer access. `/set_permission_level`: remove a server grant or grant Manager/Developer. These operations require Level 4.",
                inline=False,
            )
        await send_response(interaction, embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))
