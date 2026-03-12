"""Various async iterators for processing model response streams, such as splitting by paragraphs or extracting content."""

from typing import AsyncIterator
from ..models import ModelResponseStream
import asyncio

from .constants import DEFAULT_MAX_CHUNK_SIZE


async def split_paragraphs(
    iterator: AsyncIterator[ModelResponseStream],
    separator: str = "\n\n",
    start_flag: bool = False,
) -> AsyncIterator[ModelResponseStream]:
    """Async iterator that takes a stream of strings and yields chunks of text split by paragraphs, while respecting code blocks.

    Args:
        iterator: An async iterator that yields ModelResponseStream objects.
        separator: The string used to split paragraphs. Defaults to two newlines ("\n\n").
        start_flag: Whether to treat yielded chunks as the start of a new message by setting the 'start' flag in ModelResponseStream. Defaults to False.
    """
    buffer = ""

    async for response in iterator:
        if response.content is None:
            continue

        buffer += response.content

        # Process the buffer for complete paragraphs
        while separator in buffer:
            chunk, buffer = buffer.split(separator, 1)
            yield ModelResponseStream(content=chunk.strip(), start=start_flag)

        # Check for code block delimiters to avoid splitting inside code blocks
        if "```" in buffer:
            parts = buffer.split("```")
            for i in range(len(parts) - 1):
                if i % 2 == 0:  # Outside code block
                    yield ModelResponseStream(
                        content=parts[i].strip(), start=start_flag
                    )
                else:  # Inside code block
                    yield ModelResponseStream(
                        content=f"```{parts[i]}```", start=start_flag
                    )
            buffer = parts[-1]  # Remaining part after the last code block

    # Yield any remaining buffer content as a final chunk
    if buffer.strip():
        yield ModelResponseStream(content=buffer.strip(), start=start_flag)


async def enforce_cooldown(
    iterator: AsyncIterator[ModelResponseStream], cooldown: float
) -> AsyncIterator[ModelResponseStream]:
    """Async iterator that enforces a cooldown between yielding items from the input iterator.

    Args:
        iterator: An async iterator that yields ModelResponseStream objects.
        cooldown: The minimum number of seconds to wait between yielding items.
    """
    last_yield_time = 0.0

    async for response in iterator:
        current_time = asyncio.get_event_loop().time()
        time_since_last_yield = current_time - last_yield_time

        if time_since_last_yield < cooldown:
            await asyncio.sleep(cooldown - time_since_last_yield)

        yield response
        last_yield_time = asyncio.get_event_loop().time()


async def buffered_cooldown(
    iterator: AsyncIterator[ModelResponseStream],
    cooldown: float,
    separator: str = "",
    buffer_size: int = DEFAULT_MAX_CHUNK_SIZE,
) -> AsyncIterator[ModelResponseStream]:
    """Async iterator that merges chunks received within the cooldown window into a single chunk,
    yielding when the window expires or the buffer would exceed the character limit.

    Chunks that arrive within `cooldown` seconds of the first chunk in a window are merged
    together. If adding a chunk would exceed `buffer_size`, the current buffer is yielded
    immediately and a new window starts with that chunk.

    Args:
        iterator: An async iterator that yields ModelResponseStream objects.
        cooldown: The duration in seconds of each collection window. After the first chunk
                  in a window arrives, further chunks are merged until the window expires.
        separator: The string used to split paragraphs when merging chunks. Defaults to an empty string (no separator).
        buffer_size: The maximum number of characters to accumulate before yielding early.
                     Defaults to DEFAULT_MAX_CHUNK_SIZE.
    """
    # A producer task feeds items into a queue so that timing out a queue.get()
    # (via asyncio.shield) never corrupts the underlying iterator — unlike calling
    # asyncio.wait_for directly on __anext__(), which cancels the generator coroutine.
    queue: asyncio.Queue[ModelResponseStream | None | Exception] = asyncio.Queue()

    async def _producer() -> None:
        try:
            async for item in iterator:
                await queue.put(item)
            await queue.put(None)  # sentinel for successful completion
        except Exception as e:
            await queue.put(e)  # sentinel for error

    producer_task = asyncio.create_task(_producer())

    buffer = ""
    exhausted = False
    # Persisted future so a timed-out get() isn't discarded between windows.
    pending_get: asyncio.Future | None = None

    try:
        while not exhausted:
            # Block until the first chunk of the next window arrives.
            if pending_get is None:
                pending_get = asyncio.ensure_future(queue.get())
            response = await pending_get
            pending_get = None

            if response is None:
                break

            # Check if producer sent an exception
            if isinstance(response, Exception):
                raise response

            if response.content is not None:
                buffer += response.content + separator

            # Greedily collect more chunks until the cooldown window expires.
            deadline = asyncio.get_event_loop().time() + cooldown
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break

                if pending_get is None:
                    pending_get = asyncio.ensure_future(queue.get())

                try:
                    # shield keeps pending_get alive if wait_for times out.
                    response = await asyncio.wait_for(
                        asyncio.shield(pending_get), timeout=remaining
                    )
                    pending_get = None
                except asyncio.TimeoutError:
                    # Window expired; pending_get survives and becomes the first
                    # item of the next window.
                    break

                if response is None:
                    exhausted = True
                    break

                # Check if producer sent an exception
                if isinstance(response, Exception):
                    raise response

                if response.content is None:
                    continue

                if len(buffer) + len(response.content) > buffer_size:
                    # Would overflow — flush and start a fresh window.
                    if buffer:
                        yield ModelResponseStream(content=buffer)
                    buffer = response.content
                    deadline = asyncio.get_event_loop().time() + cooldown
                else:
                    buffer += response.content + separator

            if buffer:
                yield ModelResponseStream(content=buffer)
                buffer = ""

    finally:
        producer_task.cancel()
        await asyncio.gather(producer_task, return_exceptions=True)
        if pending_get is not None and not pending_get.done():
            pending_get.cancel()

    if buffer:
        yield ModelResponseStream(content=buffer)


async def live_character_buffer(
    iterator: AsyncIterator[ModelResponseStream],
    buffer_size: int = DEFAULT_MAX_CHUNK_SIZE,
) -> AsyncIterator[ModelResponseStream]:
    """Async iterator that forwards all chunks from the input iterator, but sets the 'start' flag so that the output can be treated as a live-updating buffer of text, with a specified maximum size."""
    buffer = ""

    async for response in iterator:
        if response.content is None:
            continue

        if len(buffer) + len(response.content) > buffer_size:
            yield ModelResponseStream(content=response.content, start=True)
            buffer = response.content
        else:
            yield ModelResponseStream(content=response.content, start=False)
            buffer += response.content
