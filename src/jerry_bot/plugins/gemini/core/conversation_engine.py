"""Unified conversation processing engine for all message types."""

import time

from ..models import (
    Message,
    UserMessage,
    ModelMessage,
    SystemMessage,
    ExceptionMessage,
    ToolResponseMessage,
)
from ..models.exceptions import ConversationInactivityTimeoutError
from ..dc_chat import LLMContextGenerator
from .context import SessionContext

import logging
import asyncio

class ConversationEngine:
    """Engine for processing conversations, including queue dynamic handling, message processing, and error management."""
    
    def __init__(self, context: SessionContext, logger: logging.Logger, context_generator: LLMContextGenerator):
        self._context = context
        self._history: list[Message] = []
        self._logger = logger
        self._context_generator = context_generator
        self._last_processed_time = time.monotonic()
        
        self._processing_task: asyncio.Task | None = None
        
    def add_message(self, message: Message, process: bool = True) -> None:
        """Add a message to the conversation history and optionally trigger processing of the conversation."""
        if self._check_inactivity_timeout():
            raise ConversationInactivityTimeoutError(
                "Cannot enqueue message because the conversation has been inactive for too long and has been stopped."
            )

        self._history.append(message)
        self._mark_activity()
            
        if process:
            self.process_conversation()
            
    def process_conversation(self):
        """Trigger processing of the conversation, cancelling ongoing processing task if present."""
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
        
        self._processing_task = asyncio.create_task(self._process_conversation(self._history.copy()))
        
    async def stop(self):
        """Stop the conversation engine, cancelling any ongoing processing task."""
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            
    async def _process_conversation(self, history: list[Message] | None = None):
        """Internal method to process the conversation, generating context and handling messages."""
        raise NotImplementedError("Conversation processing logic is not yet implemented.")
            
    def _mark_activity(self):
        """Record recent conversation activity for inactivity timeout checks."""
        self._last_processed_time = time.monotonic()

    def _check_inactivity_timeout(self) -> bool:
        """Check if the inactivity timeout has been exceeded."""
        if self._context.global_config.ephemeral_mode.timeout_seconds is None:
            return False
        elapsed = time.monotonic() - self._last_processed_time
        if elapsed > self._context.global_config.ephemeral_mode.timeout_seconds:
            self._logger.info(
                f"Inactivity timeout exceeded (elapsed {elapsed:.2f}s), stopping message processor."
            )
            return True
        return False

