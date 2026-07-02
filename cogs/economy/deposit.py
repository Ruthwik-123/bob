from discord import app_commands
from discord.ext import commands

from .base import EconomyBase


class Deposit(EconomyBase):
    @app_commands.describe(amount="Amount to move from your wallet to your bank.")
    @commands.hybrid_command(name="deposit", description="Deposit coins into your bank.")
    async def deposit(self, ctx: commands.Context, amount: int) -> None:
        if not self.validate_positive(amount):
            await self.send(ctx, "Amount must be greater than 0.")
            return

        async with self._lock:
            data, _, account = await self.get_data_account(ctx)
            if account["wallet"] < amount:
                await self.send(ctx, f"You only have {self.money(account['wallet'])} in your wallet.")
                return
            account["wallet"] -= amount
            account["bank"] += amount
            self.save(data)
            self.log_transaction(ctx, "deposit", amount, account, "wallet_to_bank")

        await self.send(ctx, f"Deposited {self.money(amount)} into your bank.")
