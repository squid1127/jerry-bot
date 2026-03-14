"""Individual, channel-scoped conversations within the Gemini plugin."""

from logging import Logger
from typing import TYPE_CHECKING, Optional

from ..models import Channel, Guild, Message, ChannelContext, Model
from .message_queue import MessageQueue
from .message_processor import MessageProcessor
from ..input import ContextGenerator

if TYPE_CHECKING:
    from ..provider import Provider
    from ..config import GlobalConfig


class Conversation:
    """Represents an individual conversation within a channel."""

    def __init__(
        self,
        channel_context: ChannelContext,
        guild: Guild,
        logger: Logger,
        provider: "Provider",
        model: Model,
        global_config: GlobalConfig,
        channel: Optional[Channel] = None,
        channel_id: Optional[int] = None,
    ):
        """Initialize a Conversation instance.
        
        Args:
            channel_context: Contextual information about the channel.
            guild: The Guild configuration for this conversation.
            logger: Logger instance for logging.
            provider: The provider instance for API interactions.
            model: The model configuration to use for this conversation.
            channel: Optional Channel database model instance.
            channel_id: Optional channel ID (required if channel is not provided), enables ephemeral mode.
            """
        if (channel is None) and (channel_id is None):
            raise ValueError("Either channel or channel_id must be provided.")
        if (channel is not None) and (channel_id is not None):
            raise ValueError("Only one of channel or channel_id can be provided.")
        
        self.channel = channel
        self.channel_id = channel_id or (channel and channel.channel_id)
        self._channel_context = channel_context
        self.guild = guild
        self._logger = logger
        self._provider = provider
        self._global_config = global_config
        
        # Processing components
        self._context_generator = ContextGenerator(
            global_config=self._global_config,
            model_config=model,
            guild_config=self.guild,
            channel_config=self.channel,
            ephemeral=self.is_ephemeral,
        )
        self._processor = MessageProcessor(
            logger=self._logger,
            provider=self._provider,
            channel_context=self._channel_context,
            context_generator=self._context_generator,
            global_config=self._global_config,
        )
        self._message_queue = MessageQueue(
            logger=self._logger,
            processor=self._processor,
            inactive_timeout=self._global_config.ephemeral_mode.timeout_seconds if self.is_ephemeral else None,  # Ephemeral conversations have an inactivity timeout, while regular conversations do not
        )

    def add_message(self, message: Message):
        self._message_queue.enqueue(message)

    async def stop(self, drain: bool = True):
        """Stop the conversation, optionally draining the message queue first."""
        self._logger.debug(
            f"Stopping conversation for channel {self.channel_id} (drain={drain})."
        )
        await self._message_queue.stop(drain=drain)

    @property
    def is_running(self) -> bool:
        """Check if the conversation processor is currently running."""
        return self._message_queue.is_running
    
    @property
    def is_ephemeral(self) -> bool:
        """Check if this conversation is operating in ephemeral mode (not backed by a database Channel)."""
        return self.channel is None