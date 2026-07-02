import discord
from discord.ext import commands

from .base import EconomyBase


class LoanStatus(EconomyBase):
    @commands.hybrid_command(name="loan_status", description="View your active loan, interest, payments, and due date.")
    async def loan_status(self, ctx: commands.Context) -> None:
        async with self._lock:
            data, _, account = await self.get_data_account(ctx, apply_overdue=False)
            snatched = self.apply_overdue_loan(account)
            if snatched:
                self.save(data)
                self.log_transaction(ctx, "loan_snatch", -snatched, account, "loan_status_overdue")
                await self.send(ctx, f"Your loan was overdue, so the bot snatched **{self.money(snatched)}**. Your loan is now closed.")
                return
            loan = account["loan"]

        if loan["remaining"] <= 0:
            await self.send(ctx, "You do not have an active loan.")
            return

        principal = loan["principal"]
        total_due = loan["total_due"]
        total_interest = loan.get("interest_total", total_due - principal)
        repaid = total_due - loan["remaining"]
        interest_rate = loan.get("interest_rate", self.cfg["loan"]["total_interest_rate"]) * 100

        embed = discord.Embed(title=f"{self.emoji('bank_emoji')} Loan Status", color=discord.Color.orange())
        embed.add_field(name="Borrowed", value=self.money(principal), inline=True)
        embed.add_field(name=f"Interest ({interest_rate:.1f}%)", value=self.money(total_interest), inline=True)
        embed.add_field(name="Total Due", value=self.money(total_due), inline=True)
        embed.add_field(name="Repaid", value=self.money(repaid), inline=True)
        embed.add_field(name="Remaining", value=self.money(loan["remaining"]), inline=True)
        embed.add_field(name="Each pay_loan", value=self.money(loan["installment"]), inline=True)
        embed.add_field(name="Due Date", value=self.fmt_due(loan["due_at"]), inline=False)
        await ctx.reply(embed=embed, mention_author=False)
