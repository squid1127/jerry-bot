"""Database Models and Types for AutoReply Plugin"""

from collections.abc import Sequence
from tortoise import fields
from tortoise.models import Model
from tortoise.expressions import Q
from dataclasses import dataclass, field
import re
from functools import cached_property
from math import ceil

from .enums import ResponseType, IgnoreType, ResponseMethod


class AutoReplyRule(Model):
    """Model representing an auto-reply rule.

    Attributes:
        name (str): The name of the auto-reply rule.
        trigger (str): The trigger regex for the auto-reply.
        response_type (ResponseType): The type of response (text, image, etc.).
        response_method (ResponseMethod): The method for generating the response (reply, log, etc.).
        response_payload (str): The content of the response.
        is_active (bool): Whether the rule is active.
    """

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    trigger = fields.TextField()
    response_type = fields.IntEnumField(ResponseType)
    response_method = fields.IntEnumField(ResponseMethod)
    response_payload = fields.TextField()
    is_active = fields.BooleanField(default=True)

    class Meta:  # type: ignore
        table = "jerry_auto_reply_rules"
        ordering = ["id"]

    def as_dataclass(self) -> "AutoReplyRuleData":
        """Convert to dataclass representation for in-memory operations."""
        return AutoReplyRuleData(
            db_id=self.id,
            trigger=self.trigger,
            response_type=self.response_type,
            response_method=self.response_method,
            response_payload=self.response_payload,
            is_active=self.is_active,
        )

    @classmethod
    def _get_query_method(cls, search_query: str | None):
        if search_query is None:
            return cls.all()
        try:
            if search_query.startswith("id="):
                search_query_int = int(search_query[3:])
            else:
                search_query_int = int(search_query)
            return cls.filter(
                Q(name__icontains=search_query)
                | Q(trigger__icontains=search_query)
                | Q(id=search_query_int)
            )
        except ValueError:
            return cls.filter(
                Q(name__icontains=search_query)
                | Q(trigger__icontains=search_query)
            )

    @classmethod
    async def search_paginated(
        cls,
        page: int,
        limit: int,
        search_query: str | None = None,
    ) -> Sequence["AutoReplyRule"]:
        offset = (page - 1) * limit

        query = cls._get_query_method(search_query)
        return await query.offset(offset).limit(limit)

    @classmethod
    async def count_pages(cls, limit: int, search_query: str | None = None) -> int:
        total = await cls._get_query_method(search_query).count()
        return ceil(total / limit) if total > 0 else 1

    @classmethod
    async def count_total(cls, search_query: str | None = None) -> int:
        return await cls._get_query_method(search_query).count()


class AutoReplyIgnore(Model):
    """
    Model representing an ignore entry for the AutoReply plugin. This is used to specify users or channels that should not receive auto-replies.

    Attributes:
        discord_id (str): The Discord ID of the user or channel to ignore.
        discord_type (IgnoreType): The type of Discord entity (user, channel, guild).
        guild_id (str | None): The guild context for the ignore, if applicable.
        reason (str | None): Optional reason for ignoring.
        internal (bool): Whether the ignore was created automatically by the system.
    """

    id = fields.IntField(pk=True)
    discord_id = fields.CharField(max_length=50)
    discord_type = fields.IntEnumField(IgnoreType)
    guild_id = fields.CharField(
        max_length=50, null=True
    )  # Guild context for the ignore
    internal = fields.BooleanField(default=False)  # Created by the system

    class Meta:  # type: ignore
        table = "jerry_auto_reply_ignores"
        ordering = ["id"]

    def as_dataclass(self) -> "AutoReplyIgnoreData":
        """Convert to dataclass representation for in-memory operations."""
        return AutoReplyIgnoreData(
            db_id=self.id,
            discord_id=self.discord_id,
            discord_type=self.discord_type,
            guild_id=self.guild_id,
            internal=self.internal,
        )


# Dataclass Adaptations
@dataclass
class AutoReplyRuleData:
    """Dataclass representation of AutoReplyRule for in-memory operations."""

    trigger: str
    response_type: ResponseType
    response_method: ResponseMethod
    response_payload: str
    is_active: bool = True
    db_id: int | None = field(default=None)

    @cached_property
    def pattern(self):
        """Precompile the trigger regex pattern."""
        return re.compile(self.trigger, re.IGNORECASE)

    def match(self, message: str) -> bool:
        """Check if the message matches the trigger regex."""
        return bool(self.pattern.search(message))


@dataclass
class AutoReplyIgnoreData:
    """Dataclass representation of AutoReplyIgnore for in-memory operations."""

    discord_id: str
    discord_type: IgnoreType
    guild_id: str | None = None
    internal: bool = False
    reason: str | None = None
    db_id: int | None = field(default=None)
