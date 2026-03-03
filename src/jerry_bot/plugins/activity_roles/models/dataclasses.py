"""Dataclasses for activity roles plugin."""

from dataclasses import dataclass
from datetime import timedelta

from .db import ActivityRoleEntry

@dataclass
class ActivityRoleUpdate:
    """Dataclass for queuing activity role updates.
    
    Attributes:
        guild_id (int): The ID of the guild.
        user_id (int): The ID of the user.
        entry (ActivityRoleEntry): The database entry for the user's activity. (Will be updated to the should_be_active state)
        should_be_active (bool): Whether the user should be marked as active.
        """

    guild_id: int
    user_id: int
    entry: ActivityRoleEntry
    should_be_active: bool