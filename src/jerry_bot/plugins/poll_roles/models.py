"""Models for PollRoles Plugin."""

from tortoise import fields, Model

class Poll(Model):
    """Model for a poll.
    
    Attributes:
        id: The unique identifier for the poll.
        guild_id: The ID of the guild where the poll is active.
        channel_id: The ID of the channel where the poll message is located.
        message_id: The ID of the message that contains the poll.
        active: Whether the poll is currently active (not closed).
        live_mode: Whether the poll is in live mode (updates when users vote).
        mapping: A JSON field that maps options to role IDs.
        expire_by: The latest possible expiration time for the poll, used for cleanup of old polls.
    """
    
    id = fields.IntField(pk=True)
    guild_id = fields.BigIntField()
    channel_id = fields.BigIntField()
    message_id = fields.BigIntField()
    active = fields.BooleanField(default=True)
    live_mode = fields.BooleanField(default=True)
    mapping = fields.JSONField()
    expire_by = fields.DatetimeField(null=True)
    
    class Meta: # type: ignore
        """Meta class for Poll."""
        table = "jerry_poll_roles_polls"