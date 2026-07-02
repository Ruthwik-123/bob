import random

from discord import app_commands
from discord.ext import commands

from .base import EconomyBase


class Dice(EconomyBase):
    @app_commands.describe(guess="Number you think the dice will land on, 1-6.", amount="Amount to bet from your wallet.")
    @commands.hybrid_command(name="dice", description="Guess the dice roll. Exact match pays configured multiplier.")
    async def dice(self, ctx: commands.Context, guess: int, amount: int) -> None:
        if guess < 1 or guess > 6:
            await self.send(ctx, "Your dice guess must be between 1 and 6.")
            return
        min_bet = self.cfg["gambling"]["min_bet"]
        if amount < min_bet:
            await self.send(ctx, f"Minimum bet is {self.money(min_bet)}.")
            return

        roll = random.randint(1, 6)
        won = guess == roll
        payout_multiplier = self.cfg["gambling"]["dice_payout_multiplier"]
        payout = int(amount * payout_multiplier)
        profit = payout - amount

        async with self._lock:
            data, _, account = await self.get_data_account(ctx)
            if account["wallet"] < amount:
                await self.send(ctx, f"You only have {self.money(account['wallet'])} in your wallet.")
                return
            account["wallet"] += profit if won else -amount
            self.save(data)
            self.log_transaction(ctx, "dice", profit if won else -amount, account, f"guess{guess}->roll{roll}")

        dice = self.emoji("dice_emoji")
        await self.send(ctx, f"{dice} Rolled **{roll}**! Exact match - you receive {self.money(payout)} total payout." if won else f"{dice} Rolled **{roll}**. Wrong number - you lost {self.money(amount)}.")
