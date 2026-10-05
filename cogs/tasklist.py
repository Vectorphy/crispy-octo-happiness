import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs._access_policy import AccessView
from utils import acknowledge_interaction, send_response, should_use_ephemeral

logger = logging.getLogger(__name__)


class TaskActionSelect(discord.ui.Select):
    def __init__(self, tasks, db, action):
        self.db = db
        self.action = action
        self.task_groups = {}
        options = []
        for t in tasks:
            task_id = str(t["id"])
            self.task_groups[task_id] = t.get("group_id")
            task_num = t.get("task_id_str") or t.get("task_number") or task_id
            desc = str(t["description"])
            group_name = str(t.get("group_name", "Global Task"))

            label = f"#{task_num} - {desc}"
            if len(label) > 100:
                label = label[:97] + "..."

            options.append(
                discord.SelectOption(
                    label=label,
                    description=f"Group: {group_name}"[:100],
                    value=str(task_id),
                )
            )
        super().__init__(
            placeholder=f"Select a task to {action}...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        task_id = self.values[0] if self.values else None
        if task_id is None or task_id not in self.task_groups:
            await send_response(interaction, "Choose a task from this menu.", ephemeral=True)
            return
        success = await self.db.apply_task_action(
            interaction.user.id, int(task_id), self.task_groups[task_id], self.action
        )
        if success:
            result = "marked as complete" if self.action == "complete" else "deleted"
            await interaction.edit_original_response(content=f"Task #{task_id} {result}.", view=None)
        else:
            await interaction.edit_original_response(
                content=f"Task #{task_id} could not be {self.action}d. Refresh your task list.", view=None
            )
        if self.view:
            self.view.stop()


class TaskActionView(AccessView):
    def __init__(self, tasks, db, user_id, action):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.add_item(TaskActionSelect(tasks, db, action))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("Only the task owner can use this menu.", ephemeral=True)
        return False


class TaskPaginationView(AccessView):
    def __init__(self, tasks: list, title: str):
        super().__init__(timeout=180)
        self.tasks = tasks
        self.title = title
        self.current_page = 0
        self.per_page = 15
        self.total_pages = (len(self.tasks) - 1) // self.per_page + 1

        self.update_buttons()

    def update_buttons(self):
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == self.total_pages - 1

    def get_embed(self):
        embed = discord.Embed(title=self.title, color=discord.Color.blue())

        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_tasks = self.tasks[start_idx:end_idx]

        lines = []
        for task in page_tasks:
            try:
                t_id = (
                    task["task_id_str"]
                    if ("task_id_str" in task.keys() and task["task_id_str"])
                    else (task["task_number"] if ("task_number" in task.keys() and task["task_number"]) else task["id"])
                )
                t_desc = task["description"]
                t_comp = bool(task["completed"])
            except (TypeError, IndexError, AttributeError):
                t_id = task[0]
                t_desc = task[2] if len(task) > 2 else "Task"
                t_comp = bool(task[3]) if len(task) > 3 else False

            status_icon = "✅" if t_comp else "⏳"
            status_text = "Completed" if t_comp else "In Progress"
            lines.append(f"{status_icon} **Task #{t_id}**: {t_desc} — *{status_text}*")

        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Page {self.current_page + 1} of {self.total_pages} | Total Tasks: {len(self.tasks)}")
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="prev_page")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)


