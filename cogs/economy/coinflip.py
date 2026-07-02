import random

from discord import app_commands
from discord.ext import commands

from .base import EconomyBase


class Coinflip(EconomyBase):
    @app_commands.describe(amount="Amount to bet from your wallet.", choice="Pick heads or tails.")
    @app_commands.choices(choice=[app_commands.Choice(name="Heads", value="heads"), app_commands.Choice(name="Tails", value="tails")])
    @commands.hybrid_command(name="coinflip", description="Bet coins on heads or tails.")
    async def coinflip(self, ctx: commands.Context, amount: int, choice: str) -> None:
        choice = choice.lower()
        min_bet = self.cfg["gambling"]["min_bet"]
        if choice not in {"heads", "tails"}:
            await self.send(ctx, "Choose `heads` or `tails`.")
            return
        if amount < min_bet:
            await self.send(ctx, f"Minimum bet is {self.money(min_bet)}.")
            return

        result = random.choice(["heads", "tails"])
        won = choice == result
        profit = int(amount * self.cfg["gambling"]["coinflip_profit_multiplier"])

        async with self._lock:
            data, _, account = await self.get_data_account(ctx)
            if account["wallet"] < amount:
                await self.send(ctx, f"You only have {self.money(account['wallet'])} in your wallet.")
                return
            account["wallet"] += profit if won else -amount
            self.save(data)
            self.log_transaction(ctx, "coinflip", profit if won else -amount, account, f"{choice}->{result}")

        coin = self.emoji("coin_emoji")
        await self.send(ctx, f"{coin} It landed on **{result}**! You won {self.money(profit)} profit." if won else f"{coin} It landed on **{result}**. You lost {self.money(amount)}.")
