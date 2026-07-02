import discord
from discord.ext import commands

from .base import EconomyBase
from .storage import load_data


class Account(EconomyBase):
    @commands.hybrid_command(name="account", description="View your economy profile, investments, and loans.")
    async def account(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        async with self._lock:
            data = load_data()
            guild = self.get_guild(data, self.guild_key(ctx))
            stock = self.ensure_stock(guild, update=True)
            account = self.get_account(guild, target)
            self.apply_overdue_loan(account)
            self.save(data)

        stock_key = self.cfg["stock_market"]["stock_key"]
        stock_name = self.cfg["stock_market"]["display_name"]
        inv = account["investments"][stock_key]
        investment_value = inv["shares"] * stock["price"]
        loan = account["loan"]
        net = self.net_worth(guild, account)

        embed = discord.Embed(title=f"{target.display_name}'s Economy Account", color=discord.Color.blurple())
        embed.add_field(name="Wallet", value=self.money(account["wallet"]), inline=True)
        embed.add_field(name="Bank", value=self.money(account["bank"]), inline=True)
        embed.add_field(name="Net Worth", value=self.money(net), inline=True)
        embed.add_field(
            name=f"{self.emoji('chart_up_emoji')} {stock_name} Investment",
            value=f"Shares: **{inv['shares']:,}**\nPrice: **{self.money(stock['price'])}**\nValue: **{self.money(investment_value)}**",
            inline=False,
        )
        if loan["remaining"] > 0:
            embed.add_field(
name=f"{self.emoji('bank_emoji')} Active Loan",
                value=(
                    f"Borrowed: **{self.money(loan['principal'])}**\n"
                    f"Remaining: **{self.money(loan['remaining'])}**\n"
                    f"Due: **{self.fmt_due(loan['due_at'])}**"
                ),
                inline=False,
            )
        else:
            embed.add_field(name=f"{self.emoji('bank_emoji')} Active Loan", value="None", inline=False)
        await ctx.reply(embed=embed, mention_author=False)
