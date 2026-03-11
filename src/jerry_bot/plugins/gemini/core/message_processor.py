"""Message processor implementation for handling message processing within Gemini conversations."""

import asyncio
import logging
from typing import TYPE_CHECKING
from ..models import (
    Message,
    UserMessage,
    ModelMessage,
    SystemMessage,
    ExceptionMessage,
    ModelContext,
    ModelResponseStream,
    ChannelContext,
)
from ..models.exceptions import FatalError, ProviderError
import traceback

if TYPE_CHECKING:
    from ..provider import Provider
    from ..config import GlobalConfig
from ..input import ContextGenerator
from ..output import (
    split_paragraphs,
    enforce_cooldown,
    live_character_buffer,
    buffered_cooldown,
    stream_and_send,
    stream_and_edit,
    typing_until_event,
)


class MessageProcessor:
    """Message processor implementation for handling message processing within Gemini conversations."""

    def __init__(
        self,
        logger: logging.Logger,
        provider: "Provider",
        channel_context: ChannelContext,
        global_config: "GlobalConfig",
        context_generator: ContextGenerator,
    ):
        self._logger = logger
        self._provider = provider
        self._context_generator = context_generator
        self._history: list[Message] = []
        self._channel_context = channel_context
        self._global_config = global_config

    async def process_message(self, message: Message) -> Message | None:
        """Process a single message. Returns a response message if applicable, or None if no response is needed."""
        if isinstance(message, UserMessage):
            return await self._process_user_message(message)
        elif isinstance(message, ModelMessage):
            return await self._process_model_message(message)
        # elif isinstance(message, SystemMessage):
        #     await self._process_system_message(message)
        # elif isinstance(message, ExceptionMessage):
        #     await self._process_exception_message(message)
        else:
            raise TypeError(f"Unsupported message type: {type(message)}")

    async def handle_exceptions(
        self, exception: Exception, message: Message | None = None
    ):
        """Handle exceptions that occur during message processing."""
        self._logger.error(
            f"Exception occurred while processing message: {exception} | "
        )
        traceback_str = traceback.format_exception(
            type(exception), exception, exception.__traceback__
        )
        self._logger.error(f"Traceback: {''.join(traceback_str)}")

        # Try to return the error to the provider unless it's a ProviderError, which indicates an issue with the provider itself rather than the message processing.
        if (not isinstance(message, ExceptionMessage)) and (
            not isinstance(exception, ProviderError)
        ):
            exception_message = ExceptionMessage(
                error=exception,
                fatal=isinstance(exception, FatalError),
                message=message,
            )
            try:
                await self.process_message(exception_message)
            except Exception as e:
                self._logger.error(f"Error while processing exception message: {e}")

    async def _process_user_message(self, message: UserMessage) -> ModelMessage | None:
        """Process a UserMessage."""
        self._logger.info(f"Processing UserMessage: {message.content}")
        self._history.append(message)

        context = self._context_generator.generate_context(self._history)
        await self._provider_request(context)

    async def _process_model_message(self, message: ModelMessage):
        """Process a ModelMessage."""
        self._logger.info(f"Processing ModelMessage: {message.content}")
        self._history.append(message)

    async def _provider_request(self, context: ModelContext) -> ModelMessage | None:
        """Make a request to the provider based on the message content."""

        generator = self._provider.generate(context)
        cooldown = self._global_config.message_send_cooldown
        event = asyncio.Event()
        pipeline = stream_and_edit(
            live_character_buffer(
                buffered_cooldown(
                    split_paragraphs(generator),
                    cooldown=cooldown,
                    separator="\n\n",
                ),
            ),
            channel_context=self._channel_context,
            first_message_event=event,
        )

        task = asyncio.create_task(typing_until_event(self._channel_context, event))
        try:
            result = await pipeline
        finally:
            if not event.is_set():
                event.set()
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

        self._logger.info("Completed provider response stream.")

        return ModelMessage(content=result.content) if result.content else None

    @property
    def history(self) -> list[Message]:
        """Get the conversation history."""
        return self._history.copy()
