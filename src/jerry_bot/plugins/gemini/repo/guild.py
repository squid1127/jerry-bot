""""Guild record repository and related data models for the Gemini plugin."""

from ..models import GuildRecord

class GuildRepository:
    """Repository for managing guild records."""

    def __init__(self, warm_start: bool = True):
        """Initialize the repository, optionally warming the cache.
        
        Args:
            warm_start: If True, pre-load all guild records into the cache. Otherwise, records will be loaded on demand. Defaults to True.
        """
        self._cache: dict[int, GuildRecord] = {}
        self.warm_start = warm_start
        
    async def load_all(self):
        """Pre-load all guild records into the cache."""
        self._cache.clear()
        records = await GuildRecord.all()
        for record in records:
            self._cache[record.guild_id] = record

    async def get_guild(self, guild_id: int, skip_cache: bool = False) -> GuildRecord | None:
        """Get a guild by ID, using cache if available.
        
        Args:
            guild_id: The ID of the guild to retrieve.
            skip_cache: If True, bypass the cache and query the database directly, also bypassing warm_start.
            
        Returns:
            The GuildRecord object if found, otherwise None."""
        if not skip_cache:
            if guild_id in self._cache:
                return self._cache[guild_id]
            
            if self.warm_start:
                return None  # If warm_start is enabled, we assume all guilds are already loaded in the cache

        record = await GuildRecord.get_or_none(guild_id=guild_id)
        if not record:
            return None

        self._cache[guild_id] = record
        return record
    
    async def invalidate_cache(self, guild_id: int, refresh: bool = False) -> None:
        """Invalidate the cache for a specific guild ID.
        
        Args:
            guild_id: The ID of the guild to invalidate in the cache.
            refresh: If True, the guild will be reloaded from the database after invalidation. This will always happen if warm_start is enabled.
        """
        if guild_id in self._cache:
            del self._cache[guild_id]
            
        if self.warm_start or refresh:
            await self.get_guild(guild_id, skip_cache=True)