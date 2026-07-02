import random
from datetime import timedelta

from discord.ext import commands

from .base import EconomyBase


class Daily(EconomyBase):
    @commands.hybrid_command(name="daily", description="Claim your daily prize.")
    async def daily(self, ctx: commands.Context) -> None:
        daily_cfg = self.cfg["daily"]
        cooldown = timedelta(hours=daily_cfg["cooldown_hours"])

        async with self._lock:
            data, _, account = await self.get_data_account(ctx)
            last_daily = self.parse_time(account.get("last_daily"))

            if last_daily and self.now() - last_daily < cooldown:
                remaining = cooldown - (self.now() - last_daily)
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes = remainder // 60
                await self.send(ctx, f"You already claimed daily. Try again in **{hours}h {minutes}m**.")
                return

            prize = random.randint(daily_cfg["min_reward"], daily_cfg["max_reward"])
            account["wallet"] += prize
            account["last_daily"] = self.now().isoformat()
            self.save(data)
            self.log_transaction(ctx, "daily", prize, account, "claim")

        await self.send(ctx, f"Daily claimed! You won {self.money(prize)}.")
