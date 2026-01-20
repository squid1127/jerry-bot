"""Main Module for SimpleGames"""

# squid_core imports
from squid_core import Plugin, PluginCog, Framework

import discord
from discord.ext import commands
from discord import app_commands

from .rps import RPSGame
from .tic_tac_toe import TicTacToeGame

class SimpleGames(Plugin):
    """SimpleGames Plugin."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.cog = SimpleGamesCog(self)

    async def load(self):
        """Load the SimpleGames Plugin."""
        await self.framework.bot.add_cog(self.cog)
        self.framework.logger.info("SimpleGames Plugin loaded.")

    async def unload(self):
        """Unload the SimpleGames Plugin."""
        await self.framework.bot.remove_cog(self.cog.qualified_name)


class SimpleGamesCog(PluginCog):
    """Cog for SimpleGames Plugin."""

    def __init__(self, plugin: SimpleGames):
        super().__init__(plugin)

    @app_commands.command(
        name="rps", description="Start a game of Rock, Paper, Scissors."
    )
    @app_commands.describe(players="Number of players (default is 2)")
    async def rps_command(self, interaction: discord.Interaction, players: int = 2):
        """Command to start a Rock, Paper, Scissors game."""
        if players < 2:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="Number of players must be 2 or more.",
                    title="Rock, Paper, Scissors",
                    ephemeral=True,
                    color=discord.Color.red(),
                )
            )
            return
        rps_game = RPSGame(interaction, players)
        await interaction.response.send_message(view=rps_game)

    @app_commands.command(
        name="tictactoe", description="Start a game of Tic Tac Toe."
    )
    async def tictactoe_command(self, interaction: discord.Interaction):
        """Command to start a Tic Tac Toe game."""
        tictactoe_game = TicTacToeGame(interaction)
        await interaction.response.send_message(view=tictactoe_game)