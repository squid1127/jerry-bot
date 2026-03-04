"""Database models for Activity Roles Plugin."""
from tortoise import fields
from tortoise.models import Model

class ActivityRoleConfig(Model):
    """
    Database model for activity roles configuration.
    
    Attributes:
        guild_id (int): The ID of the guild. Primary key.
        active_role_id (int): The ID of the role assigned to active members.
        inactive_role_id (int): The ID of the role assigned to inactive members.
        activity_threshold (int): The activity threshold as a time delta.
    """

    guild_id = fields.BigIntField(primary_key=True)
    active_role_id = fields.BigIntField()
    inactive_role_id = fields.BigIntField()
    activity_threshold = fields.TimeDeltaField()
    
    class Meta:
        table = "best_bot_activity_roles_config"
    
class ActivityRoleEntry(Model):
    """
    Database model for tracking user activity for roles.
    
    Attributes:
        id (int): Auto-incrementing primary key.
        guild_id (int): The ID of the guild.
        user_id (int): The ID of the user.
        last_active (datetime): Timestamp of the user's last activity.
        is_active (bool): Whether the user is currently marked as active.
    """

    id = fields.IntField(pk=True)
    guild_id = fields.BigIntField()
    user_id = fields.BigIntField()
    last_active = fields.DatetimeField()
    is_active = fields.BooleanField(default=False)
    
    class Meta:
        table = "best_bot_activity_roles_entry"
        indexes = (("guild_id", "user_id"),)