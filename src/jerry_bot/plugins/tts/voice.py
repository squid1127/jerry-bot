"""Voice chat handler for TTS"""

import discord
import asyncio
from pathlib import Path

from .models.exceptions import (
    TTSVoiceError,
    TTSVoiceConnectionError,
    TTSVoiceInUseError,
)


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
        self._playback_channel: discord.VoiceChannel | None = None
        self._playback_queue: asyncio.Queue[Path] = asyncio.Queue()
        self._playback_task: asyncio.Task | None = None

    def enqueue(self, channel: discord.VoiceChannel, file: Path):
        """
        Enqueue a file to the playback queue

        Args:
            channel (VoiceChannel): Voice channel voice should be played in
        """

        if channel != self._playback_channel:
            if self._playback_queue.empty():
                self._playback_channel = channel
            else:
                raise TTSVoiceInUseError(f"This guild is already playing in {self._playback_channel}")
        
        
    @property
    def channel(self) -> discord.VoiceChannel | None:
        """The last channel files have been played in"""
        
        return self._playback_channel
    
    def is_empty(self) -> bool:
        """Whether the queue is empty"""
        return self._playback_queue.empty()