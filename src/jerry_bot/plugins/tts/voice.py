"""Voice chat handler for TTS"""

import discord
import asyncio
from pathlib import Path
from dataclasses import dataclass

from .models.exceptions import (
    TTSVoiceError,
    TTSVoiceConnectionError,
    TTSVoiceInUseError,
)


from .models.ratelimit import RateLimiter

@dataclass(frozen=True, slots=True, order=True)
class TTSVoiceQueueItem:
    """Represents an item in the TTS voice queue"""

    user: discord.Member
    file: Path

class TTSVoiceClient:
    """Represents a voice client connected for tts in a guild."""

    def __init__(self, guild: discord.Guild, timeout: float = 600.0):
        """Initialize TTSVoiceChannel

        Args:
            guild (Guild): The guild that client corresponds too
            timeout (float): Seconds after the last request before the request times out (defaults to 600)
        """

        self.guild = guild
        self.timeout = timeout
        self._playback_queue: asyncio.Queue[TTSVoiceQueueItem] = asyncio.Queue()
        self._playback_task: asyncio.Task | None = None
        self._rate_limiter: RateLimiter = RateLimiter(max_calls=10, period=30.0)
        self._timeout_task: asyncio.Task | None = None
        self._voice_client: discord.VoiceClient | None = None

    def enqueue(self, user: discord.Member, file: Path):
        """
        Enqueue a file to the playback queue

        Args:
            user (Member): Member that requested the voice
            file (Path): Path to the file to be played
        """

        item = TTSVoiceQueueItem(user=user, file=file)
        self._playback_queue.put_nowait(item)
        self._ensure_running()

    def _ensure_running(self):
        """Ensure the playback task is running"""
        if self._playback_task is None or self._playback_task.done():
            self._playback_task = asyncio.create_task(self._playback_loop())

    async def _playback_loop(self):
        """Playback loop that plays files in the queue"""
        while not self._playback_queue.empty():
            item = await self._playback_queue.get()
            try:
                await self._rate_limiter.acquire()
                await self._play_file(item)
                await self._reset_timeout()
            except Exception as e:
                raise TTSVoiceError(f"Error playing {item}: {e}")
            finally:
                self._playback_queue.task_done()

    async def stop(self, from_timeout: bool = False):
        """Stop the playback loop and clear the queue"""
        if self._playback_task is not None:
            self._playback_task.cancel()
            if self.voice_client is not None and self.voice_client.is_connected():
                await self.voice_client.disconnect(force=True)
            try:
                await self._playback_task
            except asyncio.CancelledError:
                pass
            self._playback_task = None
        while not self._playback_queue.empty():
            self._playback_queue.get_nowait()
            self._playback_queue.task_done()
        
        # Cancel the timeout task if it exists and this stop was not called from the timeout watcher
        if not from_timeout and self._timeout_task is not None:
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass
            self._timeout_task = None

    async def _play_file(self, item: TTSVoiceQueueItem):
        """Play a file in the current channel"""

        if item.user.voice is None or item.user.voice.channel is None:
            raise TTSVoiceConnectionError(f"User {item.user} is not in a voice channel")
        user_channel = item.user.voice.channel
        
        # Ensure the voice client is connected to the correct channel
        try:
            if self._voice_client is not None and self._voice_client.channel != user_channel:
                await self._voice_client.disconnect(force=True)
                self._voice_client = await user_channel.connect()
            elif self._voice_client is None:
                self._voice_client = await user_channel.connect()
            if not self._voice_client.is_connected():
                await self._voice_client.connect(reconnect=True, timeout=10.0)
                
        except discord.ClientException as e:
            raise TTSVoiceInUseError(f"Voice client is already in use: {e}")
        except discord.Forbidden as e:
            raise TTSVoiceConnectionError(f"Bot does not have permission to connect to the voice channel: {e}")
        except discord.HTTPException as e:
            raise TTSVoiceConnectionError(f"Failed to connect to voice channel {user_channel}: {e}")

        voice_client = self._voice_client

        if not voice_client.is_connected():
            raise TTSVoiceConnectionError("Voice client is not connected")

        # Play the file
        source = discord.FFmpegPCMAudio(str(item.file))
        loop = asyncio.get_running_loop()
        playback_finished = asyncio.Event()
        playback_error: list[Exception] = []

        def on_playback_finished(error: Exception | None):
            if error is not None:
                playback_error.append(error)
            loop.call_soon_threadsafe(playback_finished.set)

        voice_client.play(source, after=on_playback_finished)

        # Wait for the file to finish playing
        await playback_finished.wait()
        if playback_error:
            raise playback_error[0]

    async def _watch_timeout(self):
        """Watch for timeout and stop playback if no new files are enqueued"""
        try:
            await asyncio.sleep(self.timeout)
            await self.stop(from_timeout=True)
        except asyncio.CancelledError:
            pass
        
    async def _reset_timeout(self):
        """Reset the timeout watcher"""
        if self._timeout_task is not None:
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass
        self._timeout_task = asyncio.create_task(self._watch_timeout())

    def is_empty(self) -> bool:
        """Whether the queue is empty"""
        return self._playback_queue.empty()

    @property
    def voice_client(self) -> discord.VoiceClient | None:
        """The voice client for the guild"""
        
        return self._voice_client
