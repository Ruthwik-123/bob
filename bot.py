"""Discord economy bot using discord.py v2.x.

- Loads configuration from .env via python-dotenv.
- Supports slash commands and no-prefix message commands.
- Loads economy commands from cogs/economy.
"""

import logging
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from cogs.economy.storage import config_values


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("economy_bot")


# Env loading: DISCORD_TOKEN is read from .env.
load_dotenv()
DISCORD_TOKEN: Optional[str] = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN. Add it to your .env file.")


# Default intents are required. message_content is required because this bot uses
# no-prefix message commands like `balance`, `deposit 100`, and `hello`.
intents = discord.Intents.default()
intents.message_content = True


class EconomyBot(commands.Bot):
    def __init__(self) -> None:
        # Empty prefix means commands are typed directly, e.g. `hi`, `balance`.
        super().__init__(command_prefix="", intents=intents)
        self._synced_commands = False

    async def setup_hook(self) -> None:
        # Cog loading: all economy commands live in cogs/economy.
        await self.load_extension("cogs.economy")
        logger.info("Loaded economy cog.")

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id if self.user else "unknown")

        # Tree sync: makes slash commands available in Discord.
        if not self._synced_commands:
            try:
                synced = await self.tree.sync()
                self._synced_commands = True
                logger.info("Successfully synced %d slash command(s).", len(synced))
            except discord.HTTPException as exc:
                logger.exception("Failed to sync slash command tree: %s", exc)
            except Exception as exc:
                logger.exception("Unexpected error while syncing command tree: %s", exc)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        # Ignore normal chat that is not a command. This is important with no prefix.
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"Missing argument: `{error.param.name}`.", mention_author=False)
            return

        if isinstance(error, commands.BadArgument):
            await ctx.reply("Invalid argument. Check the command and try again.", mention_author=False)
            return

        logger.exception("Prefix command error in %s: %s", ctx.command, error)
        await ctx.reply("Sorry, something went wrong while running that command.", mention_author=False)


bot = EconomyBot()


async def greeting_for(user: discord.abc.User, greeting: str) -> str:
    wave = config_values().get("emojis", {}).get("wave_emoji", "")
    wave_text = f" {wave}" if wave else ""
    return f"{greeting}, {user.mention}!{wave_text} Hope you're having a great day!"


@bot.command(name="hello", help="Say hello to the bot.")
async def prefix_hello(ctx: commands.Context) -> None:
    await ctx.reply(await greeting_for(ctx.author, "Hello"), mention_author=False)


@bot.command(name="hi", help="Say hi to the bot.")
async def prefix_hi(ctx: commands.Context) -> None:
    await ctx.reply(await greeting_for(ctx.author, "Hi"), mention_author=False)


@app_commands.command(name="hello", description="Receive a hello greeting.")
async def slash_hello(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(await greeting_for(interaction.user, "Hello"))


@app_commands.command(name="hi", description="Receive a hi greeting.")
async def slash_hi(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(await greeting_for(interaction.user, "Hi"))


@slash_hello.error
@slash_hi.error
async def slash_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    logger.exception("Slash greeting command error: %s", error)
    message = "Sorry, something went wrong while running that command."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


# Slash command registration for the simple greeting commands.
bot.tree.add_command(slash_hello)
bot.tree.add_command(slash_hi)


if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure as exc:
        logger.exception("Invalid DISCORD_TOKEN provided: %s", exc)
        raise SystemExit("Invalid DISCORD_TOKEN. Check your .env file.") from exc
