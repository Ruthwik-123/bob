"""Loan command: borrow coins with configured interest."""

from __future__ import annotations

from discord import app_commands
from discord.ext import commands

from .base import EconomyBase


class Loan(EconomyBase):
    @app_commands.describe(amount="Amount to borrow.")
    @commands.hybrid_command(name="loan", description="Borrow coins and repay with configured interest.")
    async def loan(self, ctx: commands.Context, amount: int) -> None:
        if not self.validate_positive(amount):
            await self.send(ctx, "Loan amount must be greater than 0.")
            return

        async with self._lock:
            data, _, account = await self.get_data_account(ctx, apply_overdue=False)
            overdue_snatched = self.apply_overdue_loan(account)

            loan = account["loan"]
            if loan["remaining"] > 0:
                if overdue_snatched:
                    self.save(data)
                    self.log_transaction(ctx, "loan_snatch", -overdue_snatched, account, "overdue_before_new_loan")
                await self.send(ctx, f"You already have an active loan with {self.money(loan['remaining'])} remaining. Use `pay_loan` first.")
                return

            total_due = self.loan_total_due(amount)
            installment = self.loan_installment(amount)
            due_at = self.loan_due_at()

            account["wallet"] += amount
            account["loan"] = {
                "principal": amount,
                "remaining": total_due,
                "total_due": total_due,
                "interest_total": total_due - amount,
                "interest_rate": self.cfg["loan"]["total_interest_rate"],
                "installment": installment,
                "borrowed_at": self.now().isoformat(),
                "due_at": due_at.isoformat(),
            }
            self.save(data)
            self.log_transaction(ctx, "loan_borrow", amount, account, f"due:{self.fmt_due(due_at)};total:{total_due}")

        interest_percent = self.cfg["loan"]["total_interest_rate"] * 100
        await self.send(
            ctx,
            f"Loan approved! You borrowed {self.money(amount)}.\n"
            f"Total repayment with {interest_percent:.0f}% interest: {self.money(total_due)}.\n"
            f"Each `pay_loan` payment is {self.money(installment)}.\n\n"
            f"Pay within {self.cfg['loan']['term_days']} days (**{self.fmt_due(due_at)}**) "
            "or it will be snatched and your account might go into negatives.",
        )
