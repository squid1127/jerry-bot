"""Simple discord.py bot to erase application commands."""

import discord
from discord.ext import commands

TOKEN_VAR = "BOT_TOKEN"

class ResetBot(commands.Bot):
    """A bot that can reset its application commands."""

    def __init__(self) -> None:
        """Initialize the bot with necessary intents."""
        intents = discord.Intents.none()
        super().__init__(command_prefix="!", intents=intents)

    async def on_ready(self) -> None:
        """Event triggered when the bot is ready."""
        if self.user is None:
            raise RuntimeError("Invalid user state")
        
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")
        await self.tree.sync()  # Sync commands on startup (There's none)
        print("Application commands have been reset, exiting...")
        await self.close()  # Close the bot after resetting commands


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv

    load_dotenv()
    TOKEN = os.getenv(TOKEN_VAR)
    if not TOKEN:
        raise ValueError(f"{TOKEN_VAR} should be set as a env variable (or inside .env)")

    bot = ResetBot()
    print("Running bot...")
    bot.run(TOKEN)