class TaskList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("Tasklist cog initialized")

    @app_commands.command(
        name="task_add",
        description="Add a new task to your list (scoped to group if inside group channel)",
    )
    @app_commands.describe(description="The task description")
    async def add_task(self, interaction: discord.Interaction, *, description: str):
        await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        group_id = None
        group_name = None
        channel_id = getattr(interaction, "channel_id", None)
        if isinstance(channel_id, int):
            group = await self.bot.db.get_study_group_by_channel(channel_id)
            if group:
                group = dict(group)
                group_id = group.get("group_id") or str(group.get("id"))
                group_name = group.get("name")

        guild = getattr(interaction, "guild", None)
        guild_id = getattr(interaction, "guild_id", None) if guild is not None else None
        if not isinstance(guild_id, int) and guild is not None:
            guild_id = getattr(guild, "id", None)
        if not isinstance(guild_id, int):
            guild_id = None

        if group_id:
            task_id = await self.bot.db.add_task(interaction.user.id, description, group_id=group_id, guild_id=guild_id)
            await send_response(
                interaction,
                f"Task #{task_id} added successfully to **{group_name}**: {description}",
                ephemeral=ephemeral,
            )
        elif guild_id:
            task_id = await self.bot.db.add_task(interaction.user.id, description, guild_id=guild_id)
            await send_response(interaction, f"Task added successfully. Task ID: {task_id}", ephemeral=ephemeral)
        else:
            task_id = await self.bot.db.add_task(interaction.user.id, description)
            await send_response(interaction, f"Task added successfully. Task ID: {task_id}", ephemeral=ephemeral)

    @app_commands.command(name="task_complete", description="Mark a task as complete")
    @app_commands.describe(task_ids="The ID(s) or task number(s) to complete (comma-separated, optional if using UI)")
    async def complete_task(self, interaction: discord.Interaction, task_ids: Optional[str] = None):
        await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        if task_ids is not None:
            group_id = None
            channel_id = getattr(interaction, "channel_id", None)
            if isinstance(channel_id, int):
                group = await self.bot.db.get_study_group_by_channel(channel_id)
                if group:
                    group = dict(group)
                    group_id = group.get("group_id") or str(group.get("id"))

            completed_list = []
            failed_list = []
            for tid_str in [x.strip() for x in task_ids.split(",") if x.strip()]:
                tid = tid_str
                if group_id:
                    success = await self.bot.db.complete_task(interaction.user.id, tid, group_id=group_id)
                else:
                    success = await self.bot.db.complete_task(interaction.user.id, tid)

                if success:
                    completed_list.append(str(tid))
                else:
                    failed_list.append(str(tid))

            res = []
            if completed_list:
                res.append(f"Tasks marked as complete: {', '.join(completed_list)}")
            if failed_list:
                res.append(f"Failed to find or already completed: {', '.join(failed_list)}")

            if res:
                await send_response(interaction, "\n".join(res), ephemeral=True if failed_list else ephemeral)
            else:
                await send_response(interaction, "No valid tasks were provided.", ephemeral=True)
            return

        await self._send_task_menu(interaction, "complete")

    async def _send_task_menu(self, interaction, action):
        ephemeral = True
        group_id = None
        group_name = None
        channel_id = getattr(interaction, "channel_id", None)
        guild = getattr(interaction, "guild", None)
        guild_id = getattr(interaction, "guild_id", None) if guild is not None else None
        if not isinstance(guild_id, int) and guild is not None:
            guild_id = getattr(guild, "id", None)
        if not isinstance(guild_id, int):
            guild_id = None

        if isinstance(channel_id, int):
            group = await self.bot.db.get_study_group_by_channel(channel_id)
            if group:
                group_id = dict(group).get("group_id") or str(group["id"])
                group_name = dict(group).get("name", "Study group")
        if group_id:
            tasks = await self.bot.db.get_user_tasks(interaction.user.id, group_id=group_id)
        elif guild_id:
            tasks = await self.bot.db.get_user_tasks(interaction.user.id, global_only=True, guild_id=guild_id)
        else:
            tasks = await self.bot.db.get_user_tasks(interaction.user.id, global_only=True)
        choices = [dict(task) for task in tasks if action == "delete" or not task["completed"]]
        for task in choices:
            task["group_name"] = group_name or ("Study group" if task.get("group_id") else "Server Task")
        if not choices:
            await send_response(interaction, f"You have no tasks to {action}.", ephemeral=ephemeral)
            return
        view = TaskActionView(choices[:25], self.bot.db, interaction.user.id, action)
        await send_response(interaction, f"Select a task to {action}:", view=view, ephemeral=ephemeral)

    @app_commands.command(name="task_list", description="List your current tasks")
    @app_commands.describe(all_groups="Show tasks across all groups (default False if inside a group)")
    async def list_tasks(self, interaction: discord.Interaction, all_groups: bool = False):
        if isinstance(all_groups, str):
            all_groups = all_groups.strip().lower() in {"true", "1", "yes", "on"}
        await acknowledge_interaction(interaction)
        ephemeral = True if all_groups else await should_use_ephemeral(interaction, self.bot.db)
        group_id = None
        group_name = None
        channel_id = getattr(interaction, "channel_id", None)
        if not all_groups and isinstance(channel_id, int):
            group = await self.bot.db.get_study_group_by_channel(channel_id)
            if group:
                group = dict(group)
                group_id = group.get("group_id") or str(group.get("id"))
                group_name = group.get("name")

        guild = getattr(interaction, "guild", None)
        guild_id = getattr(interaction, "guild_id", None) if guild is not None else None
        if not isinstance(guild_id, int) and guild is not None:
            guild_id = getattr(guild, "id", None)
        if not isinstance(guild_id, int):
            guild_id = None

        if all_groups:
            tasks = await self.bot.db.get_user_tasks(interaction.user.id)
            title = f"{interaction.user.display_name}'s Tasks — All Groups"
        elif group_id:
            tasks = await self.bot.db.get_user_tasks(interaction.user.id, group_id=group_id)
            title = f"{interaction.user.display_name}'s Tasks — {group_name}"
        elif guild_id:
            tasks = await self.bot.db.get_user_tasks(interaction.user.id, global_only=True, guild_id=guild_id)
            title = f"{interaction.user.display_name}'s Tasks"
        else:
            tasks = await self.bot.db.get_user_tasks(interaction.user.id, global_only=True)
            title = f"{interaction.user.display_name}'s Tasks"

        if not tasks:
            await send_response(interaction, "You have no tasks.", ephemeral=ephemeral)
            return

        view = TaskPaginationView(tasks, title)
        await send_response(interaction, embed=view.get_embed(), view=view, ephemeral=ephemeral)

    @app_commands.command(name="task_delete", description="Delete one or multiple tasks")
    @app_commands.describe(task_ids="The ID(s) to delete (comma-separated, optional if using the menu)")
    async def delete_task(self, interaction: discord.Interaction, task_ids: Optional[str] = None):
        await acknowledge_interaction(interaction)
        ephemeral = await should_use_ephemeral(interaction, self.bot.db)
        if task_ids is None:
            await self._send_task_menu(interaction, "delete")
            return
        group_id = None
        channel_id = getattr(interaction, "channel_id", None)
        if isinstance(channel_id, int):
            group = await self.bot.db.get_study_group_by_channel(channel_id)
            if group:
                group = dict(group)
                group_id = group.get("group_id") or str(group.get("id"))

        deleted_list = []
        failed_list = []
        for tid_str in [x.strip() for x in task_ids.split(",") if x.strip()]:
            tid = tid_str
            if group_id:
                success = await self.bot.db.delete_task(interaction.user.id, tid, group_id=group_id)
            else:
                success = await self.bot.db.delete_task(interaction.user.id, tid)

            if success:
                deleted_list.append(str(tid))
            else:
                failed_list.append(str(tid))

        res = []
        if deleted_list:
            res.append(f"Tasks deleted: {', '.join(deleted_list)}")
        if failed_list:
            res.append(f"Failed to find or delete: {', '.join(failed_list)}")

        if res:
            await send_response(interaction, "\n".join(res), ephemeral=True if failed_list else ephemeral)
        else:
            await send_response(interaction, "No valid tasks were provided.", ephemeral=True)

    @app_commands.command(
        name="task_purge",
        description="Purge all tasks for a specific group, or globally",
    )
    @app_commands.describe(all_tasks="⚠️ CAUTION: Set to True to purge ALL your tasks globally across ALL study groups")
    async def purge_tasks(self, interaction: discord.Interaction, all_tasks: bool = False):
        await acknowledge_interaction(interaction)
        ephemeral = True if all_tasks else await should_use_ephemeral(interaction, self.bot.db)
        if all_tasks:
            deleted_count = await self.bot.db.purge_all_user_tasks(interaction.user.id)
            cleanup = await self._purge_task_messages(interaction)
            await send_response(
                interaction,
                f"Purged {deleted_count} tasks globally across all your groups.{cleanup}",
                ephemeral=True if cleanup else ephemeral,
            )
            return

        group_id = None
        channel_id = getattr(interaction, "channel_id", None)
        if isinstance(channel_id, int):
            group = await self.bot.db.get_study_group_by_channel(channel_id)
            if group:
                group = dict(group)
                group_id = group.get("group_id") or str(group.get("id"))

        guild = getattr(interaction, "guild", None)
        guild_id = getattr(interaction, "guild_id", None) if guild is not None else None
        if not isinstance(guild_id, int) and guild is not None:
            guild_id = getattr(guild, "id", None)
        if not isinstance(guild_id, int):
            guild_id = None

        if group_id:
            count = await self.bot.db.purge_group_tasks(interaction.user.id, group_id)
            cleanup = await self._purge_task_messages(interaction)
            await send_response(
                interaction,
                f"Successfully purged {count} tasks from this group.{cleanup}",
                ephemeral=True if cleanup else ephemeral,
            )
        elif guild_id:
            count = await self.bot.db.purge_guild_tasks(interaction.user.id, guild_id)
            cleanup = await self._purge_task_messages(interaction)
            await send_response(
                interaction,
                f"Successfully purged {count} tasks from this server.{cleanup}",
                ephemeral=True if cleanup else ephemeral,
            )
        else:
            count = await self.bot.db.purge_personal_tasks(interaction.user.id)
            await send_response(interaction, f"Successfully purged {count} personal tasks.", ephemeral=True)

    async def _purge_task_messages(self, interaction):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or self.bot.user is None:
            return ""

        def is_owned_task_message(message):
            if message.author.id != self.bot.user.id:
                return False
            metadata = getattr(message, "interaction_metadata", None) or getattr(message, "interaction", None)
            if metadata is None or metadata.user.id != interaction.user.id:
                return False
            return message.content.startswith(
                ("Task added successfully", "Task #", "Tasks marked as complete", "Tasks deleted", "Select a task to")
            ) or any("'s Tasks" in (embed.title or "") for embed in message.embeds)

        try:
            await channel.purge(limit=100, check=is_owned_task_message)
        except discord.HTTPException:
            logger.exception(
                "Task message cleanup failed guild_id=%s user_id=%s channel_id=%s",
                interaction.guild_id,
                interaction.user.id,
                channel.id,
            )
            return " Task records were removed, but channel messages could not be cleaned up."
        return ""


async def setup(bot):
    await bot.add_cog(TaskList(bot))
    logger.info("Loaded TaskList cog")
