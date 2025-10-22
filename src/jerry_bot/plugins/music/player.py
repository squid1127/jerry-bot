"""Music player module."""

from .queue import MusicQueue
from .models import Track, Playlist

import discord
from enum import Enum

import asyncio
from typing import Optional, Callable
import logging

class PlayerState(Enum):
    """Enum representing the state of the music player."""

    IDLE = "Idle"
    PLAYING = "Playing"
    PAUSED = "Paused"
    KILL = "Stopping"


class MusicPlayer:
    """Class representing a music player."""

    def __init__(self, guild: discord.Guild, logger: logging.Logger):
        self.queue = MusicQueue()
        self.guild: discord.Guild = guild
        self.channel: discord.VoiceChannel | None = None
        self.state: PlayerState = PlayerState.IDLE
        self.client: discord.VoiceClient | None = None
        self.current_track: Track | None = None
        self.logger = logger
        self.update_listeners: list[Callable[[], None]] = []
        
    def add_update_listener(self, listener: Callable[[], None]) -> None:
        """Add a listener to be called on player updates."""
        self.update_listeners.append(listener)
        
    def remove_update_listener(self, listener: Callable[[], None]) -> None:
        """Remove a listener from the update listeners."""
        if listener in self.update_listeners:
            self.update_listeners.remove(listener)

    async def switch_channel(self, channel: discord.VoiceChannel) -> None:
        """Switch the voice channel the player is connected to."""
        if self.state != PlayerState.IDLE:
            raise NotImplementedError(
                "Switching channels while playing is not implemented yet."
            )
        self.channel = channel

    async def connect(self) -> None:
        """Connect to the voice channel."""
        if self.channel is None:
            raise ValueError("Voice channel is not set.")
        if self.client is not None and self.client.is_connected():
            return
        self.logger.info(f"Connecting to voice channel: {self.channel.name}")
        self.client = await self.channel.connect()

    async def disconnect(self) -> None:
        """Disconnect from the voice channel."""
        if self.client is not None and self.client.is_connected():
            await self.client.disconnect()
            self.logger.info(f"Disconnected from voice channel: {self.channel.name}")
            self.client = None
    
    def clear_update_listeners(self) -> None:
        """Clear all update listeners (useful during shutdown)."""
        self.update_listeners.clear()

    async def _loop(self) -> None:
        """Internal method to handle the playback loop."""
        self.logger.info(f"Starting playback loop for channel: {self.channel.name}")
        if self.queue.is_empty():
            return
        try:
            if self.state != PlayerState.IDLE:
                raise RuntimeError("Player is already running.")
            self.state = PlayerState.PLAYING

            await self.connect()

            # Loop to play tracks from the queue
            self.logger.info("Entering playback loop.")
            while True:
                if self.state == PlayerState.KILL:
                    break

                if self.queue.is_empty():
                    break
                
                current_track = self.queue.pop_next()
                if not current_track:
                    self.logger.warning("Uncaught empty track in queue.")
                    break
                self.logger.info(f"Playing track: {current_track.title}")
                await self._play_track(current_track)

        except Exception as e:
            self.logger.error(f"Error in playback loop: {e}")
        finally:
            self.logger.info(f"Exiting playback loop for channel: {self.channel.name}")
            self.state = PlayerState.IDLE
            self.current_track = None
            await self.disconnect()
            # Try to update listeners, but if it fails (e.g., during shutdown), clear them
            try:
                await self._update()
            except Exception as e:
                if "Session is closed" in str(e):
                    self.logger.debug("Session closed during cleanup, clearing listeners")
                    self.clear_update_listeners()
                else:
                    self.logger.warning(f"Error during final update: {e}")
            

    async def _play_track(self, track: Track) -> None:
        """Internal method to play a single track."""
        if self.client is None or not self.client.is_connected():
            raise RuntimeError("Voice client is not connected.")
        if self.client.is_playing():
            raise RuntimeError("Voice client is already playing.")

        audio_source = None
        self.current_track = track
        try:
            preferred_audio = await track.get_preferred_audio()
            if preferred_audio is None:
                raise ValueError("No audio available for the track.")

            audio_source = discord.FFmpegPCMAudio(preferred_audio.file_path)
            self.logger.info(f"Now playing: {track.title}")
            self.client.play(audio_source)
            
            await self._update()

            # Wait until the track finishes playing
            while self.client.is_playing() or self.state == PlayerState.PAUSED:
                await asyncio.sleep(1)

        except Exception as e:
            print(f"Error playing track {track.title}: {e}")
        finally:
            if audio_source is not None:
                audio_source.cleanup()

    async def start(self) -> None:
        """Start the music player."""
        if self.state != PlayerState.IDLE:
            raise RuntimeError("Player is already running.")
        asyncio.create_task(self._loop())

    # * Basic Playback Control
    async def play(self) -> None:
        """Resume playback."""
        if (
            self.state == PlayerState.PAUSED
            and self.client is not None
            and self.client.is_connected()
            and self.client.is_paused()
        ):
            self.client.resume()
            self.state = PlayerState.PLAYING
            
            await self._update()

    async def pause(self) -> None:
        """Pause playback."""
        if (
            self.state == PlayerState.PLAYING
            and self.client is not None
            and self.client.is_connected()
            and not self.client.is_paused()
        ):
            self.client.pause()
            self.state = PlayerState.PAUSED
            
            await self._update()

    async def stop(self, clear: bool = True) -> None:
        """Stop playback and clear the queue."""
        self.state = PlayerState.KILL
        if self.client is not None and self.client.is_connected():
            self.client.stop()
        if clear:
            self.queue.clear()
        self.state = PlayerState.IDLE
        self.current_track = None

    async def skip(self) -> None:
        """Skip the current track."""
        if self.client is not None and self.client.is_connected():
            self.client.stop()
            await self._update()
            
    async def previous(self) -> None:
        """Play the previous track in the queue."""
        if self.queue:
            self.queue.back() # Go back to song currently playing
            self.queue.back() # Go back to previous song
            if self.client is not None and self.client.is_connected():
                self.client.stop()
                await self._update()

    async def _update(self) -> None:
        """Call update listeners."""
        for listener in self.update_listeners:
            try:
                await listener()
            except Exception as e:
                # Only log if it's not a session closed error (happens during shutdown)
                if "Session is closed" not in str(e):
                    self.logger.warning(f"Error in update listener: {e}")