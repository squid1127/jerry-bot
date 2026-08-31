"""Main plugin file for Commands plugin."""

import asyncio

import aiohttp
import bs4
import discord
from discord import app_commands
from squid_core import Plugin, PluginCog
from squid_core.framework import Framework

from .at_everyone import StaticCommandAtEveryoneCog
from .constants import *
from .repeat import StaticCommandRepeatCog


class StaticCommands(PluginCog):
    """
    #! Reused from legacy Jerry Bot + minor modifications

    Static commands that don't really do much, including api commands
    """

    def __init__(self, plugin: Plugin):
        self.plugin: Plugin = plugin
        self.bot = plugin.fw.bot
        self.logger = plugin.logger
        self.perms = plugin.fw.perms

        self.dev_excuses = "http://developerexcuses.com/"

        self.cat = "https://cataas.com/cat"
        self.cat_title = "Cat as a Service"
        
        self.random = "https://www.random.org/integers"
        self.api_command_semaphore = asyncio.Semaphore(2)  # Limit to 2 concurrent API commands
        self._http_session: aiohttp.ClientSession | None = None

    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create a shared HTTP session."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session
    
    async def cog_unload(self):
        """Clean up resources when cog is unloaded."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

    @app_commands.command(
        name="ping-jerry",
        description="[Commands] Is Jerry alive?",
    )
    async def ping_command(self, interaction: discord.Interaction):
        if not await self.perms.interaction_check(interaction):
            return

        # Get latency
        latency = self.bot.latency * 1000
        await interaction.response.send_message(f"Pong! 🏓\nLatency: {latency:.2f}ms")

    @app_commands.command(
        name="help-jerry",
        description="[Commands] Get help with Jerry",
    )
    @app_commands.allowed_contexts(app_commands.AppCommandContext(guild=True))
    async def help_command(self, interaction: discord.Interaction):
        if not await self.perms.interaction_check(interaction):
            return

        embed = discord.Embed(
            title=JERRY_TITLE,
            description=JERRY_DESCRIPTION,
            color=discord.Color.red(),
        )

        embed.add_field(
            name="Global Commands",
            value=JERRY_GLOBAL_COMMANDS,
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="my-code-sucks",
        description="[Commands] Helps you with your stupid code",
    )
    async def my_code_sucks_command(self, interaction: discord.Interaction):
        """Gives you a random excuse for your code not working"""
        if not await self.perms.interaction_check(interaction):
            return

        # Request headers
        headers = {
            "User-Agent": "JerryBot/1.0",
            "Accept": "text/plain",
        }
        await interaction.response.defer(thinking=True)
        
        # Semaphore to limit concurrent API commands
        async with self.api_command_semaphore:
            session = await self._get_session()
            async with session.get(self.dev_excuses, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = bs4.BeautifulSoup(html, "html.parser")
                    excuse_tag = soup.find("center")
                    excuse = (
                        excuse_tag.find("a").text
                        if excuse_tag and excuse_tag.find("a")
                        else "No excuse found."
                    )
                    await interaction.followup.send(f"||*{excuse}*||")
                else:
                    await interaction.followup.send(
                        "Sorry, I can't help you. It's just that bad. :P"
                    )


    @app_commands.command(name="cat", description="[Commands] Sends a random cat image.")
    async def cat_command(self, interaction: discord.Interaction):
        """Sends a random cat image."""

        if not await self.perms.interaction_check(interaction):
            return

        await interaction.response.defer(thinking=True)
        

        async with self.api_command_semaphore:
            # Request headers
            headers = {
                "User-Agent": "JerryBot/1.0",
            }

            # Fetch cat image
            session = await self._get_session()
            async with session.get(self.cat, headers=headers) as response:
                if response.status == 200:
                    data = await response.read()

                else:
                    await interaction.followup.send(
                        "Sorry, I couldn't get a cat image right now."
                    )
                    return

        # Convert to discord file, using BytesIO
        from io import BytesIO

        file = discord.File(BytesIO(data), filename="cat.jpg")

        # Embed
        embed = discord.Embed(color=discord.Color.blue()).set_footer(
            text=f"Images provided by {self.cat_title}"
        )

        await interaction.followup.send(embed=embed, file=file)
    
    @app_commands.command(
        name="yes-no", description="[Commands] Get a random yes or no answer. Like an 8-ball but simpler."
    )
    async def yes_no_command(self, interaction: discord.Interaction):
        """Responds with a random yes or no answer."""
        if not await self.perms.interaction_check(interaction):
            return
        
        # Use true random from random.org
        await interaction.response.defer(thinking=True)
        
        params = {
            "num": 1,
            "min": 0,
            "max": 1,
            "col": 1,
            "base": 10,
            "format": "plain",
            "rnd": "new",
        }
        try:       
            async with self.api_command_semaphore:
                session = await self._get_session()
                async with session.get(self.random, params=params) as response:
                    if response.status == 200:
                        text = await response.text()
                        result = text.strip()
                        if result == "0":
                            answer = "No."
                        elif result == "1":
                            answer = "Yes."
                        else:
                            raise ValueError("Unexpected response from random.org")
                    else:
                        raise ValueError("Failed to get response from random.org")
                        
        except Exception as e:
            import random
            self.logger.error(f"Error in yes_no_command: {e}")
            answer = random.choice(["Yes.", "No."])
            await interaction.followup.send(f"*{answer}*")
            return
        
        await interaction.followup.send(f"*{answer}*")
        
            
class CommandsPlugin(Plugin):
    """Plugin class for Commands."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.cog = StaticCommands(self)
        self.at_everyone_cog = StaticCommandAtEveryoneCog(self)
        self.repeat_cog = StaticCommandRepeatCog(self)

    async def load(self) -> None:
        """Load the Commands plugin."""
        await self.fw.bot.add_cog(self.cog)
        await self.fw.bot.add_cog(self.at_everyone_cog)
        await self.fw.bot.add_cog(self.repeat_cog)

    async def unload(self) -> None:
        """Unload the Commands plugin."""
        await self.fw.bot.remove_cog(self.cog.qualified_name)
        await self.fw.bot.remove_cog(self.at_everyone_cog.qualified_name)
        await self.fw.bot.remove_cog(self.repeat.qualified_name)