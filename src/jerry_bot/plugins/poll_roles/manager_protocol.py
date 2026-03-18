"""Protocol for managing poll roles."""

from typing import Protocol
import discord

from .models import Poll

class PollRoleManager(Protocol):
    """Protocol for managing poll roles."""

    def get_poll(self, guild_id: int, channel_id: int, message_id: int) -> Poll | None:
        """Get a poll by its guild, channel, and message IDs."""
        ...
        
    async def get_inactive_poll(self, guild_id: int, channel_id: int, message_id: int) -> Poll | None:
        """Get a poll by its guild, channel, and message IDs, including inactive polls."""
        ...

    def add_poll(self, poll: Poll):
        """Add a poll to the in-memory cache."""
        ...

    def remove_poll(
        self, guild_id: int, channel_id: int, message_id: int
    ) -> Poll | None:
        """Remove a poll from the in-memory cache."""
        ...
        
    async def close_poll(self, guild_id: int, channel_id: int, message_id: int) -> bool:
        """Close a poll, marking it as inactive and removing it from the cache. Returns True if a poll was closed, False if no poll was found."""
        ...
        
    async def process_role_updates(
        self,
        poll: Poll,
        new_object: discord.Poll,
        user_id: int | None,
        answer_id: int | None = None,
    ):
        """Process a poll, reading poll object and diffing to apply role updates. Filter by user_id if provided otherwise process all votes."""
        ...