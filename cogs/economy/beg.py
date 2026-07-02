import random

from discord.ext import commands

from .base import EconomyBase


class Beg(EconomyBase):
    @commands.hybrid_command(name="beg", description="Beg for coins.")
    async def beg(self, ctx: commands.Context) -> None:
        beg_cfg = self.cfg["beg"]
        won = random.random() < beg_cfg["win_chance"]
        prize = random.randint(beg_cfg["min_reward"], beg_cfg["max_reward"]) if won else 0

        async with self._lock:
            data, _, account = await self.get_data_account(ctx)
            if won:
                account["wallet"] += prize
            self.save(data)
            self.log_transaction(ctx, "beg", prize, account, "win" if won else "loss")

        await self.send(ctx, f"Someone felt generous! You received {self.money(prize)}." if won else "No one gave you anything this time.")
