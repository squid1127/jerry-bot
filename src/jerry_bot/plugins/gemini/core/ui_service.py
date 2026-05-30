"""Abstraction layer for configuration UI, allowing for Discord UI to interface with core logic"""

from ..repo import Repositories
from .manager import ConversationManager
from ..models import ChannelRecord, Channel, GuildRecord, LLMProfile, LLMProfileRecord
from ..provider import Provider

class UIService:
    """Service for handling UI interactions and interfacing with core logic."""

    def __init__(
        self,
        repos: Repositories,
        conversation_manager: ConversationManager,
    ):
        """
        Initialize the UIService with necessary dependencies.

        Args:
            repos: RepositoryContext containing all necessary repositories for loading data.
            conversation_manager: Manager for handling conversation logic.
        """
        self._repos = repos
        self._conversation_manager = conversation_manager
        
    #* Channel Management *#

    async def get_channel(self, channel_id: int, active: bool = True, ignore_active: bool = False) -> Channel | None:
        """Get a channel by its ID."""
        result = await self._repos.channel_repo.get_channel(channel_id, active=active)
        
        if not result and ignore_active:
            return await self._repos.channel_repo.get_channel(channel_id, active=False)
        
        return result

    async def set_channel(self, channel_id: int, create: bool = False, **kwargs) -> Channel:
        """Create or update a channel record with the given parameters, and invalidate the cache for that channel.
        
        Args:
            channel_id: The ID of the channel to create or update.
            create: If True, a new channel record will be created if one does not already exist. If False, an error will be raised if the channel does not already exist. Defaults to False
            **kwargs: Fields to set on the channel record (e.g., active, prompt, etc.). All required fields must be included when creating a new record.
            
        Returns:
            The created or updated Channel object.
        """
        channel = await ChannelRecord.get_or_none(channel_id=channel_id)
        if not channel:
            if not create:
                raise ValueError(f"Channel with ID {channel_id} not found.")
            channel = ChannelRecord(channel_id=channel_id, **kwargs)
        else:
            for key, value in kwargs.items():
                setattr(channel, key, value)

        await channel.save()
        await self._repos.channel_repo.invalidate_cache(channel_id)
        return Channel.from_record(channel)
    
    #* Guild Management *#
    
    async def get_guild(self, guild_id: int) -> GuildRecord | None:
        """Get a guild record by its ID."""
        return await self._repos.guild_repo.get_guild(guild_id)
    
    async def set_guild(self, guild_id: int, create: bool = False, **kwargs) -> GuildRecord:
        """Create or update a guild record with the given parameters.
        
        Args:
            guild_id: The ID of the guild to create or update.
            create: If True, a new guild record will be created if one does not already exist. If False, an error will be raised if the guild does not already exist. Defaults to False
            **kwargs: Fields to set on the guild record (e.g., config_data, trusted, prompt, etc.). All required fields must be included when creating a new record.
            
        Returns:
            The created or updated GuildRecord object.
        """
        guild = await GuildRecord.get_or_none(guild_id=guild_id)
        if not guild:
            if not create:
                raise ValueError(f"Guild with ID {guild_id} not found.")
            guild = GuildRecord(guild_id=guild_id, **kwargs)
        else:
            for key, value in kwargs.items():
                setattr(guild, key, value)

        await guild.save()
        await self._repos.guild_repo.invalidate_cache(guild_id)
        return guild
    
    #* LLM Profile Management *#
    async def get_llm_profiles(self, channel_id: int) -> list[LLMProfile] | None:
        """Get a list of LLM profiles for a given channel. Returns None if no profiles are found."""
        return await self._repos.llm_profile_repo.get_profiles(channel_id)
    
    async def get_llm_profile(self, channel_id: int, profile_id: int) -> LLMProfile | None:
        """Get a specific LLM profile by channel ID and profile ID. Returns None if the profile is not found."""
        profiles = await self._repos.llm_profile_repo.get_profiles(channel_id)
        if not profiles:
            return None
        for profile in profiles:
            if profile.id == profile_id:
                return profile
    
    async def set_llm_profile(self, channel_id: int, id: int | None, create: bool = False, **kwargs) -> LLMProfile:
        """Create or update an LLM profile for a given channel with the provided parameters, and invalidate the cache for that channel.
        
        Args:
            channel_id: The ID of the channel to which the LLM profile belongs.
            id: The ID of the LLM profile to create or update. If creating a new profile, this should be set to None or omitted.
            create: If True, a new LLM profile will be created if one does not already exist with the given ID. If False, an error will be raised if a profile with the given ID does not already exist. Defaults to False.
            **kwargs: Fields to set on the LLM profile record (e.g., provider_name, model_name, temperature, etc.). All required fields must be included when creating a new record.
        Returns:
            The created or updated LLMProfile object.
        """
        profile = None
        if id is not None:
            profile = await LLMProfileRecord.get_or_none(id=id, channel_id=channel_id)
        
        if not profile:
            if not create:
                raise ValueError(f"LLM Profile with ID {id} for channel {channel_id} not found.")
            profile = await LLMProfileRecord.create(channel_id=channel_id, **kwargs)
        else:
            for key, value in kwargs.items():
                setattr(profile, key, value)
            await profile.save()
        
        await self._repos.llm_profile_repo.invalidate_cache(channel_id)
        return LLMProfile.from_record(profile)
    
    #* Provider Operations *#
    def get_providers(self) -> list[str]:
        """Get a list of available provider names."""
        return list(self._repos.provider_registry.providers.keys())
    
    def get_provider(self, provider_name: str) -> Provider:
        """Get a provider instance by name."""
        provider = self._repos.provider_registry.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' not found.")
        return provider
    
    def get_default_provider(self) -> Provider:
        """Get the default provider instance."""
        default_provider_name = self._repos.global_config.default_provider
        return self.get_provider(default_provider_name)
    
    async def model_exists(self, provider_name: str, model_name: str) -> bool:
        """Check if a model exists for a given provider."""
        provider = self._repos.provider_registry.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' not found.")
        return await provider.model_exists(model_name)
    
    #* Conversation Management *#
    async def stop_conversation(self, channel_id: int) -> None:
        """Stop the conversation session for a given channel ID."""
        await self._conversation_manager.stop_session(channel_id)
        
    def has_conversation(self, channel_id: int) -> bool:
        """Check if there is an active conversation session for a given channel ID."""
        return self._conversation_manager.get_session(channel_id) is not None