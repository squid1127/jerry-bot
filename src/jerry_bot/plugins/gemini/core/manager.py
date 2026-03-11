""" "Conversation manager for Gemini plugin."""

from logging import Logger
from typing import Optional, TYPE_CHECKING
import discord

from ..models import UserMessage, Channel, Guild, ChannelContext
from ..models.exceptions import (
    ChannelAlreadyRegisteredError,
    ChannelNotRegisteredError,
    ConfigurationError,
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
        self.logger = logger
        self.config = config
        self.conversations: dict[int, Conversation] = {}  # Keyed by channel_id
        self.channels: dict[int, Channel] = {}  # Keyed by channel_id
        self.provider_manager = provider_manager

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

        provider = self.provider_manager.get_provider(channel.provider_name)
        guild = await channel.guild  # Await the FK to get the Guild instance
        conversation = Conversation(
            channel=channel,
            channel_context=ChannelContext(dc_channel, dc_channel.guild),
            guild=guild,
            logger=self.logger,
            provider=provider,
        )
        self.conversations[channel.channel_id] = conversation
        return conversation

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
        resolved_provider = provider_name or self.config.default_provider
        if resolved_provider not in self.provider_manager.providers:
            available = ", ".join(self.provider_manager.providers.keys())
            raise ConfigurationError(
                f"Unknown provider '{resolved_provider}'. Available providers: {available}"
            )

        # Ensure the guild exists (get or create)
        guild, _ = await Guild.get_or_create(guild_id=guild_id)

        channel = await Channel.create(
            channel_id=channel_id,
            guild=guild,
            provider_name=resolved_provider,
            provider_overrides=provider_overrides or {},
            prompt=prompt,
            override_system_prompt=override_system_prompt,
        )

        # Cache and initialise a live conversation
        self.channels[channel_id] = channel

        self.logger.info(
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
            if provider_name not in self.provider_manager.providers:
                available = ", ".join(self.provider_manager.providers.keys())
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

        self.logger.info(f"Updated Gemini channel {channel_id}.")
        return channel

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
            self.logger.debug(f"Torn down conversation for channel {channel_id}.")

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

        self.logger.info(f"Deleted Gemini channel {channel_id}.")

    # ── Message routing ───────────────────────────────────────────────────

    async def route_message(self, message: discord.Message):
        """Route an incoming Discord message to the appropriate Conversation instance based on the channel it originated from."""
        if not isinstance(message.channel, discord.TextChannel):
            self.logger.debug(
                f"Received message for channel_id {message.channel.id} which is not a TextChannel. Ignoring."
            )
            return

        conversation = await self.get_conversation(dc_channel=message.channel)
        if not conversation:
            self.logger.debug(
                f"Received message for channel_id {message.channel.id} which is not registered as a Gemini conversation."
            )
            return

        chat_message = UserMessage.from_discord_message(message)
        conversation.add_message(chat_message)
