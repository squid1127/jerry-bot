"""Conversation factory and context builder for the Gemini plugin."""

from discord import TextChannel
from discord.ext.commands import Bot
from logging import Logger

from .context import SessionContext
from .session import ConversationSession
from ..models import OutputContext, Channel, ConfigurationError
from ..config import GlobalConfig
from ..repo import Repositories


class ConversationFactory:
    """Factory for creating conversation sessions and their contexts."""

    def __init__(
        self,
        repos: Repositories,
        bot: Bot,
        logger: Logger,
    ):
        """
        Initialize the ConversationFactory with necessary dependencies.

        Args:
            repos: RepositoryContext containing all necessary repositories for loading data.
            bot: The instance of the Discord Bot, used for generating Discord context objects.
            logger: The logger instance for logging within the factory and created sessions.
        """
        self._bot = bot
        self._logger = logger
        self._repos = repos

    def generate_output_context(self, channel_id: int) -> OutputContext | None:
        """Generate an OutputContext object for a given channel ID."""
        dc_guild = self._bot.get_guild(channel_id)
        dc_channel = dc_guild.get_channel(channel_id) if dc_guild else None

        if not (dc_guild and dc_channel and isinstance(dc_channel, TextChannel)):
            return None

        return OutputContext(
            guild=dc_guild,
            channel=dc_channel,
        )

    async def create_session_context(
        self, channel_id: int, channel: Channel | None = None
    ) -> SessionContext:
        """
        Create a SessionContext for a given channel ID, loading necessary data from repositories.

        Args:
            channel_id: The ID of the channel for which to create the session context.
            channel: The channel object for which to create the session context.
        Returns:
            A SessionContext instance populated with data from the repositories and generated output context.

        Raises:
            ConfigurationError: If any required data (output context, channel record, guild record, LLM profiles) cannot be found or generated.
        """

        output_context = self.generate_output_context(channel_id)
        if not output_context:
            raise ConfigurationError(
                f"Could not generate output context for channel ID {channel_id}"
            )

        if channel:
            if not channel.is_ephemeral:
                raise ConfigurationError(
                    "Passing in non-ephemeral channel record is not allowed"
                )
        else:
            channel = await self._repos.channel_repo.get_channel(channel_id)
            if not channel:
                raise ConfigurationError(
                    f"No channel record found for channel ID {channel_id}"
                )

        guild_record = await self._repos.guild_repo.get_guild(channel.guild_id)
        if not guild_record:
            raise ConfigurationError(
                f"No guild record found for guild ID {channel.guild_id}"
            )

        llm_profiles = await self._repos.llm_profile_repo.get_profiles(channel_id)
        if not llm_profiles:
            raise ConfigurationError(
                f"No LLM profiles found for channel ID {channel_id}"
            )

        providers = {
            profile.provider_name: self._repos.provider_registry.get_provider(
                profile.provider_name
            )
            for profile in llm_profiles
        }

        context = SessionContext(
            channel=channel,
            guild=guild_record,
            output_context=output_context,
            llm_profiles=llm_profiles,
            providers=providers,
            global_config=self._repos.global_config,
        )

        # Set the active profile to the first one by default
        # TODO: Implement fail over logic
        context.set_active_profile(llm_profiles[0])

        return context

    async def create_conversation_session(
        self,
        channel_id: int,
        logger: Logger | None = None,
        channel: Channel | None = None,
    ) -> ConversationSession:
        """
        Create a ConversationSession for a given channel ID.

        Args:
            channel_id: The ID of the channel for which to create the conversation session.
            logger: Override logger for the session. If None, the factory's logger will be used.
            channel: If ephemeral, the Channel object for which to create the session.

        Returns:
            A ConversationSession instance initialized with the appropriate context and logger.

        Raises:
            ConfigurationError: If the session context cannot be created due to missing data.
        """
        context = await self.create_session_context(channel_id, channel)
        return ConversationSession(context=context, logger=logger or self._logger)
