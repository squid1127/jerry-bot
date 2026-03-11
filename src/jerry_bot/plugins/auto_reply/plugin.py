"""Main Module for AutoReply"""

# squid_core imports
import asyncio
import re
from squid_core.plugin_base import Plugin
from squid_core.framework import Framework
from squid_core.decorators import DiscordEventListener, CLICommandDec, RedisSubscribe
from squid_core.components.cli import CLIContext, EmbedLevel

# other imports
import discord
from typing import Optional, TYPE_CHECKING

# plugin integration imports
if TYPE_CHECKING:
    from ..gemini import Gemini as GeminiPlugin
    from ..gemini.models import Channel as GeminiChannel, Guild as GeminiGuild

# local imports
from .models.db import (
    AutoReplyRule,
    AutoReplyRuleData,
    AutoReplyIgnore,
    AutoReplyIgnoreData,
)
from .models.enums import IgnoreType, ResponseType
from .cog import AutoReplyCog
from .ui import AutoReplyMainUI
from .ar import AutoReply

class AutoReplyPlugin(Plugin):
    """AutoReply Plugin."""

    def __init__(self, framework: Framework):
        super().__init__(framework)

        self.auto_reply = AutoReply(self)
        self.cog = AutoReplyCog(self, self.ar)
        
    @property
    def ar(self) -> AutoReply:
        return self.auto_reply
    
    async def load(self):
        """Load the AutoReply Plugin."""
        await self.ar.init()
        await self.framework.bot.add_cog(self.cog)
        self.logger.info("AutoReply plugin loaded.")

    async def unload(self):
        """Unload the AutoReply Plugin."""
        await self.framework.bot.remove_cog(self.cog.qualified_name)
        self.logger.info("AutoReply plugin unloaded.")

    @DiscordEventListener()
    async def on_message(self, message: discord.Message):
        """Handle incoming messages and respond if they match any auto-reply rules."""
        try:
            if message.author.bot:
                return  # Ignore messages from bots


            # Optimized ignore check - check once instead of twice
            if self.ar.check_ignored(
                channel_id=message.channel.id,
                user_id=message.author.id,
                guild_id=message.guild.id if message.guild else None, # type: ignore
                role_ids=[role.id for role in message.author.roles] if message.guild else None, # type: ignore
            ):
                return  # Ignore this message
                
            # Content
            content = message.content
            try:
                content = self.ar.reverse_template(content, author=message.author)
            except Exception as e:
                self.logger.debug(f"Error reversing templates in message content: {e}")

            found = 0
            for rule in self.ar.cache:
                try:
                    if rule.match(content):
                        await self.ar.send_response(message, rule)
                        found += 1
                except Exception as e:
                    self.logger.error(
                        f"Error processing rule {rule.db_id} for message {message.id}: {e}",
                        exc_info=True
                    )

            if found > 0:
                self.logger.debug(
                    f"Auto-replied {found} times in response to message ID {message.id}."
                )
        except Exception as e:
            self.logger.error(f"Unexpected error in on_message handler: {e}", exc_info=True)

    @CLICommandDec(
        "autoreply", # type: ignore - squid core decorators break typing somehow
        aliases=["ar", "auto_reply"],
        description="Manage AutoReply plugin settings and rules.",
    )
    async def cli_autoreply(self, ctx: CLIContext):
        """CLI command to manage AutoReply plugin."""
        
        # Type checking got mad somehow
        if ctx.message is None:
            raise ValueError("CLIContext message is None. This command must be invoked with a message context.")
        
        try:
            ui = AutoReplyMainUI(ar=self.ar, message_method=ctx.message.reply)
            await ui.render()
        except Exception as e:
            self.logger.error(f"Error rendering AutoReply UI: {e}", exc_info=True)
            await ctx.message.reply(
                embed=discord.Embed(
                    title="Error",
                    description="Failed to open AutoReply management interface. Please try again.",
                    color=discord.Color.red(),
                )
            )

    @RedisSubscribe(["jerry:auto_reply:reload_cache"])  # type: ignore - squid core decorators break typing somehow
    async def redis_reload_cache(self, message: dict):
        """Handle Redis message to reload cache."""
        
        await self.ar.load_cache()
        self.logger.info("AutoReply cache reloaded via Redis message.")
        
        # Send confirmation back if reply_to is specified
        if not isinstance(message, dict):
            return
        if "reply_to" in message:
            await self.framework.redis.publish(
                message["reply_to"],
                {
                    "status": "success",
                    "message": "AutoReply cache reloaded.",
                    "rule_count": len(self.ar.cache),
                    "ignore_count": len(self.ar.ignore_cache),
                },
            )
            
    # Due to current limitations, this can't be down reliably on_load, since there isn't dependency injection or guaranteed load order. Instead, we'll listen for on_ready and then check if the gemini plugin is loaded, and if so, fetch the channels and add them to the ignore list.
    @DiscordEventListener() # type: ignore - squid core decorators break typing somehow
    async def on_ready(self):
        """Handle bot ready event to integrate with Gemini plugin if available."""
        try:
            await self.gemini_integration()
        except Exception as e:
            self.logger.error(f"Error during Gemini integration: {e}", exc_info=True)
    
    async def gemini_integration(self):
        """Fetch channels from jerry-gemini plugin (if available) and ignore them in auto-reply."""
        
        gemini_plugin : GeminiPlugin | None = await self.framework.plugins.get_plugin("jerry:gemini") # type: ignore

        if gemini_plugin is None:
            self.logger.info("jerry-gemini plugin not found, skipping Gemini integration.")
            return
        if  type(gemini_plugin).__name__ != "Gemini":
            self.logger.info("jerry-gemini plugin of invalid type, skipping Gemini integration.")
            return
        
        channels: list[GeminiChannel] = await gemini_plugin.list_channels()
        for channel in channels:
            guild: GeminiGuild | None = await channel.guild
            ignore = AutoReplyIgnore(
                guild_id=guild.guild_id if guild else None,
                discord_type=IgnoreType.CHANNEL,
                discord_id=channel.channel_id,
            )
            self.logger.info(
                f"Adding auto-reply ignore for jerry-gemini channel {channel.channel_id} (guild: {guild.guild_id if guild else 'N/A'})"
            )
            await ignore.save()