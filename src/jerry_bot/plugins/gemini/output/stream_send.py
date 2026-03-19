"""Stream and send model output as messages dynamically."""

from typing import AsyncIterator
from ..models import OutputContext, LLMResponseStream, FatalError
import discord
import asyncio

from ..constants import DEFAULT_TYPING_TIMEOUT, FORBIDDEN_ERROR_MESSAGE


async def stream_and_send(
    message_generator: AsyncIterator[LLMResponseStream],
    channel_context: OutputContext,
    first_message_event: asyncio.Event | None = None,
) -> LLMResponseStream:
    """Stream and send each chunk to the Discord channel as it is generated.

    Args:
        message_generator: An async iterator that yields ModelResponseStream objects.
        channel_context: The context of the channel to send messages in.
        first_message_event: An optional asyncio.Event that will be set after the first message chunk is sent, allowing the caller to know when the first message has been sent.
    Returns:
        ModelResponseStream: The full response content after streaming is complete.
    """
    channel: discord.TextChannel = channel_context.channel
    buffer = ""
    event_set = False

    try:
        async for chunk in message_generator:
            if chunk.content is None:
                continue

            if not event_set and first_message_event is not None:
                first_message_event.set()
                event_set = True

            buffer += chunk.content
            await channel.send(chunk.content)
    except discord.Forbidden as e:
        raise FatalError(FORBIDDEN_ERROR_MESSAGE) from e

    return LLMResponseStream(content=buffer)


async def stream_and_edit(
    message_generator: AsyncIterator[LLMResponseStream],
    output: OutputContext,
    first_message_event: asyncio.Event | None = None,
) -> LLMResponseStream:
    """Stream and send each chunk to the Discord channel as it is generated, editing the same message with new content instead of sending multiple messages.

    Args:
        message_generator: An async iterator that yields ModelResponseStream objects.
        channel_context: The context of the channel to send messages in.
        first_message_event: An optional asyncio.Event that will be set after the first message chunk is sent, allowing the caller to know when the first message has been sent.
    Returns:
        ModelResponseStream: The full response content after streaming is complete.
    """
    channel = output.channel
    sent_message = None
    buffer = ""
    global_buffer = ""
    event_set = False

    try:

        async for chunk in message_generator:
            if chunk.content is None:
                continue

            if not event_set and first_message_event is not None:
                first_message_event.set()
                event_set = True

            global_buffer += chunk.content
            if sent_message is None or chunk.start:

                sent_message = await channel.send(chunk.content)
                buffer = chunk.content
            else:
                buffer += chunk.content
                await sent_message.edit(content=buffer)
    except discord.Forbidden as e:
        raise FatalError(FORBIDDEN_ERROR_MESSAGE) from e

    return LLMResponseStream(content=global_buffer)


def start_typing_until_event(
    channel_context: OutputContext,
    timeout: float = DEFAULT_TYPING_TIMEOUT,
) -> tuple[asyncio.Task, asyncio.Event]:
    """Start the typing indicator and return a task and event to control it.

    The typing indicator will remain active until the returned event is set.
    Automatically handles Discord's typing timeout by refreshing the indicator.

    Args:
        channel_context: The context of the channel to show typing in.
        timeout: The maximum time in seconds to wait before refreshing the typing indicator. Should be less than Discord's ~10s timeout.

    Returns:
        tuple: (typing_task, stop_event) - Set the event to stop typing,
               await the task to ensure cleanup is complete.

    Example:
        typing_task, event = start_typing_until_event(channel_context)
        try:
            # Do work, pass event to stream functions
            result = await some_operation(event)
        finally:
            event.set()
            await typing_task
    """
    stop_event = asyncio.Event()
    channel = channel_context.channel

    async def _typing_loop():
        """Keep typing indicator active, handling Discord's ~10s timeout."""
        while not stop_event.is_set():
            async with channel.typing():
                try:
                    # Wait for stop event with timeout slightly less than Discord's limit
                    await asyncio.wait_for(stop_event.wait(), timeout=timeout)
                    break  # Event was set, exit cleanly
                except asyncio.TimeoutError:
                    # Typing expired, loop will restart it
                    continue

    task = asyncio.create_task(_typing_loop())
    return task, stop_event


async def send_success_message(
    channel_context: OutputContext, content: str, title: str = "Success ✅"
) -> None:
    """Send a success message to the channel."""
    channel = channel_context.channel
    embed = discord.Embed(title=title, description=content, color=discord.Color.green())
    try:
        await channel.send(embed=embed)
    except discord.Forbidden as e:
        raise FatalError(FORBIDDEN_ERROR_MESSAGE) from e


async def send_error_message(
    output: OutputContext, content: str, title: str = "Error ❌"
) -> None:
    """Send an error message to the channel."""
    channel = output.channel
    embed = discord.Embed(title=title, description=content, color=discord.Color.red())
    try:
        await channel.send(embed=embed)
    except discord.Forbidden as e:
        raise FatalError(FORBIDDEN_ERROR_MESSAGE) from e
