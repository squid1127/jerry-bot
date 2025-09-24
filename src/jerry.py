"""
Jerry-Bot
~~~~~~~~~~~~~~~~~~~
The bot designed specifically for LBUSD Drone Soccer Discord and other of squid1127's personal servers.

:license: MIT, see LICENSE for more details.
"""

# Packages & Imports
# Discord Packages
import discord

# Async Packages
import asyncio

# Pillow HEIF support
import pillow_heif
pillow_heif.register_heif_opener()  # Register the HEIF opener to process HEIF images

# System
import sys

# Core bot
import core  # Core bot (https://github.com/squid1127/squid-core)

# Jerry cogs
import cogs

# Logging
import logging

logger = logging.getLogger("jerry")


class Jerry(core.Bot):
    def __init__(
        self,
        discord_token: str,
        shell_channel: int,
        memory: core.Memory = None,
        **kwargs,
    ):
        # Initialize the bot
        super().__init__(
            token=discord_token, name="jerry", shell_channel=shell_channel, memory=memory, **kwargs
        )

        # Confgure random status
        statuses = [
            discord.CustomActivity("Nuh-uh ❌", emoji="❌"),
            discord.CustomActivity("Yuh-uh ✅", emoji="✅"),
        ]
        self.set_status(random_status=statuses)

    # Load cogs
    async def load_cogs(self):
        await super().load_cogs()
        await self.add_cog(cogs.JerryGemini(self))
        await self.add_cog(cogs.InformationChannels(self))
        # await self.add_cog(cogs.CubbScratchStudiosStickerPack(self, "communal/css_stickers"))
        await self.add_cog(cogs.Stickers(self))
        await self.add_cog(cogs.StaticCommands(self))
        await self.add_cog(cogs.SimpleUpdate(self))
        await self.add_cog(cogs.AutoReply(self))
        await self.add_cog(cogs.MusicCog(self))


    JERRY_RED = 0xFF5C5C


if __name__ == "__main__":
    print("Run app.py to start the bot.")
    sys.exit(1)
