""""Channel record repository and related data models for the Gemini plugin."""

from ..models import ChannelRecord, Channel

class ChannelRepository:
    """Repository for managing channel records."""

    def __init__(self, warm_start: bool = True):
        """Initialize the repository, optionally warming the cache.
        
        Args:
            warm_start: If True, pre-load all channel records into the cache. Otherwise, records will be loaded on demand. Defaults to True.
        """
        self._cache: dict[int, Channel] = {}
        self.warm_start = warm_start
        
    async def load_all(self):
        """Pre-load all channel records into the cache."""
        self._cache.clear()
        records = await ChannelRecord.filter(active=True).all()
        for record in records:
            channel = Channel.from_record(record)
            self._cache[channel.channel_id] = channel

    async def get_channel(self, channel_id: int, active: bool = True, skip_cache: bool = False) -> Channel | None:
        """Get a channel by ID, using cache if available.
        
        Args:
            channel_id: The ID of the channel to retrieve.
            active: If True, only return the channel if it is marked as active.
            skip_cache: If True, bypass the cache and query the database directly, also bypassing warm_start.
            
        Returns:
            The Channel object if found and active (if active=True), otherwise None."""
        if not skip_cache:
            if channel_id in self._cache:
                return self._cache[channel_id]
            
            if self.warm_start:
                return None  # If warm_start is enabled, we assume all channels are already loaded in the cache

        record = await ChannelRecord.get_or_none(channel_id=channel_id)
        if not record or (active and not record.active):
            return None

        channel = Channel.from_record(record)
        self._cache[channel_id] = channel
        return channel
    
    async def invalidate_cache(self, channel_id: int, refresh: bool = False) -> None:
        """Invalidate the cache for a specific channel ID.
        
        Args:
            channel_id: The ID of the channel to invalidate in the cache.
            refresh: If True, the channel will be reloaded from the database after invalidation. This will always happen if warm_start is enabled.
        """
        if channel_id in self._cache:
            del self._cache[channel_id]
            
        if self.warm_start or refresh:
            await self.get_channel(channel_id, skip_cache=True)
            
    async def get_all(self, active: bool = True) -> list[Channel]:
        """Get all channels, optionally filtering by active status.
        
        Args:
            active: If True, only return channels that are marked as active. Defaults to True.
        
        Returns:
            A list of Channel objects matching the criteria."""
        if self.warm_start and active:
            return list(self._cache.values())
        
        records = await ChannelRecord.filter(active=active).all()
        channels = []
        for record in records:
            channel = Channel.from_record(record)
            self._cache[channel.channel_id] = channel
            channels.append(channel)
        return channels