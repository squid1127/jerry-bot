"""Main Module for Gemini"""

from typing import Optional
import discord
from pathlib import Path

# squid_core imports
from squid_core import Plugin, Framework
from squid_core.decorators import DiscordEventListener

# Plugin imports
from .config import ConfigManager, GlobalConfig
from .core import ConversationManager, UIService
from .dc_chat import InputProcessor, OutputContext

from .dc_config.cog import GeminiCog
from .models import Channel
from .repo import (
    Repositories,
    ChannelRepository,
    GuildRepository,
    LLMProfileRepository,
    ProviderRegistry,
)


class Gemini(Plugin):
    """Gemini Plugin."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.cog: Optional[GeminiCog] = None
        self.ui_service: Optional[UIService] = None
        self.config_manager: Optional[ConfigManager] = None
        self.conversation_manager: Optional[ConversationManager] = None
        self.repos: Optional[Repositories] = None
        self.input_processor = InputProcessor()

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

        repos = await self.init_repos()
        self.conversation_manager = ConversationManager(
            logger=self.logger,
            repos=repos,
            bot=self.fw.bot,
        )
        self.ui_service = UIService(
            repos=repos, conversation_manager=self.conversation_manager
        )
        self.cog = GeminiCog(
            plugin=self,
            ui_service=self.ui_service,
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
        if not self.repos:
            self.logger.error("Repositories not initialized.")
            return []
        return await self.repos.channel_repo.get_all()

    async def init_repos(self) -> Repositories:
        """Initialize the repository context for the plugin."""
        if not self.config:
            raise ValueError(
                "Configuration not loaded before initializing repositories. This should not happen."
            )

        self.repos = Repositories(
            channel_repo=ChannelRepository(),
            guild_repo=GuildRepository(),
            llm_profile_repo=LLMProfileRepository(),
            provider_registry=ProviderRegistry(self.config),
            global_config=self.config,
        )
        await self.repos.channel_repo.load_all()
        await self.repos.guild_repo.load_all()
        await self.repos.llm_profile_repo.load_all()
        return self.repos

    @DiscordEventListener()
    async def on_message(self, message: discord.Message):
        """Event listener for incoming messages to route them to the appropriate conversation."""
        if not self.conversation_manager:
            self.logger.error("Conversation manager not initialized.")
            return
        if not self.input_processor:
            self.logger.error("Input processor not initialized.")
            return
        if message.author == self.fw.bot.user:
            return  # Ignore messages from the bot itself
        if not isinstance(message.channel, discord.TextChannel):
            return  # Ignore messages that are not from text channels
        if not message.guild:
            return  # Ignore messages that are not from guilds

        allow_ephemeral = bool(self.config and self.config.ephemeral_mode.enabled)
        await self.conversation_manager.route_message(
            message=self.input_processor.process(message),
            channel_id=message.channel.id,
            allow_ephemeral=allow_ephemeral,
            create_mentionable=self.is_mentioned(message),
            quiet=True,
            output_context=OutputContext(channel=message.channel, guild=message.guild),
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
