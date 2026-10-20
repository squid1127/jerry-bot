"""Main Plugin Module for Joe."""

from pathlib import Path
from typing import override

import discord
import yaml
from squid_core import CLIContext, EmbedLevel, Framework, Plugin
from squid_core.decorators import CLICommandDec

from .cog import JoeCog
from .models.config import JoePluginConfig
from .models.manager import ConfigManager


class JoePlugin(Plugin):
    """Rename channels when configured users speak."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.path: Path = self.get_working_directory()
        self.config_manager = ConfigManager(self.path / "config.yaml", self.logger)
        self.cog: JoeCog | None = None

    async def preload(self):
        """Load the Joe plugin configuration."""
        await self.config_manager.load()

    @override
    async def load(self):
        """Load the Joe plugin."""
        config = self.config
        if config is None:
            raise RuntimeError(
                "Configuration not loaded. Please run the preload method first."
            )
        if not config.enabled:
            self.logger.info("Joe plugin is disabled in the configuration.")
            return

        self.cog = JoeCog(self, config)
        await self.framework.bot.add_cog(self.cog)
        self.logger.info("Joe plugin loaded.")

    @override
    async def unload(self):
        """Unload the Joe plugin."""
        if self.cog is not None:
            await self.framework.bot.remove_cog(self.cog.qualified_name)
            self.cog = None
        self.logger.info("Joe plugin unloaded.")

    @property
    def config(self) -> JoePluginConfig | None:
        """Get the current Joe plugin configuration."""
        return self.config_manager.config

    @CLICommandDec(
        name="joe",
        description="Reload Joe plugin config and get channel mappings",
    )
    async def helper_command(self, ctx: CLIContext):
        """Helper CLI command for fetching channel names"""

        if ctx.args and ctx.args[0] == "reload":
            try:
                config = await self.config_manager.load()
            except (OSError, TypeError, ValueError, yaml.YAMLError) as error:
                await ctx.respond_exception("Joe Configuration Reload Failed", error)
                return

            if self.cog is not None:
                self.cog.inject_config(config)
                description = "Successfully reloaded the Joe plugin configuration."
            else:
                description = (
                    "Configuration reloaded, but the Joe plugin is not active. "
                    "The setting will take effect when the plugin is loaded."
                )

            await ctx.respond(
                title="Joe Configuration Reloaded",
                description=description,
                level=EmbedLevel.SUCCESS,
            )
            return

        guilds: list[discord.Guild] = []
        for arg in ctx.args:
            try:
                guild_id = int(arg)
            except ValueError:
                continue

            guild = self.fw.bot.get_guild(guild_id)
            if guild:
                guilds.append(guild)

        if not guilds:
            await ctx.respond(
                "Usage: joe reload\n"
                "Reload the Joe plugin configuration.\n\n"
                "Or provide one or more guild IDs separated by spaces to generate "
                "channel-to-name mappings as YAML.",
                "Missing Guild IDs",
                level=EmbedLevel.ERROR,
            )
            return

        channels: dict[str, str] = {}
        for guild in guilds:
            for channel in guild.channels:
                if isinstance(channel, discord.CategoryChannel):
                    continue
                channels[str(channel.id)] = channel.name

        content = yaml.safe_dump(channels, indent=4)
        await ctx.respond(
            f"```yaml\n{content}\n```",
            f"Mapping for {len(guilds)} guild{'s' if len(guilds) != 1 else ''}",
            level=EmbedLevel.INFO,
        )
