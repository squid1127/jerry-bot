"""Main Module for Gemini"""

from typing import Optional
import discord
from discord.ext import commands

# squid_core imports
from squid_core import Plugin, PluginCog, Framework
from squid_core.decorators import DiscordEventListener

# Plugin imports

class Gemini(Plugin):
    """Gemini Plugin."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.cog = GeminiCog(self)

    async def load(self):
        """Load the Gemini Plugin."""
        await self.fw.bot.add_cog(self.cog)

    async def unload(self):
        """Unload the Gemini Plugin."""
        await self.fw.bot.remove_cog(self.cog.qualified_name)

class GeminiCog(PluginCog):
    """Cog for Gemini Plugin to handle Discord events."""

    def __init__(self, plugin: Gemini):
        super().__init__(plugin)
        self.gemini_plugin: Gemini = plugin
