"""pay_loan command: repay the current loan in fixed installments."""

from __future__ import annotations

from discord.ext import commands

from .base import EconomyBase


class PayLoan(EconomyBase):
    @commands.hybrid_command(name="pay_loan", description="Pay one configured loan installment.")
    async def pay_loan(self, ctx: commands.Context) -> None:
        async with self._lock:
            data, _, account = await self.get_data_account(ctx, apply_overdue=False)
            overdue_snatched = self.apply_overdue_loan(account)

            if overdue_snatched:
                self.save(data)
                self.log_transaction(ctx, "loan_snatch", -overdue_snatched, account, "overdue_pay_loan")
                await self.send(ctx, f"Your loan was overdue, so the bot snatched **{self.money(overdue_snatched)}** from your account. Your loan is now closed.")
                return

            loan = account["loan"]
            remaining = loan["remaining"]
            if remaining <= 0:
                await self.send(ctx, "You do not have an active loan.")
                return

            payment = min(loan.get("installment", self.loan_installment(loan["principal"])), remaining)
            if account["wallet"] < payment:
                await self.send(ctx, f"You need {self.money(payment)} in your wallet for this loan payment, but you only have {self.money(account['wallet'])}.")
                return

            account["wallet"] -= payment
            loan["remaining"] -= payment

            if loan["remaining"] <= 0:
                account["loan"] = self.empty_loan()
                self.save(data)
                self.log_transaction(ctx, "loan_payment", -payment, account, "loan_fully_repaid")
                await self.send(ctx, f"Paid {self.money(payment)}. Your loan is fully repaid!")
                return

            self.save(data)
            self.log_transaction(ctx, "loan_payment", -payment, account, f"remaining:{loan['remaining']}")
            due_text = self.fmt_due(loan.get("due_at"))

        await self.send(ctx, f"Paid {self.money(payment)} toward your loan. Remaining debt: **{self.money(loan['remaining'])}**. Due: **{due_text}**.")
