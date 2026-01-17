"""Guild-based playback system for Jerry Bot."""

from .models.db import MusicTrack, MusicPlaylist, MusicPlaylistEntry
from .models.enums import PlaybackState
from .queue import MusicQueue
from pathlib import Path
import logging
import discord
import asyncio
import weakref, inspect
class GuildMusicPlayer:
    """Manages music playback for a specific guild."""

    def __init__(self, guild: discord.Guild, logger: logging.Logger, playback_dir: Path):
        self.guild = guild
        self.channel: discord.VoiceChannel | None = None
        self.connection: discord.VoiceClient | None = None
        self.logger = logger
        self.state: PlaybackState = PlaybackState.STOPPED
        
        if not playback_dir.is_dir():
            raise NotADirectoryError(f"Playback directory should exsist and be a directory: {playback_dir}")

        self.playback_dir = playback_dir
        self.queue: MusicQueue = MusicQueue()
        self.operation_lock = asyncio.Lock()
        
        self.player_lock = asyncio.Lock()
        self.player_task: asyncio.Task | None = None
        self._current_track: MusicTrack | None = None
        
        self._listeners: set[weakref.ReferenceType] = set()
        
    async def reset(self):
        """Reset the music player state and queue."""
        async with self.operation_lock:
            self.state = PlaybackState.STOPPED
            # Create a new queue instance to clear existing tracks
            self.queue = MusicQueue()
        
    async def start_player(self):
        """Attempt to start the music player loop. (Ignores if already running)"""

        async with self.player_lock:
            if self.player_task is None or self.player_task.done():
                self.player_task = asyncio.create_task(self._player_loop())
                
    async def _player_loop(self):
        """Main loop for the music player."""
        if self.connection is None:
            if self.channel is None:
                self.logger.error(f"Cannot start player loop: No voice channel set for guild {self.guild.id}")
                return
            self.connection = await self.channel.connect()
        
        self.logger.info(f"Starting music player loop for guild {self.guild.id}")
        self.state = PlaybackState.PLAYING

        
        while True:
            try:
                if self.state == PlaybackState.STOPPED:
                    break  # Exit the loop if stopped
                
                next_track = await self.queue.pop()
                if next_track is None:
                    self.state = PlaybackState.STOPPED
                    break  # No more tracks to play
                
                self.state = PlaybackState.PLAYING
                
                await self._do_track(next_track)
                
            except Exception as e:
                # Handle exceptions and log errors
                self.logger.error(f"Error in music player loop: {e}")
                self.state = PlaybackState.STOPPED
                break
            
        # Cleanup after exiting the loop
        self.logger.info(f"Music player loop ending for guild {self.guild.id}")
        await self.stop()
                    
    async def _do_track(self, track: MusicTrack):
        """Play a single track."""
                
        # Create an event to signal when playback is finished
        finished = asyncio.Event()
        def finished_callback(error):
            if error:
                self.logger.error(f"Error during playback: {error}")
            finished.set()
                    
        # Fetch track file path
        track_path = self.playback_dir / track.file_name
        if not track_path.exists():
            self.logger.error(f"Track file does not exist: {track_path}")
            return
        self._current_track = track
        
        await self.emit_event("track_start")

        # Create audio source and play
        source = discord.FFmpegPCMAudio(
            track_path.as_posix(),
            options="-vn",
            before_options="-nostdin",
        )
        
        self.connection.play(source, after=finished_callback)
        await finished.wait()
        
                
    async def add_track(self, track: MusicTrack | list[MusicTrack]):
        """Add a track to the playback queue."""
        async with self.operation_lock:
            if isinstance(track, list):
                for t in track:
                    await self.queue.add(t)
            else:
                await self.queue.add(track)
            await self.start_player()
            await self.emit_event("add_track")
    
    async def add_playlist(self, playlist: MusicPlaylist):
        """Add all tracks from a playlist to the playback queue."""
        async with self.operation_lock:
            entries = await MusicPlaylistEntry.filter(playlist=playlist).order_by("order").prefetch_related("track")
            for entry in entries:
                await self.queue.add(entry.track)
            await self.start_player()
            await self.emit_event("add_playlist")
                
    async def stop(self):
        """Stop playback and reset the player."""
        async with self.operation_lock:
            self.logger.info(f"Stopping playback in guild {self.guild.id}")
            self.state = PlaybackState.STOPPED
            if self.player_task:
                self.player_task.cancel()
                self.player_task = None
            if self.connection is not None:
                await self.connection.disconnect()
            self.connection = None
            await self.reset()
            await self.emit_event("stop")
            
    async def set_channel(self, channel: discord.VoiceChannel):
        """Set the voice channel for playback. Does not connect to it."""
        async with self.operation_lock:
            if self.connection is not None:
                raise RuntimeError("Voice channel is already set and connected.")
            self.channel = channel
            
    async def pause(self):
        """Pause playback."""
        async with self.operation_lock:
            if self.connection and self.connection.is_playing():
                self.connection.pause()
                self.state = PlaybackState.PAUSED
            await self.emit_event("pause")
                
    async def resume(self):
        """Resume playback."""
        async with self.operation_lock:
            if self.connection and self.connection.is_paused():
                self.connection.resume()
                self.state = PlaybackState.PLAYING
            await self.emit_event("resume")
                
    async def skip(self):
        """Skip the current track."""
        async with self.operation_lock:
            if self.connection and self.connection.is_playing():
                self.connection.stop()
            await self.emit_event("skip")
                
    @property
    def current_track(self) -> MusicTrack | None:
        """Get the currently playing track if any."""
        if self.connection is None:
            return None
        if self.connection.is_playing() or self.connection.is_paused():
            return self._current_track
        return None
    
    # "Simple" event system to allow subscribing to player events

    def subscribe(self, callback):
        """
        Subscribe a listener callback to player events.
        
        The callback should be a callable that takes a single argument: the event name. It can be either:
        - a function
        - a bound method
        """
        if inspect.ismethod(callback):
            ref = weakref.WeakMethod(callback)
        else:
            ref = weakref.ref(callback)

        self._listeners.add(ref)
        
    async def emit_event(self, event_name: str):
        """Emit an event to all subscribed listeners."""
        to_remove = set()
        for ref in self._listeners:
            callback = ref()
            if callback is None:
                to_remove.add(ref)
                continue
            try:
                if inspect.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event_name))
                else:
                    callback(event_name)
            except Exception as e:
                self.logger.error(f"Error in listener callback: {e}")
        self._listeners.difference_update(to_remove)
        