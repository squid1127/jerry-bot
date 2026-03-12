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
    start_typing_until_event,
    send_error_message,
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
        elif isinstance(message, SystemMessage):
            await self._process_system_message(message)
        elif isinstance(message, ExceptionMessage):
            await self._process_exception_message(message)
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
        if isinstance(exception, ProviderError):
            # Send error message directly to the channel for provider errors
            await send_error_message(
                channel_context=self._channel_context,
                content=str(exception),
                title=f"{type(exception).__name__} ❌",
            )
        elif not isinstance(message, ExceptionMessage):
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
        return await self._provider_request(context)

    async def _process_model_message(self, message: ModelMessage):
        """Process a ModelMessage."""
        self._logger.info(f"Processing ModelMessage: {message.content}")
        self._history.append(message)

    async def _process_system_message(self, message: SystemMessage):
        """Process a SystemMessage."""
        self._logger.info(f"Processing SystemMessage: {message.content}")
        self._history.append(message)

        context = self._context_generator.generate_context(self._history)
        await self._provider_request(context)

    async def _process_exception_message(self, message: ExceptionMessage):
        """Process an ExceptionMessage."""
        self._logger.info(f"Processing ExceptionMessage: {message.content}")
        self._history.append(message)

        await send_error_message(
            channel_context=self._channel_context,
            content=f"Something went wrong while processing a message: {message.error}",
            title=f"{'[FATAL] ' if message.fatal else ''}{type(message.error).__name__} occurred ❌",
        )

        if message.fatal:
            self._logger.error(f"Fatal error occurred: {message.content}")
            return None  # Do not attempt to process fatal errors further

        context = self._context_generator.generate_context(self._history)
        return await self._provider_request(context)

    async def _provider_request(self, context: ModelContext) -> ModelMessage | None:
        """Make a request to the provider based on the message content."""

        generator = self._provider.generate(context)
        cooldown = self._global_config.message_send_cooldown

        typing_task, event = start_typing_until_event(self._channel_context)
        
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

        try:
            result = await pipeline
        except (ProviderError, FatalError):
            # Re-raise provider errors and fatal errors to be handled by the queue
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error during provider request: {e}")
            raise
        finally:
            event.set()
            await typing_task

        self._logger.info("Completed provider response stream.")

        return ModelMessage(content=result.content.strip()) if result.content else None

    def clear_history(self):
        """Clear the conversation history."""
        self._history.clear()

    @property
    def history(self) -> list[Message]:
        """Get the conversation history."""
        return self._history.copy()
