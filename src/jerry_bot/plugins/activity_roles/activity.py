"""Activity tracking for Activity Roles plugin."""

from redis.asyncio import Redis
import squid_core
from datetime import datetime, timedelta, timezone
import asyncio

from .models.db import ActivityRoleEntry, ActivityRoleConfig
from .models.dataclasses import ActivityRoleUpdate

class ActivityTracker:
    """Class to track user activity within guilds."""

    def __init__(
        self, plugin: squid_core.Plugin, redis_namespace: str, redis_ttl: int = 3600
    ) -> None:
        """
        Initialize the ActivityTracker.

        Args:
            plugin (squid_core.Plugin): The plugin instance.
            redis_namespace (str): The Redis namespace for storing activity data.
            redis_ttl (int): The time-to-live for Redis keys in seconds. Default is 3600 seconds (1 hour).
        """
        self.plugin = plugin
        self.logger = plugin.logger
        self.redis_namespace = redis_namespace
        self.redis_ttl = redis_ttl
        
    @property
    def redis(self) -> Redis:
        """Get the Redis client from the framework."""
        if not self.plugin.fw.redis or not self.plugin.fw.redis.client:
            raise RuntimeError("Redis client is not available in the framework")
        
        return self.plugin.fw.redis.client

    async def activity(
        self, guild_id: int, user_id: int, last_active: datetime, ignore_exceptions: bool = True
    ) -> None:
        """
        Save the last active timestamp for a user in a guild to Redis.

        Args:
            guild_id (int): The ID of the guild.
            user_id (int): The ID of the user.
            last_active (datetime): The last active timestamp.
            ignore_exceptions (bool): Whether to ignore exceptions during the operation. Default is True.
        """
        try:
            key = f"{self.redis_namespace}:activity:{guild_id}:{user_id}"
            await self.redis.set(key, int(last_active.timestamp()))
            await self.redis.expire(key, self.redis_ttl)
            self.logger.debug(
                f"Saved activity for user {user_id} in guild {guild_id} at {last_active}"
            )
        except Exception as e:
            if not ignore_exceptions:
                raise e
            self.logger.error(
                f"Failed to save activity for user {user_id} in guild {guild_id}: {e}"
            )

    async def set_guild_config(
        self,
        guild_id: int,
        active_role_id: int,
        inactive_role_id: int,
        activity_threshold: timedelta,
    ) -> ActivityRoleConfig:
        """
        Set the activity roles configuration for a guild.

        Args:
            guild_id (int): The ID of the guild.
            active_role_id (int): The ID of the role assigned to active members.
            inactive_role_id (int): The ID of the role assigned to inactive members.
            activity_threshold (timedelta): The activity threshold.
            
        Returns:
            ActivityRoleConfig: The updated or created activity role configuration.
        """
        # Save to database
        config = await ActivityRoleConfig.get_or_none(guild_id=guild_id)
        # If config does not exist, create a new one (without committing)
        if config is None:
            config = ActivityRoleConfig(guild_id=guild_id)
        config.active_role_id = active_role_id
        config.inactive_role_id = inactive_role_id
        config.activity_threshold = activity_threshold
        await config.save()
        
        self.logger.info(f"Set activity roles config for guild {guild_id} -> {config}")
        return config

    async def flush_cache(self) -> None:
        """Flush the Redis cache to the database."""
        pattern = f"{self.redis_namespace}:activity:*"
        cursor = b"0"
        
        # First, collect all data from Redis
        redis_data = []
        redis_keys = []
        while cursor:
            cursor, keys = await self.redis.scan(cursor=cursor, match=pattern, count=100)
            for key in keys:
                # Remove the namespace prefix before splitting
                prefix = f"{self.redis_namespace}:activity:"
                key_str = key.decode().removeprefix(prefix)
                parts = key_str.split(":")
                guild_id = int(parts[0])
                user_id = int(parts[1])
                last_active_timestamp = await self.redis.get(key)
                if last_active_timestamp is None:
                    continue
                last_active = datetime.fromtimestamp(int(last_active_timestamp), tz=timezone.utc)
                redis_data.append((guild_id, user_id, last_active))
                redis_keys.append(key)
                
            if cursor == b"0":
                break
        
        if not redis_data:
            self.logger.debug("No activity entries to flush from Redis.")
            return
            
        # Fetch all existing entries in one query
        existing_entries = await ActivityRoleEntry.all()
        existing_map = {(entry.guild_id, entry.user_id): entry for entry in existing_entries}
        
        # Separate entries to update vs create
        to_update = []
        to_create = []
        
        for guild_id, user_id, last_active in redis_data:
            key = (guild_id, user_id)
            if key in existing_map:
                entry = existing_map[key]
                entry.last_active = last_active
                to_update.append(entry)
            else:
                to_create.append(
                    ActivityRoleEntry(
                        guild_id=guild_id,
                        user_id=user_id,
                        last_active=last_active,
                    )
                )
            
            self.logger.debug(
                f"Flushed activity for user {user_id} in guild {guild_id} at {last_active}"
            )
        
        # Bulk operations
        if to_create:
            await ActivityRoleEntry.bulk_create(to_create)
        if to_update:
            await ActivityRoleEntry.bulk_update(to_update, fields=["last_active"])
        
        # Delete all Redis keys in bulk
        if redis_keys:
            await self.redis.delete(*redis_keys)
        
        count = len(redis_data)
        self.logger.info(f"Flushed {count} activity tracking entries from Redis to the database.")
        
    async def get_guild_config(self, guild_id: int) -> ActivityRoleConfig | None:
        """
        Get the activity roles configuration for a guild.

        Args:
            guild_id (int): The ID of the guild.
        Returns:
            ActivityRoleConfig | None: The activity role configuration or None if not found.
        """
        config = await ActivityRoleConfig.get_or_none(guild_id=guild_id)
        return config
        
    async def update_queue(self, now: datetime) -> asyncio.Queue:
        """
        Generate a queue of ActivityRoleUpdate objects for processing.
        
        Args:
            now (datetime): The current timestamp.
        Returns:
            asyncio.Queue: A queue containing ActivityRoleUpdate objects.
        """
        queue = asyncio.Queue()
        
        # Fetch all entries and configs in bulk
        entries = await ActivityRoleEntry.all()
        configs = await ActivityRoleConfig.all()
        
        # Create a lookup dictionary for configs by guild_id
        config_map = {config.guild_id: config for config in configs}
        
        for entry in entries:
            config = config_map.get(entry.guild_id)
            if config is None:
                continue
            should_be_active = (now - entry.last_active) <= config.activity_threshold
            if entry.is_active == should_be_active:
                self.logger.debug(f"No role update needed for user {entry.user_id} in guild {entry.guild_id}")
                continue  # No change needed
            update = ActivityRoleUpdate(
                guild_id=entry.guild_id,
                user_id=entry.user_id,
                entry=entry,
                should_be_active=should_be_active,
            )
            await queue.put(update)
        self.logger.info(f"Generated update queue with {queue.qsize()} entries.")
        return queue
    
    async def get_user_activity(self, user_id: int) -> list[ActivityRoleEntry]:
        """
        Get all activity role entries for a specific user across guilds.

        Args:
            user_id (int): The ID of the user.
        Returns:
            list[ActivityRoleEntry]: A list of activity role entries for the user.
        """
        entries = await ActivityRoleEntry.filter(user_id=user_id)
        return entries
    
    async def add_missing_members(self, guild_id: int, member_ids: list[int]) -> int:
        """
        Add missing guild members to the database as inactive.
        
        Args:
            guild_id (int): The ID of the guild.
            member_ids (list[int]): List of member IDs to check and add if missing.
        Returns:
            int: The number of members added to the database.
        """
        # Fetch existing entries for this guild
        existing_entries = await ActivityRoleEntry.filter(guild_id=guild_id)
        existing_user_ids = {entry.user_id for entry in existing_entries}
        
        # Find members that don't exist in the database
        missing_member_ids = [mid for mid in member_ids if mid not in existing_user_ids]
        
        if not missing_member_ids:
            self.logger.info(f"No missing members to add for guild {guild_id}")
            return 0
        
        # Get the guild config to determine an appropriate inactive timestamp
        config = await self.get_guild_config(guild_id)
        if config is None:
            raise ValueError(f"No activity role config found for guild {guild_id}")
        
        # Set last_active to a time that's definitely beyond the threshold (making them inactive)
        # Using current time minus (threshold + 1 day) to ensure they're marked as inactive
        now = datetime.now(timezone.utc)
        inactive_timestamp = now - config.activity_threshold - timedelta(days=1)
        
        # Create new entries for missing members
        new_entries = [
            ActivityRoleEntry(
                guild_id=guild_id,
                user_id=member_id,
                last_active=inactive_timestamp,
                is_active=True, # Set to true to ensure they are marked inactive on next check
            )
            for member_id in missing_member_ids
        ]
        
        # Bulk create
        await ActivityRoleEntry.bulk_create(new_entries)
        
        count = len(new_entries)
        self.logger.info(f"Added {count} missing members to guild {guild_id} as inactive")
        return count