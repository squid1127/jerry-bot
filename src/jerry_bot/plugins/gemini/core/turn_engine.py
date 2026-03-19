"""Turn engine for orchestrating one conversation turn at a time."""

import asyncio
from dataclasses import dataclass
import logging
import traceback
from typing import TYPE_CHECKING, AsyncIterator

from .context import SessionContext

from ..dc_chat import LLMContextGenerator, OutputContext
from ..models import (
    ExceptionMessage,
    FunctionCall,
    FunctionResponseMessage,
    Message,
    LLMContext,
    ModelMessage,
    LLMResponseStream,
    SystemMessage,
    UserMessage,
)
from ..models.exceptions import FatalError, FunctionCallError, ProviderError
from ..dc_chat import (
    buffered_cooldown,
    live_character_buffer,
    send_error_message,
    split_paragraphs,
    start_typing_until_event,
    stream_and_edit,
)


@dataclass(slots=True)
class ProviderRoundResult:
    """Result of one provider round in an agentic turn."""

    text: str | None
    function_calls: list[FunctionCall]


class TurnEngine:
    """Processes a single inbound message into a complete model turn."""

    def __init__(
        self,
        logger: logging.Logger,
        context: SessionContext,
        llm_context_generator: LLMContextGenerator,
        max_function_rounds: int = 4,
    ):
        self._logger = logger
        self._history: list[Message] = []
        self._max_function_rounds = max(1, max_function_rounds)
        self._context = context
        self._context_generator = llm_context_generator

    async def run_turn(self, message: Message) -> None:
        """Run one turn for an inbound message."""
        if isinstance(message, UserMessage):
            await self._run_user_message(message)
            return

        if isinstance(message, ModelMessage):
            self._record_model_message(message)
            return

        if isinstance(message, SystemMessage):
            await self._run_system_message(message)
            return

        if isinstance(message, ExceptionMessage):
            await self._run_exception_message(message)
            return

        raise TypeError(f"Unsupported message type: {type(message)}")

    async def handle_exceptions(
        self, exception: Exception, message: Message | None = None
    ) -> None:
        """Handle exceptions that occur during turn execution."""
        self._logger.error(
            f"Exception occurred while processing message: {exception} | "
        )
        traceback_str = traceback.format_exception(
            type(exception), exception, exception.__traceback__
        )
        self._logger.error(f"Traceback: {''.join(traceback_str)}")

        if isinstance(exception, ProviderError):
            await send_error_message(
                output=self._context.output_context,
                content=str(exception),
                title=f"{type(exception).__name__} ❌",
            )
            return

        if isinstance(message, ExceptionMessage):
            return

        exception_message = ExceptionMessage(
            error=exception,
            fatal=isinstance(exception, FatalError),
            message=message,
        )
        try:
            await self.run_turn(exception_message)
        except Exception as nested_error:
            self._logger.error(
                f"Error while processing exception message: {nested_error}"
            )

    async def _run_user_message(self, message: UserMessage) -> None:
        """Process a user message turn."""
        self._logger.info(f"Processing UserMessage: {message.content}")
        self._history.append(message)

        await self._run_agentic_loop()

    def _record_model_message(self, message: ModelMessage) -> None:
        """Persist a model message in turn history."""
        if message.function_call is not None:
            self._logger.info(
                f"Processing ModelMessage function call: {message.function_call.name}"
            )
        else:
            self._logger.info(f"Processing ModelMessage: {message.content}")
        self._history.append(message)

    def _record_function_response(self, message: FunctionResponseMessage) -> None:
        """Persist a function response message in turn history."""
        outcome = "error" if message.error else "success"
        self._logger.info(
            f"Processing FunctionResponseMessage ({outcome}): "
            f"{message.function_call.name}"
        )
        self._history.append(message)

    async def _run_system_message(self, message: SystemMessage) -> None:
        """Process a system message turn."""
        self._logger.info(f"Processing SystemMessage: {message.content}")
        self._history.append(message)

        await self._run_agentic_loop()

    async def _run_exception_message(self, message: ExceptionMessage) -> None:
        """Process an exception message turn."""
        self._logger.info(f"Processing ExceptionMessage: {message.content}")
        self._history.append(message)

        await send_error_message(
            output=self._context.output_context,
            content=f"Something went wrong while processing a message: {message.error}",
            title=f"{'[FATAL] ' if message.fatal else ''}{type(message.error).__name__} occurred ❌",
        )

        if message.fatal:
            self._logger.error(f"Fatal error occurred: {message.content}")
            return

        await self._run_agentic_loop()

    async def _run_agentic_loop(self) -> None:
        """Run model->function->model rounds until the model produces a final text response."""
        for round_index in range(1, self._max_function_rounds + 1):
            context = self._context_generator.generate_context(self._history)
            round_result = await self._provider_round(context)

            if round_result.text:
                self._record_model_message(ModelMessage(content=round_result.text))

            if not round_result.function_calls:
                return

            self._logger.info(
                f"Provider requested {len(round_result.function_calls)} function call(s) "
                f"in round {round_index}/{self._max_function_rounds}."
            )

            for function_call in round_result.function_calls:
                self._record_model_message(ModelMessage(function_call=function_call))

            #! Function call execution is currently disabled
            # if self._function_executor is None:
            #     raise FunctionCallError(
            #         "Provider requested function calls but no function executor is configured."
            #     )

            # responses = await self._function_executor.execute_many(
            #     round_result.function_calls
            # )
            # for response in responses:
            #     self._record_function_response(response)

        raise FunctionCallError(
            "Exceeded maximum function-call rounds without producing a final response."
        )

    async def _provider_round(self, context: LLMContext) -> ProviderRoundResult:
        """Generate one provider round and capture both text and function calls."""
        generator = self._context.provider.generate(context)
        function_calls: list[FunctionCall] = []
        cooldown = self._context.global_config.message_send_cooldown

        typing_task, event = start_typing_until_event(self._context.output_context)

        pipeline = stream_and_edit(
            live_character_buffer(
                buffered_cooldown(
                    split_paragraphs(
                        self._extract_text_chunks(generator, function_calls)
                    ),
                    cooldown=cooldown,
                    separator="\n\n",
                ),
            ),
            output=self._context.output_context,
            first_message_event=event,
        )

        try:
            result = await pipeline
        except (ProviderError, FatalError):
            raise
        except Exception as error:
            self._logger.error(f"Unexpected error during provider request: {error}")
            raise
        finally:
            event.set()
            await typing_task

        self._logger.info("Completed provider response stream.")
        text = result.content.strip() if result.content else None
        return ProviderRoundResult(text=text, function_calls=function_calls)

    async def _extract_text_chunks(
        self,
        iterator: AsyncIterator[LLMResponseStream],
        function_calls: list[FunctionCall],
    ) -> AsyncIterator[LLMResponseStream]:
        """Split provider chunks into text stream output and captured function calls."""
        async for chunk in iterator:
            if chunk.function_call is not None:
                function_calls.append(chunk.function_call)

            if chunk.content is not None:
                yield LLMResponseStream(content=chunk.content, start=chunk.start)

    def clear_history(self) -> None:
        """Clear the conversation turn history."""
        self._history.clear()

    @property
    def history(self) -> list[Message]:
        """Get the conversation turn history."""
        return self._history.copy()
