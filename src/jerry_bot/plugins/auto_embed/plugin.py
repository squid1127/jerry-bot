"""Main plugin file for AutoEmbed plugin."""

from squid_core.plugin_base import Plugin as PluginBase, PluginCog
from squid_core.framework import Framework

from enum import Enum
import aiohttp, bs4
import asyncio

import discord
from discord import app_commands

from .interactions import AutoEmbedInputForm

class AutoEmbedPlugin(PluginBase):
    """Plugin class for AutoEmbed."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.cog = AutoEmbedCog(self)

    async def load(self) -> None:
        """Load the AutoEmbed plugin."""
        await self.fw.bot.add_cog(self.cog)

    async def unload(self) -> None:
        """Unload the AutoEmbed plugin."""
        await self.fw.bot.remove_cog(self.cog.__class__.__name__)


class AutoEmbedCog(PluginCog):
    """
    Cog class for AutoEmbed.
    """

    def __init__(self, plugin: AutoEmbedPlugin):
        self.plugin: AutoEmbedPlugin = plugin
        self.bot = plugin.fw.bot
        self.logger = plugin.logger
        
    @app_commands.command(name="auto-embed", description="Create and send a discord embed automatically.")
    async def auto_embed_command(self, interaction: discord.Interaction) -> None:
        """Handle the /auto-embed command."""
        form = AutoEmbedInputForm()
        await interaction.response.send_modal(form)