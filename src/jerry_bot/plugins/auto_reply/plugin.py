"""Main Module for AutoReply"""

# squid_core imports
import asyncio
from squid_core.plugin_base import Plugin
from squid_core.framework import Framework
from squid_core.decorators import DiscordEventListener, CLICommandDec, RedisSubscribe
from squid_core.components.cli import CLIContext, EmbedLevel

# third-party imports
import discord, yaml, random

# local imports
from .models.db import (
    AutoReplyRule,
    AutoReplyRuleData,
    AutoReplyIgnore,
    AutoReplyIgnoreData,
)
from .models.enums import IgnoreType, ResponseType
from .editor import SearchView, SearchSelect


class AutoReply(Plugin):
    """AutoReply Plugin."""

    def __init__(self, framework: Framework):
        super().__init__(framework)

        self.cache: list[AutoReplyRuleData] = []
        self.ignore_cache: dict[int, AutoReplyIgnoreData] = {}

    async def load(self):
        """Load the AutoReply Plugin."""
        await self.load_cache()
        self.logger.info("AutoReply plugin loaded.")

    async def unload(self):
        """Unload the AutoReply Plugin."""
        self.logger.info("AutoReply plugin unloaded.")

    async def load_cache(self):
        """Load rules and ignores into memory cache."""
        rules = await AutoReplyRule.all()
        self.cache = [rule.as_dataclass() for rule in rules if rule.is_active]

        ignores = await AutoReplyIgnore.all()
        self.ignore_cache = {
            int(ignore.discord_id): ignore.as_dataclass() for ignore in ignores
        }

        self.logger.info(
            f"Loaded {len(self.cache)} auto-reply rules and {len(self.ignore_cache)} ignores into cache."
        )

    def check_ignored(
        self, channel_id: int = None, user_id: int = None, guild_id: int = None
    ) -> bool:
        """Check if a message should be ignored based on channel, user, or guild ID."""
        if user_id and user_id in self.ignore_cache:
            ignore = self.ignore_cache[user_id]
            if ignore.discord_type == IgnoreType.USER:
                return True
        if channel_id and channel_id in self.ignore_cache:
            ignore = self.ignore_cache[channel_id]
            if ignore.discord_type == IgnoreType.CHANNEL:
                return True
        if guild_id and guild_id in self.ignore_cache:
            ignore = self.ignore_cache[guild_id]
            if ignore.discord_type == IgnoreType.GUILD:
                return True
        return False

    def choose_random(self, response_payload: str) -> str:
        """Choose a random response from a newline-separated list."""
        # Parse as YAML to handle multi-line strings properly
        try:
            responses = yaml.safe_load(response_payload)
            if isinstance(responses, list) and responses:
                return random.choice(responses)
            else:
                raise ValueError("Response payload is not a valid list.")
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing response payload as YAML: {e}")
            raise ValueError("Invalid YAML format.")

    def auto_template(self, text: str, author: discord.User = None) -> str:
        """Define built-in templates for auto-reply responses."""

        # Bot user mention
        bot = self.framework.bot.user
        if bot:
            text = text.replace("{bot_mention}", bot.mention)

        # Author mention
        if author:
            text = text.replace("{author_mention}", author.mention)

        return text
    
    def reverse_template(self, text: str, author: discord.User = None) -> str:
        """Reverse built-in templates to their placeholders."""

        # Bot user mention
        bot = self.framework.bot.user
        if bot:
            text = text.replace(bot.mention, "{bot_mention}")

        # Author mention
        if author:
            text = text.replace(author.mention, "{author_mention}")

        return text

    async def send_response(self, message: discord.Message, rule: AutoReplyRuleData):
        """Send a response based on the rule's response type."""
        if rule.response_type == ResponseType.TEXT:
            response_templated = self.auto_template(rule.response_payload, author=message.author)
            await message.reply(response_templated)
        elif rule.response_type == ResponseType.TEXT_RANDOM:
            try:
                response = self.choose_random(rule.response_payload)
                response_templated = self.auto_template(response, author=message.author)
                await message.reply(response_templated)
            except ValueError:
                await message.reply(
                    embed=discord.Embed(
                        title="Error",
                        description="Failed to parse random text responses.",
                    ).set_footer(
                        text="If you are a bot admin, please check the auto-reply rule configuration."
                    )
                )
        elif rule.response_type == ResponseType.STICKER:
            await message.reply(
                embed=discord.Embed(
                    title="Error",
                    description="Sticker responses are not supported in this implementation.",
                ).set_footer(text="If you are a bot admin, please remove this rule.")
            )
        elif rule.response_type == ResponseType.REACTION:
            try:
                emoji = rule.response_payload.strip()
                await message.add_reaction(emoji)
            except Exception as e:
                self.logger.error(f"Failed to add reaction: {e}")
                await message.reply(
                    embed=discord.Embed(
                        title="Error",
                        description="Failed to add reaction. Please ensure the emoji is valid and the bot has permission to use it.",
                    ).set_footer(
                        text="If you are a bot admin, please check the auto-reply rule configuration."
                    )
                )
        else:
            await message.reply(
                embed=discord.Embed(
                    title="Error", description="Unknown response type configured."
                ).set_footer(
                    text="If you are a bot admin, please check the auto-reply rules."
                )
            )

    @DiscordEventListener("on_message")
    async def handle_message(self, message: discord.Message):
        """Handle incoming messages and respond if they match any auto-reply rules."""
        if message.author.bot:
            return  # Ignore messages from bots

        # Optimized ignore check - check once instead of twice
        if self.check_ignored(
            channel_id=message.channel.id,
            user_id=message.author.id,
            guild_id=message.guild.id,
        ):
            return  # Ignore this message
            
        # Content
        content = message.content
        try:
            content = self.reverse_template(content, author=message.author)
        except Exception as e:
            self.logger.error(f"Error reversing templates in message content: {e}")

        found = 0
        for rule in self.cache:
            if rule.match(content):
                await self.send_response(message, rule)
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

        if len(ctx.args) == 0:
            await ctx.respond(
                "AutoReply Plugin CLI\nAvailable subcommands: `reload`, `rule`",
                title="AutoReply CLI",
                level=EmbedLevel.INFO,
            )
            return

        subcommand = ctx.args[0].lower()

        if subcommand == "reload":
            await self.load_cache()
            await ctx.respond(
                f"Reloaded AutoReply cache with {len(self.cache)} rules and {len(self.ignore_cache)} ignores.",
                title="AutoReply Cache Reloaded",
                level=EmbedLevel.SUCCESS,
            )
        elif subcommand == "rule":
            if len(ctx.args) > 1:
                query = " ".join(ctx.args[1:])

                # Search for rules matching the query
                matching_rules = []
                if query:
                    for rule in self.cache:
                        # Check if trigger or payload is similar (without regex)
                        if (
                            query.lower() in rule.trigger.lower()
                            or query.lower() in rule.response_payload.lower()
                        ):
                            matching_rules.append(rule)

                        # Check if trigger regex matches
                        elif rule.match(query):
                            matching_rules.append(rule)

                # If too many results, limit to first 20
                if len(matching_rules) > 20:
                    matching_rules = matching_rules[:20]
            else:
                matching_rules = self.cache if 20 > len(self.cache) > 0 else None

            view = SearchView(plugin=self, search_results=matching_rules)
            message = await ctx.message.reply(
                embed=discord.Embed(
                    description="Just a sec...", color=discord.Color.blue()
                )
            )
            await asyncio.sleep(
                0.5
            )  # Small delay to ensure message is sent before editing
            await view.init_message(message)
        else:
            await ctx.respond(
                f"Unknown subcommand '{subcommand}'. Available subcommands: `reload`, `rule`",
                title="Command Not Found",
                level=EmbedLevel.ERROR,
            )

    @RedisSubscribe(["reload_cache"])
    async def redis_reload_cache(self, message: dict):
        """Handle Redis message to reload cache."""
        
        await self.load_cache()
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
                    "rule_count": len(self.cache),
                    "ignore_count": len(self.ignore_cache),
                },
            )