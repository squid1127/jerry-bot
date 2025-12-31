"""Main Module for Gemini"""

from typing import Optional
import discord
from discord.ext import commands

# squid_core imports
from squid_core.plugin_base import Plugin, PluginCog
from squid_core.framework import Framework
from squid_core.decorators import DiscordEventListener
from squid_core.config_types import ConfigOption

# Plugin imports
from .models.config import GlobalConfig, InstanceConfig
from .models.gemini import MessagePart, MessageRole, DiscordContext, GeminiLLMConfig
from .instance import JerryGeminiInstance


class Gemini(Plugin):
    """Gemini Plugin."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.config: Optional[GlobalConfig] = None
        self.instances: dict[int, JerryGeminiInstance] = {}
        self.cog = GeminiCog(self)

    async def load(self):
        """Load the Gemini Plugin."""
        self.config = await self.fw.config.resolve_config(GlobalConfig, self)
        await self.fw.bot.add_cog(self.cog)
        await self.testing()  # For testing purposes only

    async def unload(self):
        """Unload the Gemini Plugin."""
        self.config = None
        await self.fw.bot.remove_cog(self.cog.qualified_name)
        
    async def testing(self):
        """Hardcoded instances for testing purposes."""
        if not self.config:
            return

        test_channel_id = await self.fw.config.get_config_option(ConfigOption(None, ['plugins', 'gemini', 'test_channel_id'], enforce_type=int, enforce_type_coerce=True), self)
        
        llm_config = GeminiLLMConfig(
            model_name="gemini-2.5-flash",
            temperature=2.0,
            top_p=0.9,
            chat_mode=True,
        )
        config = InstanceConfig(
            channel_id=test_channel_id,
            global_config=self.config,
            llm_config=llm_config
        )
        instance = JerryGeminiInstance(config=config, logger=self.logger)
        self.instances[test_channel_id] = instance


class GeminiCog(PluginCog):
    """Cog for Gemini Plugin to handle Discord events."""

    def __init__(self, plugin: Gemini):
        super().__init__(plugin)
        self.gemini_plugin: Gemini = plugin

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle incoming messages."""
        if message.author.bot:
            return  # Ignore messages from bots

        channel_id = message.channel.id
        instance = self.gemini_plugin.instances.get(channel_id)
        
        if not instance:
            return  # No Gemini instance for this channel

        # Make a message object
        discord_context = DiscordContext(
            message=message, channel=message.channel, user=message.author, guild=message.guild, interaction=None
        )
        msg_content = MessagePart(
            role=MessageRole.USER,
            content=message.content,
            discord=discord_context,
        )

        await instance.process_message(msg_content)
