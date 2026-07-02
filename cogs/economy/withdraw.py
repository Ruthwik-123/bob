from discord import app_commands
from discord.ext import commands

from .base import EconomyBase


class Withdraw(EconomyBase):
    @app_commands.describe(amount="Amount to move from your bank to your wallet.")
    @commands.hybrid_command(name="withdraw", description="Withdraw coins from your bank.")
    async def withdraw(self, ctx: commands.Context, amount: int) -> None:
        if not self.validate_positive(amount):
            await self.send(ctx, "Amount must be greater than 0.")
            return

        async with self._lock:
            data, _, account = await self.get_data_account(ctx)
            if account["bank"] < amount:
                await self.send(ctx, f"You only have {self.money(account['bank'])} in your bank.")
                return
            account["bank"] -= amount
            account["wallet"] += amount
            self.save(data)
            self.log_transaction(ctx, "withdraw", amount, account, "bank_to_wallet")

        await self.send(ctx, f"Withdrew {self.money(amount)} to your wallet.")
