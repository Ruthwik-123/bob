import discord
from discord import app_commands
from discord.ext import commands

from .base import EconomyBase
from .storage import load_data


class Pay(EconomyBase):
    @app_commands.describe(member="User to pay.", amount="Amount to send from your wallet before tax.")
    @commands.hybrid_command(name="pay", description="Pay another user with configured anti-abuse tax.")
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int) -> None:
        if member.bot:
            await self.send(ctx, "You cannot pay bots.")
            return
        if member.id == ctx.author.id:
            await self.send(ctx, "You cannot pay yourself.")
            return
        if not self.validate_positive(amount):
            await self.send(ctx, "Amount must be greater than 0.")
            return

        rate = self.tax_rate(amount)
        tax = int(amount * rate)
        received = amount - tax
        if received <= 0:
            await self.send(ctx, "Amount is too small after tax.")
            return

        async with self._lock:
            data = load_data()
            guild = self.get_guild(data, self.guild_key(ctx))
            sender = self.get_account(guild, ctx.author)
            receiver = self.get_account(guild, member)
            self.apply_overdue_loan(sender)
            self.apply_overdue_loan(receiver)

            if sender["wallet"] < amount:
                await self.send(ctx, f"You only have {self.money(sender['wallet'])} in your wallet.")
                return

            sender["wallet"] -= amount
            receiver["wallet"] += received
            self.save(data)
            self.log_transaction(ctx, "pay_sent", -amount, sender, f"to:{member.id};tax:{tax};recv:{received}")
            self.log_transaction(ctx, "pay_received", received, receiver, f"from:{ctx.author.id};tax:{tax}", user=member)

        await self.send(ctx, f"Paid {member.mention} {self.money(received)}. Tax: {self.money(tax)} ({rate * 100:.1f}%).")
