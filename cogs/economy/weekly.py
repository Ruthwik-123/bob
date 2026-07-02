import random
from datetime import timedelta

from discord.ext import commands

from .base import EconomyBase


class Weekly(EconomyBase):
    @commands.hybrid_command(name="weekly", description="Claim your weekly prize.")
    async def weekly(self, ctx: commands.Context) -> None:
        weekly_cfg = self.cfg["weekly"]
        cooldown = timedelta(days=weekly_cfg["cooldown_days"])

        async with self._lock:
            data, _, account = await self.get_data_account(ctx)
            last_weekly = self.parse_time(account.get("last_weekly"))

            if last_weekly and self.now() - last_weekly < cooldown:
                remaining = cooldown - (self.now() - last_weekly)
                await self.send(ctx, f"You already claimed weekly. Try again in **{remaining.days}d {remaining.seconds // 3600}h**.")
                return

            prize = random.randint(weekly_cfg["min_reward"], weekly_cfg["max_reward"])
            account["wallet"] += prize
            account["last_weekly"] = self.now().isoformat()
            self.save(data)
            self.log_transaction(ctx, "weekly", prize, account, "claim")

        await self.send(ctx, f"Weekly claimed! You won {self.money(prize)}.")
