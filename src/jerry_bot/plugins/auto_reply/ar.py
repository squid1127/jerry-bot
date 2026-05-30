"""Auto Reply Component for AR Plugin"""

import discord
from squid_core import Framework, Plugin

from .jinja_manager import JinjaManager
from .models.db import (
    AutoReplyIgnore,
    AutoReplyRule,
    AutoReplyIgnoreData,
    AutoReplyRuleData,
)
from .models.enums import IgnoreType
from .response_handler import ResponseHandler


class AutoReply:
    """Auto Reply Component for AR Plugin."""

    def __init__(self, plugin: Plugin):
        self.plugin = plugin
        self.cache: list[AutoReplyRuleData] = []
        self.ignore_cache: dict[
            tuple[int | None, IgnoreType, int], AutoReplyIgnoreData
        ] = {}
        self.jinja_manager = JinjaManager(plugin)
        self.response_handler = ResponseHandler(
            plugin, self.jinja_manager, plugin.framework.cli
        )

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
        self.ignore_cache = {
            (
                int(ignore.guild_id) if ignore.guild_id else None,
                ignore.discord_type,
                int(ignore.discord_id),
            ): ignore.as_dataclass()
            for ignore in ignores
        }

        self.plugin.logger.info(
            f"Loaded {len(self.cache)} auto-reply rules and {len(self.ignore_cache)} ignores into cache."
        )

    def check_ignored(
        self,
        channel_id: int | None = None,
        user_id: int | None = None,
        guild_id: int | None = None,
        role_ids: list[int] | None = None,
    ) -> bool:
        """Check if a message should be ignored based on channel, user, guild, or role ID."""
        role_ids = role_ids or []
        ignore_checks: list[tuple[int | None, IgnoreType, int | None]] = [
            (None, IgnoreType.USER, user_id),
        ]

        if guild_id:
            ignore_checks.extend(
                [
                    (guild_id, IgnoreType.USER, user_id),
                    (guild_id, IgnoreType.CHANNEL, channel_id),
                    (None, IgnoreType.GUILD, guild_id),
                ]
            )
            ignore_checks.extend(
                [(guild_id, IgnoreType.ROLE, r_id) for r_id in role_ids]
            )

        return any(check in self.ignore_cache for check in ignore_checks if check[2])

    def reverse_template(
        self, text: str, author: discord.User | discord.Member | None = None
    ) -> str:
        """Reverse built-in templates to their placeholders."""
        bot = self.framework.bot.user
        if bot:
            text = text.replace(bot.mention, "{bot_mention}")
        if author:
            text = text.replace(author.mention, "{author_mention}")
        return text

    async def send_response(self, message: discord.Message, rule: AutoReplyRuleData):
        """Send a response based on the rule's response type."""
        await self.response_handler.send_response(message, rule)

    async def set_rule(
        self,
        rule: AutoReplyRule,
    ):
        """Create or update an auto-reply rule in the database and refresh cache."""
        await rule.save()
        await self.load_cache()
