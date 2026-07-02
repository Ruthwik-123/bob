import discord
from discord.ext import commands

from .base import EconomyBase


class Transaction(EconomyBase):
    @commands.hybrid_command(name="transaction", aliases=["transactions", "history"], description="Download readable transaction history files.")
    async def transaction(self, ctx: commands.Context) -> None:
        files = await self.build_transaction_report_files(ctx)
        if not files:
            await self.send(ctx, "No transaction history has been logged yet.")
            return

        scroll = self.emoji("scroll_emoji")
        message = f"{scroll} Transaction history generated in plain English, newest to oldest."

        for index in range(0, len(files), 10):
            batch = files[index : index + 10]
            discord_files = [discord.File(path) for path in batch]
            if index == 0:
                await ctx.reply(message, files=discord_files, mention_author=False)
            else:
                await ctx.send(f"Transaction history parts {index + 1}-{index + len(batch)}:", files=discord_files)
