# * External Packages & Imports
# Discord Packages
import discord
from discord.ext import commands, tasks

# Async Packages for discord & rest apis
import asyncio

# Supabase for database
import supabase

# * Internal Packages & Imports
from .shell import ShellCore, ShellHandler, ShellCommand  # Shell
from .db import DatabaseCore, DatabaseHandler  # Database


# * Core
class Bot(commands.Bot):
    def __init__(
        self,
        token: str,
        name: str,
        shell_channel: int,
    ):
        self.token = token
        self.name = name
        self.shell_channel = shell_channel
        self.has_db = False

        # Shell
        self.shell = ShellCore(self, self.shell_channel, self.name)

        super().__init__(
            command_prefix=f"{self.name.lower()}:",
            intents=discord.Intents.all(),
            case_insensitive=True,
            help_command=None,
        )

        # Cogs
        asyncio.run(self._load_cogs())

    def add_db(
        self,
        postgres_connection: str,
        postgres_password: str = None,
        postgres_pool: int = 20,
    ):
        """
        Adds a database to the core system and initializes the database handler.
        This method sets up a database connection using the provided PostgreSQL connection string
        and attempts to add a database handler cog to the core system.
        Args:
            postgres_connection (str): The connection string for the PostgreSQL database.
            postgres_password (str, optional): The password for the PostgreSQL database. Defaults to None (Specified in the connection string).
            postgres_pool (int, optional): The maximum number of connections to the PostgreSQL database. Defaults to 20.
        Raises:
            Exception: If adding the database handler fails.
        """

        self.has_db = True
        self.db = DatabaseCore(
            self,
            postgres_connection=postgres_connection,
            postgres_password=postgres_password,
            postgres_pool=postgres_pool,
        )

        # Add the database handler
        try:
            asyncio.run(self.add_cog(DatabaseHandler(self, self.db, self.shell)))
        except:
            print("[Core] Failed to add database handler")

    def run(self):
        """Start the bot"""
        print(f"[Core] Running bot {self.name}")
        super().run(token=self.token)

    async def _load_cogs(self):
        await self.add_cog(ShellHandler(self, self.shell))

    async def on_ready(self):
        """On ready message"""
        print(f"[Core] {self.user} is ready")