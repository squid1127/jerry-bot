"""Individual, channel-scoped conversations within the Gemini plugin."""

from logging import Logger
from typing import TYPE_CHECKING
import discord

from ..models import Channel, Guild, Message, ChannelContext
from .message_queue import MessageQueue
from .message_processor import MessageProcessor
from ..input import ContextGenerator

if TYPE_CHECKING:
    from ..provider import Provider


class Conversation:
    """Represents an individual conversation within a channel."""

    def __init__(
        self,
        channel: Channel,
        channel_context: ChannelContext,
        guild: Guild,
        logger: Logger,
        provider: "Provider",
    ):
        self.channel = channel
        self.channel_context = channel_context
        self.guild = guild
        self.logger = logger
        self.provider = provider

        # Processing components
        self.context_generator = ContextGenerator(
            global_config=provider.global_config,
            model_config=provider.default_model,
            guild_config=self.guild,
        )
        self.processor = MessageProcessor(
            logger=self.logger,
            provider=self.provider,
            channel_context=self.channel_context,
            context_generator=self.context_generator,
            global_config=provider.global_config,
        )
        self.message_queue = MessageQueue(
            logger=self.logger,
            processor=self.processor,
        )

    def add_message(self, message: Message):
        self.message_queue.enqueue(message)

    async def stop(self, drain: bool = True):
        """Stop the conversation, optionally draining the message queue first."""
        self.logger.debug(
            f"Stopping conversation for channel {self.channel.channel_id} (drain={drain})."
        )
        await self.message_queue.stop(drain=drain)
