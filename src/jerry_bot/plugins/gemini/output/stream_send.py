"""Stream and send model output as messages dynamically."""

from typing import AsyncIterator
from ..models import ChannelContext, ModelResponseStream, FatalError
import discord
import asyncio

async def stream_and_send(
    message_generator: AsyncIterator[ModelResponseStream],
    channel_context: ChannelContext,
    first_message_event: asyncio.Event | None = None,
) -> ModelResponseStream:
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
        raise FatalError("Bot does not have permission to send messages in this channel.") from e
    
    return ModelResponseStream(content=buffer)
        
async def stream_and_edit(
    message_generator: AsyncIterator[ModelResponseStream],
    channel_context: ChannelContext,
    first_message_event: asyncio.Event | None = None,
) -> ModelResponseStream:
    """Stream and send each chunk to the Discord channel as it is generated, editing the same message with new content instead of sending multiple messages.
    
    Args:
        message_generator: An async iterator that yields ModelResponseStream objects.
        channel_context: The context of the channel to send messages in.
        first_message_event: An optional asyncio.Event that will be set after the first message chunk is sent, allowing the caller to know when the first message has been sent.
    Returns:
        ModelResponseStream: The full response content after streaming is complete.
    """
    channel = channel_context.channel
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
        raise FatalError("Bot does not have permission to send messages in this channel.") from e
    
    return ModelResponseStream(content=global_buffer)

async def typing_until_event(channel_context: ChannelContext, stop_event: asyncio.Event):
    """Start the typing indicator in the channel and keep it active until the stop_event is set."""
    channel = channel_context.channel

    async with channel.typing():
        await stop_event.wait()
    
    return stop_event