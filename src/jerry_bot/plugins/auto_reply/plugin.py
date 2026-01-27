"""Main Module for AutoReply"""

# squid_core imports
import asyncio
import re
from squid_core.plugin_base import Plugin
from squid_core.framework import Framework
from squid_core.decorators import DiscordEventListener, CLICommandDec, RedisSubscribe
from squid_core.components.cli import CLIContext, EmbedLevel

# third-party imports
import discord, yaml, random, datetime, math, asteval
import jinja2

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
        
        if message.author.bot:
            return  # Ignore messages from bots

        # Optimized ignore check - check once instead of twice
        if self.ar.check_ignored(
            channel_id=message.channel.id,
            user_id=message.author.id,
            guild_id=message.guild.id if message.guild else None,
            role_ids=[role.id for role in message.author.roles] if message.guild else None,
        ):
            return  # Ignore this message
            
        # Content
        content = message.content
        try:
            content = self.ar.reverse_template(content, author=message.author)
        except Exception as e:
            self.logger.error(f"Error reversing templates in message content: {e}")

        found = 0
        for rule in self.ar.cache:
            if rule.match(content):
                await self.ar.send_response(message, rule)
                found += 1

        if found > 0:
            self.logger.info(
                f"Auto-replied {found} times in response to message ID {message.id}."
            )

    @CLICommandDec(
        "autoreply",
        aliases=["ar", "auto_reply"],
        description="Manage AutoReply plugin settings and rules.",
    )
    async def cli_autoreply(self, ctx: CLIContext):
        """CLI command to manage AutoReply plugin."""

        ui = AutoReplyMainUI(ar=self.ar, message_method=ctx.message.reply)
        await ui.render()

    @RedisSubscribe(["jerry:auto_reply:reload_cache"])
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