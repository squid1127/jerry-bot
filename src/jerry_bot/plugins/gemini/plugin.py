"""Main Module for Gemini"""

from typing import Optional
import discord
from discord.ext import commands
from pathlib import Path

# squid_core imports
from squid_core import Plugin, PluginCog, Framework
from squid_core.decorators import DiscordEventListener

# Plugin imports
from .config import ConfigManager, GlobalConfig
from .core.manager import ConversationManager
from .provider import ProviderManager
from .interactions.cog import GeminiCog
from .models import Channel


class Gemini(Plugin):
    """Gemini Plugin."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.cog: Optional[GeminiCog] = None
        self.config_manager: Optional[ConfigManager] = None
        self.conversation_manager: Optional[ConversationManager] = None
        self.provider_manager = None

    async def preload(self):
        """Pre-load setup for Gemini Plugin."""
        self.config_manager = ConfigManager(
            config_path=self.config_path, logger=self.logger
        )
        await self.config_manager.load()

    async def load(self):
        """Load the Gemini Plugin."""
        if not self.config:
            raise ValueError(
                "Configuration not loaded before loading plugin. This should not happen."
            )

        self.provider_manager = ProviderManager(global_config=self.config)
        self.conversation_manager = ConversationManager(
            logger=self.logger,
            config=self.config,
            provider_manager=self.provider_manager,
        )
        self.cog = GeminiCog(
            plugin=self, conversation_manager=self.conversation_manager
        )

        await self.fw.bot.add_cog(self.cog)

    async def unload(self):
        """Unload the Gemini Plugin."""
        if self.cog:
            await self.fw.bot.remove_cog(self.cog.qualified_name)
        if self.conversation_manager:
            await self.conversation_manager.stop_all(drain=True)

    async def list_channels(self) -> list[Channel]:
        """List all channels with active conversations."""
        if not self.conversation_manager:
            self.logger.error("Conversation manager not initialized.")
            return []
        return await self.conversation_manager.list_channels()

    @DiscordEventListener()
    async def on_message(self, message: discord.Message):
        """Event listener for incoming messages to route them to the appropriate conversation."""
        if not self.conversation_manager:
            self.logger.error("Conversation manager not initialized.")
            return
        if message.author == self.fw.bot.user:
            return  # Ignore messages from the bot itself
        if not isinstance(message.channel, discord.TextChannel):
            return  # Ignore messages that are not from text channels

        allow_ephemeral = bool(self.config and self.config.ephemeral_mode.enabled)
        await self.conversation_manager.route_message(
            message=message,
            allow_ephemeral=allow_ephemeral,
            create_ephemeral=allow_ephemeral and self.is_mentioned(message),
        )

    @property
    def config_path(self) -> Path:
        """Get the path to the plugin's configuration file."""
        return self.fw.path / "plugins" / self.name / "config.yaml"

    @property
    def config(self) -> Optional[GlobalConfig]:
        """Get the current configuration."""
        return self.config_manager.config if self.config_manager else None

    def is_mentioned(self, message: discord.Message) -> bool:
        """Check if the bot is mentioned in the message."""
        return self.fw.bot.user in message.mentions
