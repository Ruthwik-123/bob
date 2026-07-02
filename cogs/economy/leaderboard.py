import discord
from discord.ext import commands

from .base import EconomyBase
from .storage import load_data


class Leaderboard(EconomyBase):
    @commands.hybrid_command(name="leaderboard", description="Show the top richest users in this server by net worth.")
    async def leaderboard(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            await self.send(ctx, "The leaderboard can only be used in a server.")
            return

        async with self._lock:
            data = load_data()
            guild = self.get_guild(data, self.guild_key(ctx))
            self.ensure_stock(guild, update=True)
            users = guild.setdefault("users", {})
            for account in users.values():
                self.apply_overdue_loan(account)
            self.save(data)

        ranked = sorted(users.items(), key=lambda item: self.net_worth(guild, item[1]), reverse=True)[: self.cfg["leaderboard"]["limit"]]

        if not ranked:
            await self.send(ctx, "No accounts yet. Use `create_account` to join the economy.")
            return

        lines = []
        for index, (user_id, account) in enumerate(ranked, start=1):
            name = await self.resolve_display_name(ctx.guild, int(user_id))
            lines.append(f"**#{index}** {name} - {self.money(self.net_worth(guild, account))}")

        trophy = self.emoji("trophy_emoji")
        embed = discord.Embed(title=f"{trophy} Server Net Worth Leaderboard", description="\n".join(lines), color=discord.Color.gold())
        await ctx.reply(embed=embed, mention_author=False)
