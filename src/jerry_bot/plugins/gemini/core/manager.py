"""Conversation session manager for Gemini plugin."""

from ..repo import Repositories
from ..models import ConfigurationError, Message
from ..dc_chat import OutputContext
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
        self._logger = logger
        self._repos = repos

    async def get_session(
        self, channel_id: int, output_context: OutputContext | None = None, create: bool = False
    ) -> ConversationSession | None:
        """
        Retrieve an existing conversation session for a given channel ID, or create one if it doesn't exist.

        Args:
            channel_id: The ID of the Discord channel to retrieve or create a session for.
            output_context: The output context for the session.
            create: Whether to create a new session if one does not already exist.
        Returns:
            The ConversationSession for the given channel ID, or None if it does not exist and create is False.
        """

        if channel_id in self._sessions:
            return self._sessions[channel_id]

        if not create:
            return None
        
        if output_context is None:
            raise ConfigurationError("Output context must be provided when creating a new session")

        if not await self._factory.has_channel(channel_id):
            return None
    
        # Create a new session context and session
        session = await self._factory.create_conversation_session(channel_id=channel_id, output_context=output_context)
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
        self._sessions.pop(channel_id, None)  # Ensure the session is removed from the dictionary even if stop() raises an error

    async def stop_all(self, drain: bool = True) -> None:
        """
        Tear down all active conversation sessions.

        Args:
            drain: Whether to wait for all message queues to finish processing before tearing down sessions.
        """
        for channel_id, session in self._sessions.items():
            await session.stop(drain=drain)

    # * Message Routing *#
    async def route_message(
        self,
        message: Message,
        output_context: OutputContext,
        channel_id: int,
        allow_ephemeral: bool = False,
        create_mentionable: bool = False,
        quiet: bool = False,
    ) -> None:
        """
        Route an incoming message to the appropriate conversation session based on the channel ID.

        Args:
            message: The incoming message to route, in the form of a Gemini Message object.
            channel_id: The ID of the Discord channel the message was sent in, used to determine which session to route to.
            allow_ephemeral: Whether to allow the creation of ephemeral responses in this session.
            create_mentionable: Whether to create a mentionable response if the message is not already mentionable.
            quiet: Whether to ignore if no valid session is found for the channel.

        """

        session = await self.get_session(channel_id=channel_id, create=True, output_context=output_context)
        if not session:
            if quiet:
                return
            raise ValueError(
                f"Failed to create or retrieve session for channel ID {channel_id}."
            )

        session.enqueue(message)
