"""Shared helpers for economy command cogs."""

from __future__ import annotations

import asyncio
import math
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from .storage import config_values, load_data, save_data


class EconomyBase(commands.Cog):
    """Base class with JSON account, config, market, and log helpers."""

    _lock = asyncio.Lock()

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def cfg(self) -> dict[str, Any]:
        return config_values()

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def parse_time(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    def fmt_due(self, value: datetime | str | None) -> str:
        dt = self.parse_time(value) if isinstance(value, str) else value
        return dt.strftime("%d-%m-%Y %H:%M UTC") if dt else "unknown"

    def emoji(self, key: str) -> str:
        """Return a Discord colon-code emoji from config.json, e.g. :coin:."""
        return self.cfg.get("emojis", {}).get(key, "")

    def money(self, amount: int | float) -> str:
        emoji = self.emoji("coin_emoji")
        prefix = f"{emoji} " if emoji else ""
        return f"{prefix}{int(amount):,}"

    @staticmethod
    def guild_key(ctx: commands.Context) -> str:
        return str(ctx.guild.id) if ctx.guild else "dm"

    @staticmethod
    def user_key(user: discord.abc.User) -> str:
        return str(user.id)

    @staticmethod
    def validate_positive(amount: int) -> bool:
        return amount > 0

    def tax_rate(self, amount: int) -> float:
        pay_cfg = self.cfg["pay"]
        return pay_cfg["low_tax_rate"] if amount < pay_cfg["tax_threshold"] else pay_cfg["high_tax_rate"]

    async def send(self, ctx: commands.Context, message: str) -> None:
        await ctx.reply(message, mention_author=False)

    def get_guild(self, data: dict[str, Any], guild_id: str) -> dict[str, Any]:
        guild = data.setdefault("guilds", {}).setdefault(guild_id, {"users": {}})
        guild.setdefault("users", {})
        guild.setdefault("market", {})
        return guild

    def empty_loan(self) -> dict[str, Any]:
        return {
            "principal": 0,
            "remaining": 0,
            "total_due": 0,
            "interest_total": 0,
            "interest_rate": 0,
            "installment": 0,
            "borrowed_at": None,
            "due_at": None,
        }

    def loan_installment(self, principal: int) -> int:
        loan_cfg = self.cfg["loan"]
        return max(
            1,
            math.ceil(principal * loan_cfg["installment_principal_rate"])
            + math.ceil(principal * loan_cfg["installment_interest_rate"]),
        )

    def loan_total_due(self, amount: int) -> int:
        return math.ceil(amount * (1 + self.cfg["loan"]["total_interest_rate"]))

    def loan_due_at(self) -> datetime:
        loan_cfg = self.cfg["loan"]
        raw_due_at = self.now() + timedelta(days=loan_cfg["term_days"])
        if not loan_cfg.get("round_due_to_next_hour", True):
            return raw_due_at
        due_at = raw_due_at.replace(minute=0, second=0, microsecond=0)
        if raw_due_at.minute or raw_due_at.second or raw_due_at.microsecond:
            due_at += timedelta(hours=1)
        return due_at

    def get_account(self, guild_data: dict[str, Any], user: discord.abc.User) -> dict[str, Any]:
        accounts_cfg = self.cfg.get("accounts", {})
        users = guild_data.setdefault("users", {})
        account = users.setdefault(
            self.user_key(user),
            {
                "wallet": accounts_cfg.get("starting_wallet", 0),
                "bank": accounts_cfg.get("starting_bank", 0),
                "last_daily": None,
                "last_weekly": None,
                "loan": self.empty_loan(),
                "investments": {},
            },
        )
        account.setdefault("wallet", accounts_cfg.get("starting_wallet", 0))
        account.setdefault("bank", accounts_cfg.get("starting_bank", 0))
        account.setdefault("last_daily", None)
        account.setdefault("last_weekly", None)
        account.setdefault("investments", {})

        if not isinstance(account.get("loan"), dict):
            account["loan"] = self.empty_loan()
        for key, value in self.empty_loan().items():
            account["loan"].setdefault(key, value)

        stock_key = self.cfg["stock_market"]["stock_key"]
        investment = account["investments"].setdefault(stock_key, {"shares": 0, "average_price": 0})
        investment.setdefault("shares", 0)
        investment.setdefault("average_price", 0)
        return account

    def apply_overdue_loan(self, account: dict[str, Any]) -> int:
        """Snatch overdue loan debt without confirmation, allowing wallet negatives."""
        loan = account.setdefault("loan", self.empty_loan())
        if not isinstance(loan, dict):
            account["loan"] = self.empty_loan()
            return 0

        remaining = int(loan.get("remaining", 0))
        due_at = self.parse_time(loan.get("due_at"))
        if remaining <= 0 or not due_at or self.now() < due_at:
            return 0

        loan_cfg = self.cfg["loan"]
        if loan_cfg.get("snatch_bank_first", True):
            available_bank = max(0, account.get("bank", 0))
            from_bank = min(available_bank, remaining)
            account["bank"] -= from_bank
            unpaid = remaining - from_bank
        else:
            unpaid = remaining

        if loan_cfg.get("allow_negative_wallet_on_snatch", True):
            account["wallet"] -= unpaid
        else:
            account["wallet"] = max(0, account["wallet"] - unpaid)
        account["loan"] = self.empty_loan()
        return remaining

    async def get_data_account(
        self,
        ctx: commands.Context,
        *,
        apply_overdue: bool = True,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        data = load_data()
        guild = self.get_guild(data, self.guild_key(ctx))
        account = self.get_account(guild, ctx.author)
        if apply_overdue:
            snatched = self.apply_overdue_loan(account)
            if snatched:
                self.save(data)
                self.log_transaction(ctx, "loan_snatch", -snatched, account, "overdue_auto_collection")
        return data, guild, account

    def ensure_stock(self, guild_data: dict[str, Any], *, update: bool = True) -> dict[str, Any]:
        market_cfg = self.cfg["stock_market"]
        stock_key = market_cfg["stock_key"]
        stock = guild_data.setdefault("market", {}).setdefault(
            stock_key,
            {
                "price": market_cfg["starting_price"],
                "last_update": self.now().isoformat(),
                "last_percent_change": 0.0,
            },
        )
        stock.setdefault("price", market_cfg["starting_price"])
        stock.setdefault("last_update", self.now().isoformat())
        stock.setdefault("last_percent_change", 0.0)

        last_update = self.parse_time(stock.get("last_update")) or self.now()
        if update and (self.now() - last_update).total_seconds() >= market_cfg["update_interval_seconds"]:
            percent = random.uniform(market_cfg["min_percent_change"], market_cfg["max_percent_change"])
            new_price = max(market_cfg["min_price"], round(stock["price"] * (1 + percent / 100)))
            stock["price"] = int(new_price)
            stock["last_update"] = self.now().isoformat()
            stock["last_percent_change"] = round(percent, 2)
        return stock

    def investment_value(self, guild_data: dict[str, Any], account: dict[str, Any]) -> int:
        stock_key = self.cfg["stock_market"]["stock_key"]
        stock = self.ensure_stock(guild_data, update=False)
        shares = account.get("investments", {}).get(stock_key, {}).get("shares", 0)
        return int(shares * stock["price"])

    def net_worth(self, guild_data: dict[str, Any], account: dict[str, Any]) -> int:
        loan_remaining = int(account.get("loan", {}).get("remaining", 0))
        return int(account.get("wallet", 0) + account.get("bank", 0) + self.investment_value(guild_data, account) - loan_remaining)

    def save(self, data: dict[str, Any]) -> None:
        save_data(data)

    @staticmethod
    def _clean_note(note: str) -> str:
        note = re.sub(r"[\r\n|]+", " ", str(note))
        return note[:160]

    def _transaction_path(self, guild_id: str, part: int = 1) -> Path:
        tx_cfg = self.cfg["transactions"]
        directory = Path(tx_cfg["directory"])
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"guild_{guild_id}_part_{part}.txt"

    def _roll_transaction_parts(self, guild_id: str) -> None:
        tx_cfg = self.cfg["transactions"]
        max_parts = int(tx_cfg.get("max_parts", 25))
        oldest = self._transaction_path(guild_id, max_parts)
        if oldest.exists():
            oldest.unlink()
        for part in range(max_parts - 1, 0, -1):
            src = self._transaction_path(guild_id, part)
            if src.exists():
                src.replace(self._transaction_path(guild_id, part + 1))

    def log_transaction(
        self,
        ctx: commands.Context,
        kind: str,
        amount: int,
        account: dict[str, Any] | None = None,
        note: str = "",
        user: discord.abc.User | None = None,
    ) -> None:
        tx_cfg = self.cfg.get("transactions", {})
        if not tx_cfg.get("enabled", True):
            return

        guild_id = self.guild_key(ctx)
        user_id = self.user_key(user or ctx.author)
        wallet = account.get("wallet", "?") if account else "?"
        bank = account.get("bank", "?") if account else "?"
        line = (
            f"{self.now().strftime('%y%m%d%H%M%S')}|u{user_id}|{kind}|{amount}|"
            f"w{wallet}|b{bank}|{self._clean_note(note)}\n"
        )
        encoded_size = len(line.encode("utf-8"))
        path = self._transaction_path(guild_id, 1)
        max_size = int(tx_cfg.get("max_part_size_bytes", 9_961_472))

        current = ""
        if path.exists():
            if path.stat().st_size + encoded_size > max_size:
                self._roll_transaction_parts(guild_id)
            else:
                current = path.read_text(encoding="utf-8")

        path.write_text(line + current, encoding="utf-8")

    def read_transaction_lines(self, ctx: commands.Context, limit: int | None = None) -> list[str]:
        tx_cfg = self.cfg["transactions"]
        lines: list[str] = []
        for part in range(1, int(tx_cfg.get("max_parts", 25)) + 1):
            path = self._transaction_path(self.guild_key(ctx), part)
            if not path.exists():
                continue
            lines.extend(path.read_text(encoding="utf-8").splitlines())
            if limit and len(lines) >= limit:
                break
        return lines[:limit] if limit else lines

    async def resolve_display_name(self, guild: discord.Guild | None, user_id: int) -> str:
        """Resolve server display name/global display name instead of raw IDs."""
        if guild:
            member = guild.get_member(user_id)
            if member:
                return member.display_name
            try:
                member = await guild.fetch_member(user_id)
                return member.display_name
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        user = self.bot.get_user(user_id)
        if not user:
            try:
                user = await self.bot.fetch_user(user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                user = None
        if user:
            return user.global_name or user.display_name or user.name
        return f"Unknown User {user_id}"

    @staticmethod
    def parse_transaction_line(line: str) -> dict[str, Any] | None:
        parts = line.split("|", 6)
        if len(parts) != 7:
            return None
        timestamp, raw_user, kind, amount, wallet, bank, note = parts
        try:
            return {
                "timestamp_raw": timestamp,
                "user_id": int(raw_user.removeprefix("u")),
                "kind": kind,
                "amount": int(amount),
                "wallet": wallet.removeprefix("w"),
                "bank": bank.removeprefix("b"),
                "note": note,
            }
        except ValueError:
            return None

    def format_transaction_timestamp(self, raw: str) -> str:
        try:
            dt = datetime.strptime(raw, "%y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            return dt.strftime("%d-%m-%Y %H:%M")
        except ValueError:
            return raw

    async def human_transaction_line(self, ctx: commands.Context, raw_line: str) -> str | None:
        parsed = self.parse_transaction_line(raw_line)
        if not parsed:
            return None

        loc = self.cfg.get("localization", {})
        actions = loc.get("transaction_actions", {})
        template = actions.get(parsed["kind"], loc.get("transaction_unknown_action", "made an economy transaction of {amount} {currency}"))
        currency = self.cfg.get("currency", {}).get("name", "coins")
        user_name = await self.resolve_display_name(ctx.guild, parsed["user_id"])
        values = {
            "user": user_name,
            "amount": parsed["amount"],
            "amount_abs": abs(parsed["amount"]),
            "currency": currency,
            "wallet": parsed["wallet"],
            "bank": parsed["bank"],
            "note": parsed["note"],
            "timestamp": self.format_transaction_timestamp(parsed["timestamp_raw"]),
        }
        try:
            action = template.format(**values)
            wrapper = loc.get("transaction_line_format", "[{timestamp}] {user} {action} (Wallet: {wallet} | Bank: {bank})")
            return wrapper.format(action=action, **values)
        except KeyError:
            return f"[{values['timestamp']}] {user_name} {parsed['kind']} {parsed['amount']} {currency} (Wallet: {parsed['wallet']} | Bank: {parsed['bank']})"

    async def build_transaction_report_files(self, ctx: commands.Context) -> list[Path]:
        """Build human-readable newest-first .txt files below the upload threshold."""
        tx_cfg = self.cfg["transactions"]
        max_size = int(tx_cfg.get("max_part_size_bytes", 9_500_000))
        out_dir = Path(tx_cfg["directory"]) / "readable"
        out_dir.mkdir(parents=True, exist_ok=True)

        guild_id = self.guild_key(ctx)
        for old in out_dir.glob(f"guild_{guild_id}_transactions_part_*.txt"):
            old.unlink()

        files: list[Path] = []
        part = 1
        current = ""
        header = "Transaction History - newest to oldest\n"
        header += "Generated in plain English from compact economy logs.\n\n"
        current += header

        for raw in self.read_transaction_lines(ctx):
            human = await self.human_transaction_line(ctx, raw)
            if not human:
                continue
            line = human + "\n"
            if len((current + line).encode("utf-8")) > max_size and current.strip():
                path = out_dir / f"guild_{guild_id}_transactions_part_{part}.txt"
                path.write_text(current, encoding="utf-8")
                files.append(path)
                part += 1
                current = header
            current += line

        if current.strip() and current != header:
            path = out_dir / f"guild_{guild_id}_transactions_part_{part}.txt"
            path.write_text(current, encoding="utf-8")
            files.append(path)
        return files

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        message = "Sorry, something went wrong while running that economy command."
        if isinstance(error, app_commands.CommandInvokeError):
            original = error.original
            if isinstance(original, commands.BadArgument):
                message = "Invalid argument. Check the command and try again."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
