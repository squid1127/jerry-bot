"""Message queue implementation for message processing within Gemini conversations."""

import asyncio
import logging
from typing import ClassVar, Protocol
from ..models import Message
from ..models.exceptions import (
    FatalError,
    ProviderError,
    ConversationInactivityTimeoutError,
)
import time


class TurnHandler(Protocol):
    """Protocol for types that can execute a single conversation turn."""

    async def run_turn(self, message: Message) -> None:
        """Run one turn for a queued message."""

    async def handle_exceptions(
        self, exception: Exception, message: Message | None = None
    ) -> None:
        """Handle an exception raised while processing a queued message."""


class MessageQueue:
    """Message queue implementation for message processing within Gemini conversations."""

    MAX_RETRIES: ClassVar[int] = 3

    def __init__(
        self,
        logger: logging.Logger,
        turn_handler: TurnHandler,
        inactive_timeout: int | None = None,
    ):
        self._queue: asyncio.Queue[Message] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._logger = logger
        self._turn_handler = turn_handler
        self._inactive_timeout = inactive_timeout
        self._last_processed_time = time.monotonic()

    def _mark_activity(self):
        """Record recent conversation activity for inactivity timeout checks."""
        self._last_processed_time = time.monotonic()

    def enqueue(self, message: Message):
        """Add a message to the queue."""
        if self._check_inactivity_timeout():
            raise ConversationInactivityTimeoutError(
                "Cannot enqueue message because the conversation has been inactive for too long and has been stopped."
            )

        self._mark_activity()
        self._queue.put_nowait(message)
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._worker())

    def _check_inactivity_timeout(self) -> bool:
        """Check if the inactivity timeout has been exceeded."""
        if self._inactive_timeout is None:
            return False
        elapsed = time.monotonic() - self._last_processed_time
        if elapsed > self._inactive_timeout:
            self._logger.info(
                f"Inactivity timeout exceeded (elapsed {elapsed:.2f}s), stopping message processor."
            )
            return True
        return False

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
        """Process a single queued message, returning any exception that occurs."""
        try:
            await self._turn_handler.run_turn(message)
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
            await self._turn_handler.handle_exceptions(error, message)

    async def _worker(self):
        """Worker that processes tasks from the queue."""
        while True:
            message = await self._queue.get()
            try:
                await self._process_with_retries(message)
            finally:
                self._mark_activity()
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
