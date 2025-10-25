"""Database Models and Types for AutoReply Plugin"""

from tortoise import fields
from tortoise.models import Model
from dataclasses import dataclass, field
import re # Precompile regex patterns if needed
from functools import cached_property

from .enums import ResponseType, IgnoreType

class AutoReplyRule(Model):
    """Model representing an auto-reply rule.
    
    Attributes:
        trigger (str): The trigger regex for the auto-reply.
        response_type (ResponseType): The type of response (text, image, etc.).
        response_payload (str): The content of the response.
        is_active (bool): Whether the rule is active.
    """
    
    id = fields.IntField(pk=True)
    trigger = fields.TextField()
    response_type = fields.IntEnumField(ResponseType)
    response_payload = fields.TextField()
    is_active = fields.BooleanField(default=True)
    
    class Meta:
        table = "jerry_auto_reply_rules"
        ordering = ["id"]
    
    def as_dataclass(self) -> "AutoReplyRuleData":
        """Convert to dataclass representation for in-memory operations."""
        return AutoReplyRuleData(
            db_id=self.id,
            trigger=self.trigger,
            response_type=self.response_type,
            response_payload=self.response_payload,
            is_active=self.is_active
        )
    
class AutoReplyIgnore(Model):
    """
    Model representing an ignore entry for the AutoReply plugin. This is used to specify users or channels that should not receive auto-replies.
    
    Attributes:
        discord_id (str): The Discord ID of the user or channel to ignore.
        discord_type (IgnoreType): The type of Discord entity (user, channel, guild).
        reason (str | None): Optional reason for ignoring.
        internal (bool): Whether the ignore was created automatically by the system.
    """
    
    id = fields.IntField(pk=True)
    discord_id = fields.CharField(max_length=50)
    discord_type = fields.IntEnumField(IgnoreType)
    internal = fields.BooleanField(default=False) # Created by the system
    
    class Meta:
        table = "jerry_auto_reply_ignores"
        ordering = ["id"]
    
    def as_dataclass(self) -> "AutoReplyIgnoreData":
        """Convert to dataclass representation for in-memory operations."""
        return AutoReplyIgnoreData(
            db_id=self.id,
            discord_id=self.discord_id,
            discord_type=self.discord_type,
            internal=self.internal
        )
    
# Dataclass Adaptations
@dataclass
class AutoReplyRuleData:
    """Dataclass representation of AutoReplyRule for in-memory operations."""
    trigger: str
    response_type: ResponseType
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
    internal: bool = False
    reason: str | None = None
    db_id: int | None = field(default=None)
