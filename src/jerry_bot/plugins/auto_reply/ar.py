"""Auto Reply Component for AR Plugin"""

# Why are there so many imports? :)
import jinja2
import discord
import yaml
import random
import datetime
import math
import re
import asteval

from squid_core import Plugin, Framework

from .models.db import AutoReplyIgnore, AutoReplyRule, AutoReplyIgnoreData, AutoReplyRuleData
from .models.enums import IgnoreType, ResponseType

class AutoReply:
    """Auto Reply Component for AR Plugin."""

    def __init__(self, plugin: Plugin):
        self.plugin = plugin
        
        self.cache: list[AutoReplyRuleData] = []
        self.ignore_cache: dict[int, AutoReplyIgnoreData] = {}
        self.jinja_env = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            enable_async=True,
            autoescape=True,
        )
        self.jinja_env.globals.update(self.make_globals())
        
    @property
    def fw(self) -> Framework:
        return self.plugin.framework
    @property
    def framework(self) -> Framework:
        return self.plugin.framework
    
    async def init(self):
        """Initialize the Auto Reply component."""
        await self.load_cache()

    async def load_cache(self):
        """Load rules and ignores into memory cache."""
        rules = await AutoReplyRule.all()
        self.cache = [rule.as_dataclass() for rule in rules if rule.is_active]

        ignores = await AutoReplyIgnore.all()
        # Use composite key (guild_id or None, type, id) for guild-specific and global ignores
        self.ignore_cache = {
            (int(ignore.guild_id) if ignore.guild_id else None, ignore.discord_type, int(ignore.discord_id)): ignore.as_dataclass() 
            for ignore in ignores
        }

        self.plugin.logger.info(
            f"Loaded {len(self.cache)} auto-reply rules and {len(self.ignore_cache)} ignores into cache."
        )

    def check_ignored(
        self, channel_id: int = None, user_id: int = None, guild_id: int = None, role_ids: list[int] = None
    ) -> bool:
        """Check if a message should be ignored based on channel, user, guild, or role ID.
        Checks both global ignores (guild_id=None) and guild-specific ignores.
        """
        # Check global ignores first (guild_id=None)
        if user_id and (None, IgnoreType.USER, user_id) in self.ignore_cache:
            return True
        if channel_id and (None, IgnoreType.CHANNEL, channel_id) in self.ignore_cache:
            return True
        if role_ids and any((None, IgnoreType.ROLE, role_id) in self.ignore_cache for role_id in role_ids):
            return True
        
        # Check guild-specific ignores if guild_id is provided
        if guild_id:
            if user_id and (guild_id, IgnoreType.USER, user_id) in self.ignore_cache:
                return True
            if channel_id and (guild_id, IgnoreType.CHANNEL, channel_id) in self.ignore_cache:
                return True
            if (None, IgnoreType.GUILD, guild_id) in self.ignore_cache:
                return True
            if role_ids and any((guild_id, IgnoreType.ROLE, role_id) in self.ignore_cache for role_id in role_ids):
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
            self.plugin.logger.error(f"Error parsing response payload as YAML: {e}")
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
    
    def make_globals(self) -> dict:
        """Create global variables for Jinja2 templates."""
        def regex_match(pattern: str, string: str) -> bool:
            """Check if the regex pattern matches the string."""
            return re.search(pattern, string) is not None
        
        def ordinal(n: int) -> str:
            """Convert an integer to its ordinal representation."""
            suffix = ["th", "st", "nd", "rd"] + ["th"] * 6
            if 10 <= n % 100 <= 20:
                return f"{n}th"
            else:
                return f"{n}{suffix[n % 10]}"
            
        self.asteval = asteval.Interpreter()
        def asteval_eval(expr: str):
            """Evaluate a mathematical expression safely."""
            try:
                result = self.asteval(expr)
            except Exception as e:
                raise ValueError(f"Error evaluating expression: {e}")
            
            # Check for errors
            if self.asteval.error:
                error_msg = "; ".join([str(err.get_error()) for err in self.asteval.error])
                raise ValueError(f"Error evaluating expression: {error_msg}")
            
            return result
        
        bot = self.framework.bot
        now = datetime.datetime.utcnow()
        globals_dict = {
            "bot": bot,
            "now": now,
            "utcnow": now,
            "math": math,
            "randint": random.randint,
            "randchoice": random.choice,
            "random": random,
            "regex_match": regex_match,
            "ordinal": ordinal,
            "asteval": asteval_eval,
        }
        return globals_dict
    
    async def render_jinja_template(self, template_str: str, **context) -> str:
        """Render a Jinja2 template string with the provided context."""
        try:
            template = self.jinja_env.from_string(template_str)
            rendered = await template.render_async(**context)
            return rendered
        except jinja2.TemplateError as e:
            self.plugin.logger.error(f"Jinja2 template rendering error: {e}")
            return template_str  # Fallback to original string on error
        except Exception as e:
            self.plugin.logger.error(f"Unexpected error during Jinja2 rendering: {e}")
            return template_str  # Fallback to original string on error

    async def send_response(self, message: discord.Message, rule: AutoReplyRuleData):
        """Send a response based on the rule's response type."""
        if rule.response_type == ResponseType.TEXT:
            response_templated = self.auto_template(rule.response_payload, author=message.author)
            await message.reply(response_templated)
        elif rule.response_type == ResponseType.TEXT_TEMPLATE:
            response_rendered = await self.render_jinja_template(
                rule.response_payload,
                content = message.content,
                author=message.author,
                message=message,
                channel=message.channel,
                guild=message.guild,
                bot=self.framework.bot,
            )
            response_templated = self.auto_template(response_rendered, author=message.author)
            if len(response_templated) == 0:
                await message.reply(
                    embed=discord.Embed(
                        title="Error",
                        description="The rendered template resulted in an empty response.",
                    ).set_footer(
                        text="If you are a bot admin, please check the auto-reply rule configuration."
                    )
                )
                return
            elif len(response_templated) > 2000:
                response_templated = response_templated[:1997] + "..."
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
                self.plugin.logger.error(f"Failed to add reaction: {e}")
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
            
    async def set_rule(
        self,
        rule: AutoReplyRule,
    ):
        """Create or update an auto-reply rule in the database and refresh cache."""
        await rule.save()
        await self.load_cache()