"""Main Plugin Module for Text-to-Speech."""

from squid_core import Plugin, PluginCog, Framework
from squid_core.decorators import CLICommandDec, RedisSubscribe

import discord
from discord import app_commands
import asyncio
from pathlib import Path

from .client import TTSSocketClient
from .cog import TTSCog
from .models.manager import ConfigManager, TTSPluginConfig
from .runner import TTSServiceRunner

class TTSPlugin(Plugin):
    """Text-to-Speech Plugin for Jerry Bot."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.path: Path = self.get_working_directory()
        self.config_manager: ConfigManager = ConfigManager(self.path / "config.yaml", self.logger)
        self.service_runner: TTSServiceRunner | None = None
        
        self.socket_client: TTSSocketClient|None = None
        self.cog: TTSCog|None = None

        
    async def preload(self):
        """Preload the Text-to-Speech Plugin."""
        await self.config_manager.load()

        
    async def load(self):
        """Load the Text-to-Speech Plugin."""
        self.logger.info("Text-to-Speech initializing...")

        if self.config is None:
            raise RuntimeError("Configuration not loaded. Please run the preload method first.")
        if not self.config.enabled:
            self.logger.info("Text-to-Speech plugin is disabled in the configuration.")
            return

        cwd = self.config.service.cwd if self.config.service.cwd else self.path
        socket_path = self.config.socket_path if self.config.socket_path.is_absolute() else cwd / self.config.socket_path
        output_dir = self.config.output_dir if self.config.output_dir.is_absolute() else cwd / self.config.output_dir
        
        self.socket_client = TTSSocketClient(socket_path, self.logger)
        self.cog = TTSCog(self, self.socket_client, output_dir, self.config)
        if self.config.service.use:
            self.service_runner = TTSServiceRunner(self.config, cwd)
            self.logger.info("Starting TTS service... with command: %s", self.service_runner.command)
            await self.service_runner.start()
            await self.service_runner.wait_for_ready()
            self.logger.info("TTS service started and ready.")

        await self.cog.socket_client.connect()
        await self.framework.bot.add_cog(self.cog)

    async def unload(self):
        """Unload the Text-to-Speech Plugin."""
        self.logger.info("Text-to-Speech unloading...")
        if self.cog:
            await self.framework.bot.remove_cog(self.cog.qualified_name)
        if self.socket_client:
            await self.socket_client.disconnect()
        if self.service_runner:
            await self.service_runner.stop()

    @property
    def config(self):
        """Get the current configuration for the Text-to-Speech Plugin."""

        return self.config_manager.config
