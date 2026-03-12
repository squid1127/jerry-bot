"""Message queue implementation for message processing within Gemini conversations."""

import asyncio
import logging
from typing import ClassVar
from ..models import Message
from ..models.exceptions import FatalError, ProviderError
from .message_processor import MessageProcessor


class MessageQueue:
    """Message queue implementation for message processing within Gemini conversations."""

    MAX_RETRIES: ClassVar[int] = 3

    def __init__(
        self,
        logger: logging.Logger,
        processor: MessageProcessor,
    ):
        self._queue: asyncio.Queue[Message] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._logger = logger
        self._processor = processor

    def enqueue(self, message: Message):
        """Add a message to the queue."""
        self._queue.put_nowait(message)
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._worker())

    async def join(self):
        """Wait until all tasks in the queue have been processed."""
        await self._queue.join()

    async def stop(self, drain: bool = True):
        """Stop the worker, optionally draining the queue first."""
        if drain:
            await self.join()
        if self._task is not None:
            self._task.cancel()

            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _process_message(
        self, message: Message, attempt: int | str = "unknown"
    ) -> Exception | None:
        """Process a single message, returning any exception that occurs."""
        try:
            response: Message | None = await self._processor.process_message(message)
        except asyncio.CancelledError:
            raise
        except FatalError as e:
            self._logger.error(
                f"Fatal error processing message — aborting retries: {e}"
            )
            return e
        except ProviderError as e:
            self._logger.error(
                f"Provider error processing message — aborting retries: {e}"
            )
            return e
        except Exception as e:
            self._logger.error(
                f"Error processing message (attempt {attempt}/{self.MAX_RETRIES}): {e}"
            )
            return e
        else:
            if response:
                return await self._process_with_retries(response)
            return None

    async def _process_with_retries(self, message: Message):
        """Process a message with retry logic."""
        error = None
        attempt = 0
        for attempt in range(1, self.MAX_RETRIES + 1):
            error = await self._process_message(message, attempt)
            if error is None or isinstance(error, (FatalError, ProviderError)):
                break
        if error:
            self._logger.error(
                f"Failed to process message after {attempt} attempts: {message}"
            )
            await self._processor.handle_exceptions(error, message)

    async def _worker(self):
        """Worker that processes tasks from the queue."""
        while True:
            message = await self._queue.get()

            await self._process_with_retries(message)
            self._queue.task_done()

    @property
    def is_running(self) -> bool:
        """Check if the worker is currently running."""
        return self._task is not None and not self._task.done()

    @property
    def queue_size(self) -> int:
        """Get the current size of the queue."""
        return self._queue.qsize()

    async def __aenter__(self):
        """Enter the async context manager."""
        return self

    async def __aexit__(self, *_):
        """Exit the async context manager, ensuring the worker is stopped."""
        await self.stop()
