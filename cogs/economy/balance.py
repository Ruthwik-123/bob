import discord
from discord.ext import commands

from .base import EconomyBase
from .storage import load_data


class Balance(EconomyBase):
    @commands.hybrid_command(name="balance", description="Check your wallet and bank balance.")
    async def balance(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        async with self._lock:
            data = load_data()
            guild = self.get_guild(data, self.guild_key(ctx))
            account = self.get_account(guild, target)
            self.save(data)

        total = account["wallet"] + account["bank"]
        embed = discord.Embed(title=f"{target.display_name}'s Balance", color=discord.Color.gold())
        embed.add_field(name="Wallet", value=self.money(account["wallet"]), inline=True)
        embed.add_field(name="Bank", value=self.money(account["bank"]), inline=True)
        embed.add_field(name="Total", value=self.money(total), inline=False)
        await ctx.reply(embed=embed, mention_author=False)
