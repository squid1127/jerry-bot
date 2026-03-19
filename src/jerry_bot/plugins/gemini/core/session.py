"""Individual, channel-scoped conversations within the Gemini plugin."""

from logging import Logger
from typing import TYPE_CHECKING, Optional

from ..dc_chat import OutputContext

from .context import SessionContext
from ..models import ChannelRecord, GuildRecord, Message, LLMProfile
from .message_queue import MessageQueue
from .turn_engine import TurnEngine
from ..dc_chat import LLMContextGenerator


class ConversationSession:
    """Represents an individual conversation within a channel."""

    def __init__(
        self,
        context: SessionContext,
        logger: Logger,
    ):
        """Initialize a Conversation instance.

        Args:
            context: Contextual information about the channel.
            logger: Logger instance for logging.
        """

        self._logger = logger
        self._context = context

        # Processing components
        self._context_generator = LLMContextGenerator(context=self.context)
        self._turn_engine = TurnEngine(
            logger=self._logger,
            context=self.context,
            llm_context_generator=self._context_generator,
        )
        self._message_queue = MessageQueue(
            logger=self._logger,
            turn_handler=self._turn_engine,
            inactive_timeout=(
                self.context.global_config.ephemeral_mode.timeout_seconds
                if self.is_ephemeral
                else None
            ),  # Ephemeral conversations have an inactivity timeout, while regular conversations do not
        )

    def enqueue(self, message: Message) -> None:
        """Enqueue a message into this conversation session."""
        self._message_queue.enqueue(message)

    def add_message(self, message: Message) -> None:
        """Backward-compatible alias for enqueue."""
        self.enqueue(message)

    async def drain(self) -> None:
        """Wait for all queued messages to finish processing."""
        await self._message_queue.join()

    async def stop(self, drain: bool = True):
        """Stop the conversation, optionally draining the message queue first."""
        self._logger.debug(
            f"Stopping conversation for channel {self.channel_id} (drain={drain})."
        )
        await self._message_queue.stop(drain=drain)

    def clear_history(self) -> None:
        """Clear in-memory history for this conversation."""
        self._turn_engine.clear_history()

    @property
    def is_running(self) -> bool:
        """Check if the conversation processor is currently running."""
        return self._message_queue.is_running

    @property
    def queue_size(self) -> int:
        """Get the current size of the conversation queue."""
        return self._message_queue.queue_size

    @property
    def history(self) -> list[Message]:
        """Get a copy of conversation history."""
        return self._turn_engine.history

    @property
    def context(self) -> SessionContext:
        """Get the session context for this conversation."""
        return self._context

    @property
    def channel_id(self) -> int:
        """Get the ID of the channel this conversation is associated with."""
        return self._context.channel.channel_id

    @property
    def is_ephemeral(self) -> bool:
        """Check if this conversation is operating in ephemeral mode (not backed by a database Channel)."""
        return self.context.channel.is_ephemeral
