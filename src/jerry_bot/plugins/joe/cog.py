"""Cog for the Joe plugin."""

import time

import discord
from squid_core import Plugin, PluginCog

from .models.config import JoePluginConfig

NamableChannel = discord.abc.GuildChannel


class JoeCog(PluginCog):
    """Main interface for the Joe plugin."""

    def __init__(self, plugin: Plugin, config: JoePluginConfig):
        super().__init__(plugin)
        self.config = config

        self.errors: dict[NamableChannel, float] = {}

    def inject_config(self, config: JoePluginConfig) -> None:
        """Replace the active configuration with a freshly loaded config."""
        self.config = config

    @PluginCog.listener()
    async def on_message(self, message: discord.Message):
        """Handles an incoming discord message"""

        if not self.config.enabled:
            return

        channel = message.channel
        guild = message.guild
        if guild is None or not isinstance(channel, NamableChannel):
            return

        name = self.get_names_for_channel(channel.id, message.author.id)

        if name is None or channel.name == name:
            return

        current_time = time.monotonic()
        last_error_time = self.errors.get(channel)
        if (
            last_error_time is not None
            and current_time - last_error_time < self.config.retry_period
        ):
            return

        try:
            self.plugin.logger.info(f"Renaming channel {channel.name} to {name}")
            await channel.edit(name=name)
        except (discord.HTTPException, discord.Forbidden):
            self.plugin.logger.exception(
                f"Could not rename channel {channel.name} to {name}"
            )
            self.errors[channel] = current_time

    def get_names_for_channel(self, channel_id: int, user_id: int) -> str | None:
        """Get the first matched name for a given channel, user, and guild"""

        entry = self.config.entries.get(user_id)
        if entry is None:
            return None
        return entry.get(channel_id)
