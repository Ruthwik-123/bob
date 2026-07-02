from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass

import discord
from discord.ext import commands

from .base import EconomyBase


@dataclass
class JobTask:
    title: str
    prompt: str
    answer: str


class WorkSelect(discord.ui.Select):
    def __init__(self, cog: "Work", ctx: commands.Context, jobs: dict[str, dict]) -> None:
        self.cog = cog
        self.ctx = ctx
        options = [
            discord.SelectOption(label=job["label"], description=job["description"][:100], value=key)
            for key, job in jobs.items()
        ]
        super().__init__(placeholder="Choose a job...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This work menu is not yours.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        for item in self.view.children:  # type: ignore[union-attr]
            item.disabled = True
        await interaction.message.edit(view=self.view)  # type: ignore[union-attr]
        await self.cog.start_private_job(self.ctx, interaction, self.values[0])


class WorkView(discord.ui.View):
    def __init__(self, cog: "Work", ctx: commands.Context, jobs: dict[str, dict], timeout: int) -> None:
        super().__init__(timeout=timeout)
        self.add_item(WorkSelect(cog, ctx, jobs))


class Work(EconomyBase):
    @commands.hybrid_command(name="work", description="Choose a job and complete a private minigame for coins.")
    async def work(self, ctx: commands.Context) -> None:
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            await self.send(ctx, "Work can only be used in a server.")
            return

        jobs = self.available_jobs(ctx.author)
        if not jobs:
            await self.send(ctx, "No jobs are currently available for your account age/roles.")
            return

        view = WorkView(self, ctx, jobs, self.cfg["work"]["selection_timeout_seconds"])
        await ctx.reply(f"{self.emoji('briefcase_emoji')} Choose a job from the dropdown. A private job channel will be created for your task.", view=view, mention_author=False)

    def available_jobs(self, member: discord.Member) -> dict[str, dict]:
        jobs = self.cfg["work"]["jobs"]
        available: dict[str, dict] = {}
        account_age_days = (self.now() - member.created_at).days
        member_roles = {role.name for role in member.roles}
        for key, job in jobs.items():
            if account_age_days < int(job.get("min_account_age_days", 0)):
                continue
            required = set(job.get("required_role_names", []))
            if required and not required.issubset(member_roles):
                continue
            available[key] = job
        return available

    async def get_or_create_jobs_category(self, guild: discord.Guild) -> discord.CategoryChannel | None:
        work_cfg = self.cfg["work"]
        category_name = work_cfg["jobs_category_name"]
        category = discord.utils.get(guild.categories, name=category_name)
        if category or not work_cfg.get("create_category_if_missing", True):
            return category
        return await guild.create_category(category_name, reason="Economy work system setup")

    async def start_private_job(self, ctx: commands.Context, interaction: discord.Interaction, job_key: str) -> None:
        guild = ctx.guild
        member = ctx.author
        if not guild or not isinstance(member, discord.Member):
            return

        job_cfg = self.cfg["work"]["jobs"][job_key]
        category = await self.get_or_create_jobs_category(guild)
        if not category:
            await interaction.followup.send("Could not find the JOBS category and auto-create is disabled.", ephemeral=True)
            return

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True)
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        safe_name = re.sub(r"[^a-z0-9-]", "-", member.display_name.lower())[:20].strip("-") or str(member.id)
        channel = await guild.create_text_channel(
            name=f"job-{safe_name}",
            category=category,
            overwrites=overwrites,
            reason=f"Temporary economy job for {member}",
        )
        await interaction.followup.send(f"Your private job channel is ready: {channel.mention}", ephemeral=True)
        await self.run_job_task(ctx, channel, job_key, job_cfg)

    def make_task(self, job_key: str) -> JobTask:
        if job_key == "data_entry":
            items = random.sample(["apricot", "falcon", "ember", "harbor", "binary", "citadel", "dynamo", "galaxy", "lantern"], 7)
            scrambled = items[:]
            random.shuffle(scrambled)
            answer = ", ".join(sorted(items))
            return JobTask("Data Entry", f"Sort these items alphabetically and send them comma-separated:\n`{', '.join(scrambled)}`", answer)

        if job_key == "quality_control":
            words = ["supply", "invoice", "package", "manifest", "delivery", "warehouse", "dispatch"]
            typo = random.choice(words)
            typo_word = typo[:-1] + "x"
            shown = [typo_word if word == typo else word for word in words]
            random.shuffle(shown)
            return JobTask("Quality Control", f"Find the typo/odd word in this block and send only that word:\n`{'  '.join(shown)}`", typo_word)

        pairs = {
            "salmon": "food",
            "helmet": "safety",
            "router": "tech",
            "forklift": "equipment",
            "rice": "food",
            "firewall": "tech",
        }
        items = random.sample(list(pairs.keys()), 4)
        answer = ", ".join(f"{item}:{pairs[item]}" for item in sorted(items))
        return JobTask(
            "Logistics",
            "Match each item to its category. Categories: food, safety, tech, equipment.\n"
            f"Items: `{', '.join(items)}`\n"
            "Reply in alphabetical item order like `item:category, item:category`.",
            answer,
        )

    @staticmethod
    def normalize_answer(value: str) -> str:
        return re.sub(r"\s+", " ", value.lower().strip())

    async def run_job_task(self, ctx: commands.Context, channel: discord.TextChannel, job_key: str, job_cfg: dict) -> None:
        task = self.make_task(job_key)
        timeout = self.cfg["work"]["task_timeout_seconds"]
        await channel.send(f"{self.emoji('briefcase_emoji')} **{task.title} Task** for {ctx.author.mention}\n{task.prompt}\n\nYou have **{timeout} seconds**.")

        def check(message: discord.Message) -> bool:
            return message.author.id == ctx.author.id and message.channel.id == channel.id

        success = False
        try:
            message = await self.bot.wait_for("message", check=check, timeout=timeout)
            success = self.normalize_answer(message.content) == self.normalize_answer(task.answer)
        except asyncio.TimeoutError:
            message = None

        if success:
            reward = random.randint(job_cfg["min_reward"], job_cfg["max_reward"])
            async with self._lock:
                data, _, account = await self.get_data_account(ctx)
                account["wallet"] += reward
                self.save(data)
                self.log_transaction(ctx, "work", reward, account, job_key)
            await channel.send(f"{self.emoji('success_emoji')} Correct! You earned {self.money(reward)}. This channel will delete soon.")
        else:
            answer = task.answer
            await channel.send(f"{self.emoji('failure_emoji')} Job failed. Correct answer was: `{answer}`. This channel will delete soon.")

        await asyncio.sleep(self.cfg["work"]["delete_channel_after_seconds"])
        try:
            await channel.delete(reason="Temporary economy job complete")
        except discord.HTTPException:
            pass
