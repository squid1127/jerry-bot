# Packages
import discord
from discord import app_commands
from discord.ext import commands
import logging

# squid-core
import core


class StaticCommands(commands.Cog):
    """Static commands that don't really do much, including api commands"""

    def __init__(self, bot: core.Bot):
        self.bot = bot

        self.bot.shell.add_command(
            "api",
            cog="StaticCommands",
            description="Manage API keys",
        )
        self.logger = logging.getLogger("jerry.staticcommands")

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("Static commands ready")

    async def cog_status(self):
        return "Ready"

    async def shell_callback(self, command: core.ShellCommand):
        if command.name == "api":
            await command.log(
                "This command is not yet implemented (Since no commands require API keys)"
            )
            return

    @app_commands.command(
        name="ping-jerry",
        description="Is Jerry alive?",
    )
    async def ping_command(self, interaction: discord.Interaction):
        # Get latency
        latency = self.bot.latency * 1000
        await interaction.response.send_message(f"Pong! 🏓\nLatency: {latency:.2f}ms")

    @app_commands.command(
        name="purge",
        description="Purge messages from a channel",
    )
    @app_commands.describe(
        limit="The number of messages to delete",
    )
    async def purge_command(self, interaction: discord.Interaction, limit: int = None):
        # Check if user has permission
        if not interaction.channel.permissions_for(interaction.user).manage_messages:
            await interaction.response.send_message(
                "You don't have permission to delete messages", ephemeral=True
            )
            return

        if limit is not None and (limit > 100 or limit < 1):
            await interaction.response.send_message(
                "The limit cannot exceed 100", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Purging {limit if limit is not None else 'all'} messages... Beware of rate limits!",
            ephemeral=True,
        )

        # Purge messages
        try:
            if limit is None:
                await interaction.channel.purge()
            else:
                await interaction.channel.purge(limit=limit)
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to delete messages", ephemeral=True
            )
            return
        except Exception as e:
            await self.bot.shell.log(
                f"A purge command failed: {e}", "StaticCommands", msg_type="error"
            )
            await interaction.followup.send(
                "An error occurred while purging messages", ephemeral=True
            )

        await interaction.followup.send("Messages purged", ephemeral=True)

    @app_commands.command(
        name="help-jerry",
        description="Get help with Jerry",
    )
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Jerry Bot",
            description="I'm Jerry, a bot created by CubbScratchStudios. I'm designed as a server-specific bot, meaning I have features that are unique to each server I'm in. However, I also have some global features that are available in all servers.",
            color=self.bot.JERRY_RED,
        )

        embed.add_field(
            name="Global Commands",
            value="""Here are some commands that are available in all servers:
- `/ping-jerry` - Check if Jerry is alive
- `/help-jerry` - This command
- `/sticker` - Get a sticker from the CubbScratchStudios sticker pack
- `/sever` - Get server information such as message count by user. Kinda like a leveling bot but includes all time. (Highly experimental)
More to come soon!""",
            inline=False,
        )
        embed.add_field(
            name="Community Server",
            value="Check out the [CubbScratchStudios Bot Community Server](https://je.fr.to/discord-bot-community) for more information about Jerry and other bots, as well as support and discussion. (We're still setting things up, so please be patient!)",
            inline=False,
        )
        embed.add_field(
            name="Splat Bot",
            value="If you want a more general-purpose bot, check out [Splat Bot](https://je.fr.to/splat-bot), a bot that can do a lot of things, including moderation, fun commands, and more!",
        )
        embed.set_footer(
            text="Brought to you by CubbScratchStudios",
            icon_url="https://je.fr.to/static/css_logo.PNG",
        )

        await interaction.response.send_message(embed=embed)


