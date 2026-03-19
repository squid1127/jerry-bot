"""Conversation session manager for Gemini plugin."""

from ..repo import Repositories
from ..models import ConfigurationError
from .factory import ConversationFactory
from .session import ConversationSession

from discord.ext.commands import Bot
from logging import Logger


class ConversationManager:
    """
    Manager for handling conversation sessions within the Gemini plugin.
    """

    def __init__(
        self,
        repos: Repositories,
        bot: Bot,
        logger: Logger,
    ):
        """
        Initialize the ConversationManager with necessary dependencies.

        Args:
            global_config: The global configuration for the Gemini plugin.
            bot: The instance of the Discord Bot, used for generating Discord context objects.
        """
        self._factory = ConversationFactory(repos=repos, bot=bot, logger=logger)
        self._sessions: dict[int, ConversationSession] = {}

    async def get_session(
        self, channel_id: int, create: bool = False
    ) -> ConversationSession | None:
        """
        Retrieve an existing conversation session for a given channel ID, or create one if it doesn't exist.

        Args:
            channel_id: The ID of the Discord channel to retrieve or create a session for.
            create: Whether to create a new session if one does not already exist.
        Returns:
            The ConversationSession for the given channel ID, or None if it does not exist and create is False.
        """

        if channel_id in self._sessions:
            return self._sessions[channel_id]

        if not create:
            return None

        # Create a new session context and session
        session = await self._factory.create_conversation_session(channel_id=channel_id)
        self._sessions[channel_id] = session
        return session

    async def stop_session(self, channel_id: int) -> None:
        """
        Tear down an existing conversation session for a given channel ID.

        Args:
            channel_id: The ID of the Discord channel to tear down the session for.
        """
        if channel_id in self._sessions:
            session = self._sessions.pop(channel_id)
            await session.stop()
        else:
            raise ValueError(f"No active session found for channel ID {channel_id}.")

    async def stop_all(self, drain: bool = True) -> None:
        """
        Tear down all active conversation sessions.

        Args:
            drain: Whether to wait for all message queues to finish processing before tearing down sessions.
        """
        for channel_id, session in self._sessions.items():
            await session.stop(drain=drain)
            self._sessions.pop(channel_id)
