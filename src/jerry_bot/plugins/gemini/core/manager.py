""" "Conversation manager for Gemini plugin."""

from logging import Logger
from typing import Optional, TYPE_CHECKING
import discord

from ..models import UserMessage, Channel, Guild, ChannelContext, ModelEntry, Model
from ..models.exceptions import (
    ChannelAlreadyRegisteredError,
    ChannelNotRegisteredError,
    ConfigurationError,
    ConversationInactivityTimeoutError,
)
from .conversation import Conversation

from ..config import GlobalConfig
from ..provider import ProviderManager, Provider


class ConversationManager:
    """Manages active conversations for the Gemini plugin, including loading/saving state and routing messages to the correct conversation instance."""

    def __init__(
        self,
        logger: Logger,
        config: "GlobalConfig",
        provider_manager: "ProviderManager",
    ):
        self._logger = logger
        self._config = config
        self.conversations: dict[int, Conversation] = {}  # Keyed by channel_id
        self.channels: dict[int, Channel] = {}  # Keyed by channel_id
        self.guilds: dict[int, Guild] = {}  # Keyed by guild_id
        self._provider_manager = provider_manager

    # ── Read ──────────────────────────────────────────────────────────────

    async def get_channel(self, channel_id: int) -> Optional[Channel]:
        """Get a Channel model if it exists locally or in the database, otherwise return None."""
        if channel_id in self.channels:
            return self.channels[channel_id]

        channel = await Channel.get_or_none(channel_id=channel_id)

        if not channel:
            return None

        self.channels[channel_id] = channel
        return channel

    async def get_conversation(
        self, dc_channel: discord.TextChannel
    ) -> Optional[Conversation]:
        """Get a Conversation instance for the given channel_id, or None if it doesn't exist. If the conversation doesn't exist but the channel does, create a new Conversation instance."""
        if dc_channel.id in self.conversations:
            return self.conversations[dc_channel.id]

        channel = await self.get_channel(dc_channel.id)
        if not channel:
            return None

        if channel.model:
            model_entry: ModelEntry = await channel.model
            model = Model.from_database_entry(model_entry)
        else:
            # Fallback to provider's default model if not set at channel level
            model = self._provider_manager.get_provider(
                channel.provider_name
            ).default_model

        provider = self._provider_manager.get_provider(channel.provider_name)

        guild_id = getattr(channel, "guild_id", None)
        guild = await self.get_guild(guild_id) if guild_id is not None else None
        if guild is None:
            guild = await channel.guild  # Fallback to FK relation fetch
            self.guilds[guild.guild_id] = guild

        conversation = Conversation(
            channel=channel,
            channel_context=ChannelContext(dc_channel, dc_channel.guild),
            guild=guild,
            logger=self._logger,
            provider=provider,
            model=model,
            global_config=self._config,
        )
        self.conversations[channel.channel_id] = conversation
        return conversation

    async def get_ephemeral_conversation(
        self, dc_channel: discord.TextChannel, create: bool = False
    ) -> Optional[Conversation]:
        """Get or create a Conversation instance for the given channel_id in ephemeral mode, or None if the channel doesn't exist or isn't in a trusted guild."""
        guild_id = dc_channel.guild.id
        guild = await self.get_guild(guild_id)
        if not guild or not guild.trusted:
            if create:
                self._logger.warning(
                    f"Attempted to create ephemeral conversation for channel {dc_channel.id} in untrusted or unregistered guild {guild_id}."
                )
            return None

        channel_id = dc_channel.id
        if channel_id in self.conversations:
            self._logger.debug(
                f"Conversation already exists for channel {channel_id}, returning existing instance for ephemeral routing."
            )
            return self.conversations[channel_id]

        if not create:
            return None

        self._logger.info(
            f"Creating new ephemeral conversation for channel {channel_id} in trusted guild {guild_id}."
        )

        # Create a temporary ChannelContext without a corresponding database Channel
        channel_context = ChannelContext(dc_channel, dc_channel.guild)

        provider_name = self._config.ephemeral_mode.provider or self._config.default_provider
        provider = self._provider_manager.get_provider(provider_name)
        model = (
            Model.from_config(self._config.ephemeral_mode.model)
            or provider.default_model
        )

        conversation = Conversation(
            channel_id=dc_channel.id,
            channel_context=channel_context,
            guild=guild,
            logger=self._logger,
            provider=provider,
            model=model,
            global_config=self._config,
        )
        self.conversations[dc_channel.id] = conversation
        return conversation

    async def get_guild(self, guild_id: int, create: bool = False) -> Optional[Guild]:
        """Get a Guild model by its ID, or None if it doesn't exist."""
        if guild_id in self.guilds:
            return self.guilds[guild_id]

        if create:
            guild, _ = await Guild.get_or_create(guild_id=guild_id)
            self.guilds[guild_id] = guild
            return guild

        guild = await Guild.get_or_none(guild_id=guild_id)
        if guild:
            self.guilds[guild_id] = guild
        return guild

    async def list_channels(self, guild_id: Optional[int] = None) -> list[Channel]:
        """List all registered channels, optionally filtered by guild.

        Args:
            guild_id: If provided, only return channels belonging to this guild.

        Returns:
            A list of Channel model instances.
        """
        if guild_id is not None:
            return await Channel.filter(guild_id=guild_id).all()
        return await Channel.all()

    # ── Create ────────────────────────────────────────────────────────────

    async def create_channel(
        self,
        channel_id: int,
        guild_id: int,
        provider_name: Optional[str] = None,
        provider_overrides: Optional[dict] = None,
        prompt: Optional[str] = None,
        override_system_prompt: bool = False,
    ) -> Channel:
        """Register a new channel as a Gemini conversation.

        Creates the parent Guild record if it doesn't already exist, then creates
        the Channel row and initializes a live Conversation for it.

        Args:
            channel_id: The Discord channel ID.
            guild_id: The Discord guild (server) ID the channel belongs to.
            provider_name: The LLM provider to use. Defaults to the global default.
            provider_overrides: Optional per-channel provider overrides.
            prompt: Optional custom prompt for the channel.
            override_system_prompt: If True, the channel prompt replaces (rather than
                supplements) the global system prompt.

        Returns:
            The newly created Channel instance.

        Raises:
            ChannelAlreadyRegisteredError: If the channel is already registered.
            ConfigurationError: If the provider name is invalid.
        """
        # Ensure the channel isn't already registered
        existing = await self.get_channel(channel_id)
        if existing:
            raise ChannelAlreadyRegisteredError(channel_id)

        # Resolve and validate provider
        resolved_provider = provider_name or self._config.default_provider
        if resolved_provider not in self._provider_manager.providers:
            available = ", ".join(self._provider_manager.providers.keys())
            raise ConfigurationError(
                f"Unknown provider '{resolved_provider}'. Available providers: {available}"
            )

        # Ensure the guild exists (get or create)
        guild = await self.get_guild(guild_id, create=True)
        if guild is None:
            raise ConfigurationError(f"Unable to resolve guild {guild_id}.")

        # Create model entry for the channel with provider's default
        model = self._provider_manager.get_provider(
            resolved_provider
        ).default_model.to_database_entry()
        await model.save()

        channel = await Channel.create(
            channel_id=channel_id,
            guild=guild,
            provider_name=resolved_provider,
            provider_overrides=provider_overrides or {},
            prompt=prompt,
            override_system_prompt=override_system_prompt,
            model=model,
        )

        # Cache and initialise a live conversation
        self.channels[channel_id] = channel

        self._logger.info(
            f"Created Gemini channel {channel_id} in guild {guild_id} "
            f"(provider={resolved_provider})."
        )
        return channel

    # ── Update ────────────────────────────────────────────────────────────

    async def update_channel(
        self,
        channel_id: int,
        *,
        provider_name: Optional[str] = None,
        provider_overrides: Optional[dict] = None,
        prompt: Optional[str] = ...,  # type: ignore[assignment]
        override_system_prompt: Optional[bool] = None,
    ) -> Channel:
        """Update properties of an existing Gemini channel.

        Only the fields that are explicitly provided will be modified. Pass
        ``prompt=None`` to clear a custom prompt.

        Args:
            channel_id: The channel to update.
            provider_name: New LLM provider name.
            provider_overrides: New provider overrides dict (replaces existing).
            prompt: New custom prompt, or ``None`` to clear it.  Omit (default
                sentinel) to leave unchanged.
            override_system_prompt: Whether the channel prompt replaces the global
                system prompt.

        Returns:
            The updated Channel instance.

        Raises:
            ChannelNotRegisteredError: If the channel is not registered.
            ConfigurationError: If the provider name is invalid.
        """
        channel = await self.get_channel(channel_id)
        if not channel:
            raise ChannelNotRegisteredError(channel_id)

        if provider_name is not None:
            if provider_name not in self._provider_manager.providers:
                available = ", ".join(self._provider_manager.providers.keys())
                raise ConfigurationError(
                    f"Unknown provider '{provider_name}'. Available providers: {available}"
                )
            channel.provider_name = provider_name

        if provider_overrides is not None:
            channel.provider_overrides = provider_overrides

        if prompt is not ...:
            channel.prompt = prompt  # type: ignore[assignment]

        if override_system_prompt is not None:
            channel.override_system_prompt = override_system_prompt

        await channel.save()

        # Refresh the cache and tear down the stale conversation so it is
        # rebuilt with the new settings on the next incoming message.
        self.channels[channel_id] = channel
        await self.stop_conversation(channel_id)

        self._logger.info(f"Updated Gemini channel {channel_id}.")
        return channel

    async def update_channel_model(
        self,
        channel_id: int,
        model: Model,
    ) -> Channel:
        """Update the model for an existing Gemini channel.

        Args:
            channel_id: The channel to update.
            model: The new model to use for the channel.
        Returns:
            The updated Channel instance.
        Raises:
            ChannelNotRegisteredError: If the channel is not registered.
        """
        channel = await self.get_channel(channel_id)
        if not channel:
            raise ChannelNotRegisteredError(channel_id)
        if channel.model:
            model_entry: ModelEntry | None = await channel.model
        else:
            model_entry = None

        if model_entry:
            self._logger.info(
                f"Updating model for Gemini channel {channel_id} from {model_entry.model_name} to {model.name}."
            )

            default_model = self._provider_manager.get_provider(
                channel.provider_name
            ).default_model.to_database_entry()

            model_entry.model_name = model.name
            model_entry.temperature = (
                model.temperature
                if model.temperature is not None
                else default_model.temperature
            )
            model_entry.max_tokens = (
                model.max_tokens
                if model.max_tokens is not None
                else default_model.max_tokens
            )
            model_entry.top_p = (
                model.top_p if model.top_p is not None else default_model.top_p
            )
            model_entry.top_k = (
                model.top_k if model.top_k is not None else default_model.top_k
            )

        else:
            self._logger.info(
                f"Setting model for Gemini channel {channel_id} to {model.name}."
            )
            model_entry = model.to_database_entry()

        await model_entry.save()

        channel.model = model_entry
        await channel.save()

        # Refresh the cache and tear down the stale conversation so it is
        # rebuilt with the new settings on the next incoming message.
        self.channels[channel_id] = channel
        await self.stop_conversation(channel_id)

        self._logger.info(f"Updated model for Gemini channel {channel_id}.")
        return channel

    async def update_guild(
        self,
        guild_id: int,
        trusted: Optional[bool] = None,
        create: bool = False,
    ) -> Guild:
        """Update properties of an existing Gemini guild.

        Only the fields that are explicitly provided will be modified.

        Args:
            guild_id: The guild to update.
            trusted: Whether the guild is trusted (allows ephemeral mode).
            create: If True, create the guild if it doesn't already exist.

        Returns:
            The updated Guild instance.

        Raises:
            ConfigurationError: If the guild does not exist.
        """
        guild = await self.get_guild(guild_id, create=create)
        if not guild:
            raise ConfigurationError(f"Guild {guild_id} is not registered.")

        if trusted is not None:
            guild.trusted = trusted

        await guild.save()
        self.guilds[guild_id] = guild

        self._logger.info(f"Updated Gemini guild {guild_id}.")
        return guild

    # ── Stop Conversation ─────────────────────────────────────────────────

    async def stop_conversation(self, channel_id: int, *, drain: bool = False) -> None:
        """Stop and remove the active Conversation instance for a channel, if one exists.

        Args:
            channel_id: The channel whose conversation should be torn down.
            drain: If True, wait for any queued messages to finish processing
                before stopping. Defaults to False.
        """
        conversation = self.conversations.pop(channel_id, None)
        if conversation:
            await conversation.stop(drain=drain)
            self._logger.debug(f"Torn down conversation for channel {channel_id}.")

    async def stop_all(self, drain: bool = False) -> None:
        """Stop all active conversations, optionally draining message queues first."""
        for conversation in self.conversations.values():
            await conversation.stop(drain=drain)
        self.conversations.clear()

    # ── Delete ────────────────────────────────────────────────────────────

    async def delete_channel(self, channel_id: int) -> None:
        """Remove a channel from Gemini, deleting its database record and
        stopping any active conversation.

        Args:
            channel_id: The channel to remove.

        Raises:
            ChannelNotRegisteredError: If the channel is not registered.
        """
        channel = await self.get_channel(channel_id)
        if not channel:
            raise ChannelNotRegisteredError(channel_id)

        # Tear down the live conversation if one exists
        await self.stop_conversation(channel_id)

        # Remove from caches and database
        self.channels.pop(channel_id, None)
        await channel.delete()

        self._logger.info(f"Deleted Gemini channel {channel_id}.")

    # ── Message routing ───────────────────────────────────────────────────

    async def _enqueue_routed_message(
        self,
        *,
        message: discord.Message,
        conversation: Conversation,
    ) -> None:
        """Convert a Discord message to a UserMessage and enqueue it to a conversation."""
        chat_message = UserMessage.from_discord_message(message)
        try:
            conversation.add_message(chat_message)
        except ConversationInactivityTimeoutError:
            self._logger.info(
                f"Conversation for channel_id {message.channel.id} has been inactive for too long and was stopped. Cannot route message."
            )
            await self.stop_conversation(message.channel.id, drain=False)

    async def route_message(
        self,
        message: discord.Message,
        *,
        allow_ephemeral: bool = False,
        create_ephemeral: bool = False,
    ) -> None:
        """Route an incoming message to a channel conversation, optionally falling back to ephemeral mode.

        Args:
            message: Incoming Discord message.
            allow_ephemeral: If True, attempt ephemeral conversation routing when
                the channel is not registered.
            create_ephemeral: If True, create an ephemeral conversation when none
                exists for the channel.
        """
        if not isinstance(message.channel, discord.TextChannel):
            self._logger.debug(
                f"Received message for channel_id {message.channel.id} which is not a TextChannel. Ignoring."
            )
            return

        conversation = await self.get_conversation(dc_channel=message.channel)
        if conversation:
            await self._enqueue_routed_message(
                message=message, conversation=conversation
            )
            return

        if not allow_ephemeral:
            self._logger.debug(
                f"Received message for channel_id {message.channel.id} which is not registered as a Gemini conversation."
            )
            return

        conversation = await self.get_ephemeral_conversation(
            dc_channel=message.channel,
            create=create_ephemeral,
        )
        if not conversation:
            self._logger.debug(
                f"Received message for channel_id {message.channel.id} which is not eligible for ephemeral conversations."
            )
            return

        await self._enqueue_routed_message(message=message, conversation=conversation)
