from discord.ext import commands

from .base import EconomyBase
from .storage import load_data


class CreateAccount(EconomyBase):
    @commands.hybrid_command(name="create_account", description="Create your economy account.")
    async def create_account(self, ctx: commands.Context) -> None:
        async with self._lock:
            data = load_data()
            guild = self.get_guild(data, self.guild_key(ctx))
            user_id = self.user_key(ctx.author)

            if user_id in guild.setdefault("users", {}):
                await self.send(ctx, f"{ctx.author.mention}, you already have an account.")
                return

            account = self.get_account(guild, ctx.author)
            self.save(data)
            self.log_transaction(ctx, "create_account", 0, account, "account_created")

        await self.send(ctx, f"Account created for {ctx.author.mention}! Use `daily` to earn your first coins.")
