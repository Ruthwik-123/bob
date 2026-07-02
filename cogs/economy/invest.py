from discord import app_commands
from discord.ext import commands

from .base import EconomyBase


class Invest(EconomyBase):
    @commands.hybrid_group(name="invest", description="View and trade the Folks stock market.", invoke_without_command=True)
    async def invest(self, ctx: commands.Context) -> None:
        async with self._lock:
            data, guild, account = await self.get_data_account(ctx)
            stock = self.ensure_stock(guild, update=True)
            self.save(data)

        stock_name = self.cfg["stock_market"]["display_name"]
        stock_key = self.cfg["stock_market"]["stock_key"]
        shares = account["investments"][stock_key]["shares"]
        change = stock.get("last_percent_change", 0.0)
        arrow = self.emoji("chart_up_emoji") if change >= 0 else self.emoji("chart_down_emoji")
        await self.send(
            ctx,
            f"{arrow} **{stock_name} Market**\n"
            f"Current price: **{self.money(stock['price'])}** per share ({change:+.2f}%).\n"
            f"You own **{shares:,}** share(s), worth **{self.money(shares * stock['price'])}**.\n"
            "Use `invest buy [shares]` or `invest sell [shares]`.",
        )

    @app_commands.describe(shares="Number of Folks shares to buy.")
    @invest.command(name="buy", description="Buy Folks shares using wallet balance.")
    async def buy(self, ctx: commands.Context, shares: int) -> None:
        if not self.validate_positive(shares):
            await self.send(ctx, "Shares must be greater than 0.")
            return

        async with self._lock:
            data, guild, account = await self.get_data_account(ctx)
            stock = self.ensure_stock(guild, update=True)
            stock_key = self.cfg["stock_market"]["stock_key"]
            inv = account["investments"][stock_key]
            cost = shares * stock["price"]

            if account["wallet"] < cost:
                await self.send(ctx, f"You need {self.money(cost)}, but only have {self.money(account['wallet'])} in your wallet.")
                return

            old_value = inv["shares"] * inv.get("average_price", 0)
            account["wallet"] -= cost
            inv["shares"] += shares
            inv["average_price"] = round((old_value + cost) / inv["shares"])
            self.save(data)
            self.log_transaction(ctx, "stock_buy", -cost, account, f"shares:{shares};price:{stock['price']}")

        await self.send(ctx, f"Bought **{shares:,}** Folks share(s) for {self.money(cost)} at {self.money(stock['price'])} each.")

    @app_commands.describe(shares="Number of Folks shares to sell.")
    @invest.command(name="sell", description="Sell Folks shares into wallet balance.")
    async def sell(self, ctx: commands.Context, shares: int) -> None:
        if not self.validate_positive(shares):
            await self.send(ctx, "Shares must be greater than 0.")
            return

        async with self._lock:
            data, guild, account = await self.get_data_account(ctx)
            stock = self.ensure_stock(guild, update=True)
            stock_key = self.cfg["stock_market"]["stock_key"]
            inv = account["investments"][stock_key]

            if inv["shares"] < shares:
                await self.send(ctx, f"You only own **{inv['shares']:,}** Folks share(s).")
                return

            revenue = shares * stock["price"]
            account["wallet"] += revenue
            inv["shares"] -= shares
            if inv["shares"] <= 0:
                inv["shares"] = 0
                inv["average_price"] = 0
            self.save(data)
            self.log_transaction(ctx, "stock_sell", revenue, account, f"shares:{shares};price:{stock['price']}")

        await self.send(ctx, f"Sold **{shares:,}** Folks share(s) for {self.money(revenue)} at {self.money(stock['price'])} each.")
