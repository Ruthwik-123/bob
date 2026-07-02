"""Economy command package.

Each command is split into its own file, while this extension loads them all.
"""

from .account import Account
from .balance import Balance
from .beg import Beg
from .coinflip import Coinflip
from .create_account import CreateAccount
from .daily import Daily
from .deposit import Deposit
from .dice import Dice
from .invest import Invest
from .leaderboard import Leaderboard
from .loan import Loan
from .loan_status import LoanStatus
from .pay import Pay
from .pay_loan import PayLoan
from .transaction import Transaction
from .weekly import Weekly
from .withdraw import Withdraw
from .work import Work


async def setup(bot):
    await bot.add_cog(CreateAccount(bot))
    await bot.add_cog(Account(bot))
    await bot.add_cog(Balance(bot))
    await bot.add_cog(Deposit(bot))
    await bot.add_cog(Withdraw(bot))
    await bot.add_cog(Leaderboard(bot))
    await bot.add_cog(Loan(bot))
    await bot.add_cog(LoanStatus(bot))
    await bot.add_cog(PayLoan(bot))
    await bot.add_cog(Invest(bot))
    await bot.add_cog(Transaction(bot))
    await bot.add_cog(Work(bot))
    await bot.add_cog(Daily(bot))
    await bot.add_cog(Weekly(bot))
    await bot.add_cog(Beg(bot))
    await bot.add_cog(Coinflip(bot))
    await bot.add_cog(Dice(bot))
    await bot.add_cog(Pay(bot))
