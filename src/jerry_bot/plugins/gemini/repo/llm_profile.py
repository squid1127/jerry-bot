""""LLM profile repository and related data models for the Gemini plugin."""

from jerry_bot.plugins.gemini.models import channel
from jerry_bot.plugins.gemini.models.database import ChannelRecord

from ..models import LLMProfile, LLMProfileRecord

class LLMProfileRepository:
    """Repository for managing LLM profiles."""

    def __init__(self, warm_start: bool = True):
        """Initialize the repository, optionally warming the cache.
        
        Args:
            warm_start: If True, pre-load all channel records into the cache. Otherwise, records will be loaded on demand. Defaults to True.
        """
        self._cache: dict[int, list[LLMProfile]] = {}
        self.warm_start = warm_start
        
    async def load_all(self):
        """Pre-load all channel records into the cache."""
        self._cache.clear()
        records = await LLMProfileRecord.all()
        for record in records:
            profile = LLMProfile.from_record(record)
            self._cache.setdefault(record.channel_id, []).append(profile)

    async def get_profiles(self, channel_id: int, skip_cache: bool = False) -> list[LLMProfile] | None:
        """Get all LLM profiles for a channel by ID, using cache if available.

        Args:
            channel_id: The ID of the channel to retrieve.
            skip_cache: If True, bypass the cache and query the database directly, also bypassing warm_start.
            
        Returns:
            The Channel object if found and active (if active=True), otherwise None."""
        if not skip_cache:
            if channel_id in self._cache:
                return self._cache[channel_id]
            
            if self.warm_start:
                return None  # If warm_start is enabled, we assume all profiles are already loaded in the cache

        records = await LLMProfileRecord.filter(channel_id=channel_id).all()
        if not records:
            return None

        profiles = [LLMProfile.from_record(record) for record in records]
        self._cache[channel_id] = profiles
        return profiles
    
    async def invalidate_cache(self, channel_id: int, refresh: bool = False) -> None:
        """Invalidate the cache for a specific channel ID.
        
        Args:
            channel_id: The ID of the channel to invalidate in the cache.
            refresh: If True, the channel will be reloaded from the database after invalidation. This will always happen if warm_start is enabled.
        """
        if channel_id in self._cache:
            del self._cache[channel_id]
            
        if self.warm_start or refresh:
            await self.get_profiles(channel_id, skip_cache=True)