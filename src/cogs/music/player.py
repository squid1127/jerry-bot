"""Music player for the music cog."""

import asyncio
import discord
from discord.ui import View
from discord.ext import commands
import logging
import os
from enum import Enum, auto

from cogs.music.config import MusicConfig

from .types import Song, Playlist, PlaylistEntry
from .db import MusicDB
from .downloader import Downloader

logger = logging.getLogger("jerry.music.player")


class PlayerState(Enum):
    """Represents the state of the music player."""

    IDLE = "Idle"
    PLAYING = "Playing"
    PAUSED = "Paused"
    STOPPED = "Stopped"
    BUFFERING = "Buffering"
    DEAD = "Dead"


class PlayerLoopState(Enum):
    """Represents the loop state of the music player."""

    STOPPED = auto()
    RUNNING = auto()


class PlaybackAction(Enum):
    """Represents actions that can be performed on playback."""

    SKIP = "Skip ⏭️"
    PAUSE = "Pause ⏸️"
    RESUME = "Resume ▶️"
    STOP = "Stop ⏹️"


class PlayerError(RuntimeError):
    """Base class for player-related errors."""

    pass


class PlayerExsistsError(PlayerError):
    """Raised when a player already exists in a different channel."""

    pass


class PlayerNotFoundError(PlayerError):
    """Raised when a player is not found for a guild."""

    pass

class Emoji(Enum):
    PLAY = "▶️"
    PAUSE = "⏸️"
    PLAYPAUSE = "⏯️"
    SKIP = "⏭️"
    STOP = "⏹️"
    SONG = "🎵"
    PLAYLIST = "📜"
    QUEUE = "🔊"

class MusicPlayer:
    """Handles music playback in voice channels."""

    def __init__(self, db: MusicDB, downloader: Downloader):
        self.db = db
        self.downloader = downloader
        self.players = {}  # Maps guild_id to PlayerInstance

    async def edit_playback_message(
        self,
        interaction: discord.Interaction,
        content: str,
        title="Music Player",
        color=discord.Color.blue(),
    ):
        """Edit the playback message in the interaction."""
        try:
            await interaction.edit_original_response(
                content="",
                embed=discord.Embed(title=title, description=content, color=color),
            )
        except discord.HTTPException as e:
            logger.error(f"Failed to edit playback message: {e}")

    async def play_interactive(
        self,
        interaction: discord.Interaction,
        og_interaction: discord.Interaction,
        playlist: Playlist | None = None,
        song: Song | None = None,
        voice_channel: discord.VoiceChannel | None = None,
    ):
        """Play a song interactively in a voice channel."""
        if not voice_channel:
            await self.edit_playback_message(
                og_interaction,
                title="Music Player | Error",
                content="Voice channel not specified.",
                color=discord.Color.red(),
            )
            return

        if playlist:
            songs = await self.expand_playlist(playlist)
        elif song:
            songs = [song]
        else:
            await self.edit_playback_message(
                og_interaction,
                content="No song or playlist specified.",
                title="Music Player | Error",
                color=discord.Color.red(),
            )
            return

        guild = interaction.guild
        if not guild:
            await self.edit_playback_message(
                og_interaction,
                content="This command can only be used in a server.",
                title="Music Player | Error",
                color=discord.Color.red(),
            )
            return

        try:
            player = await self.get_player(guild, voice_channel, create=True)
        except PlayerExsistsError:
            await self.edit_playback_message(
                og_interaction,
                content="A player is already active in a different channel. (Only one player per server is allowed)",
                title="Music Player | Error",
                color=discord.Color.red(),
            )
            return

        for song in songs:
            await player.add_to_queue(song)

        # Success message
        await asyncio.sleep(1)  # Give some time for the player to start
        if playlist:
            await self.edit_playback_message(
                og_interaction,
                content=f"Added playlist **{playlist.name}** with {len(songs)} songs to the queue in **{voice_channel.mention}**.",
                title="Music Player | Playlist Added",
                color=discord.Color.green(),
            )
        else:
            await self.edit_playback_message(
                og_interaction,
                content=f"Added song **{songs[0].title}** to the queue in **{voice_channel.mention}**.",
                title="Music Player | Song Added",
                color=discord.Color.green(),
            )

    async def expand_playlist(self, playlist: Playlist) -> list[Song]:
        """Expand a playlist into its constituent songs."""
        songs = []
        for entry in playlist.songs:
            if isinstance(entry, Song):
                songs.append(entry)
            elif isinstance(entry, PlaylistEntry):
                song = await self.db.get_song(id=entry.song_id)
                if song:
                    songs.append(song)
        return songs

    async def get_player(
        self, guild: discord.Guild, channel: discord.VoiceChannel, create: bool = False
    ) -> "PlayerInstance":
        """Get or create a PlayerInstance for the guild."""
        if guild.id not in self.players:
            if not create:
                raise PlayerNotFoundError("No player found for this guild.")
            self.players[guild.id] = PlayerInstance(
                guild.id, channel, self.downloader.config
            )
        if self.players[guild.id].channel.id != channel.id:
            if create and self.players[guild.id].state == PlayerState.IDLE:
                # Allow moving the player if it's idle
                self.players[guild.id].channel = channel
            else:
                raise PlayerExsistsError("Player is already active in a different channel.")
        return self.players[guild.id]

    async def remove_player(self, guild: discord.Guild):
        """Remove and kill the player for the guild."""
        if guild.id in self.players:
            player = self.players[guild.id]
            await player.kill_player()
            del self.players[guild.id]


class PlayerInstance:
    """Represents a music player instance for a guild/channel."""

    def __init__(self, guild: discord.Guild, channel: discord.VoiceChannel, config: MusicConfig):
        self.guild = guild
        self.channel = channel
        self.path = config.songs
        self.config = config

        self.voice_client: discord.VoiceClient | None = None
        self.queue = asyncio.Queue()
        self.current_song: Song | None = None
        self.state = PlayerState.IDLE
        self.loop_state = PlayerLoopState.STOPPED
        self.kill = False
        self.status_message: discord.Message | None = None

    async def add_to_queue(self, song: Song):
        """Add a song to the playback queue."""
        await self.queue.put(song)

        if self.loop_state == PlayerLoopState.STOPPED:
            asyncio.create_task(self.loop())
        
        await asyncio.sleep(1.5)  # Give some time for the loop to start
        if len(self.queue._queue) > 0 and len(self.queue._queue) < 6:
            await self.text_channel_controls()  # Update the control message's up next queue

    async def vc_connect(self):
        """Connect to the voice channel."""
        if self.voice_client and self.voice_client.is_connected():
            return
        self.voice_client = await self.channel.connect()

    async def vc_disconnect(self):
        """Disconnect from the voice channel."""
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
            self.voice_client = None

    async def loop(self):
        """Main playback loop."""
        if self.loop_state == PlayerLoopState.RUNNING:
            raise RuntimeError("Playback loop is already running.")
        if self.state == PlayerState.DEAD:
            raise RuntimeError("Cannot start playback loop on a dead player.")

        try:
            self.loop_state = PlayerLoopState.RUNNING
            if self.kill:
                self.loop_state = PlayerLoopState.STOPPED
                return

            await self.vc_connect()
            await asyncio.sleep(1)  # Give some time to connect

            while True:
                self.current_song = await self.queue.get()
                self.state = PlayerState.PLAYING
                await self.play_song(self.current_song)
                if self.queue.empty() or self.kill:
                    logger.info(
                        f"{self.guild}: Queue empty or kill requested, stopping playback."
                    )
                    self.state = PlayerState.IDLE
                    self.current_song = None
                    break

        except Exception as e:
            logger.error(f"{self.guild}: Error in playback loop: {e}")

        finally:
            await self.set_channel_status()
            await self.text_channel_controls()
            await self.vc_disconnect()
            self.state = PlayerState.IDLE

        self.loop_state = PlayerLoopState.STOPPED

    async def play_song(self, song: Song):
        """Play a single song."""
        path = os.path.join(self.path, song.filename)
        logger.info(f"{self.guild}: Now playing {song.title} ({path})")

        # Create an event to signal when playback is done
        playback_future = asyncio.Future()

        def after_playing(error):
            if error:
                logger.error(f"{self.guild}: Error playing {song.title}: {error}")
                if not playback_future.done():
                    playback_future.set_exception(error)
            else:
                logger.info(f"{self.guild}: Finished playing {song.title}")
                # Signal that playback is complete
                if not playback_future.done():
                    playback_future.set_result(True)

        self.voice_client.play(
            discord.FFmpegPCMAudio(
                path,
            ),
            after=after_playing,
        )

        # Wait until the song finishes or we're asked to stop
        await self.set_channel_status()
        await self.text_channel_controls()
        await playback_future

    async def set_channel_status(self):
        """Set the voice channel's user limit and bitrate to match the guild's defaults."""
        try:
            if self.current_song and self.state == PlayerState.PLAYING:
                status = f"🎵  {self.current_song.title} - {self.current_song.artist}"
                if len(status) > 500:
                    status = status[:497] + "..."
                await self.channel.edit(status=status)
            else:
                await self.channel.edit(status=None)
        except discord.Forbidden:
            logger.warning(f"{self.guild}: Missing permissions to edit channel.")
        except discord.HTTPException as e:
            logger.error(f"{self.guild}: Failed to edit channel: {e}")

    async def _set_event(self, event: asyncio.Event):
        """Helper to set an event from a sync context."""
        event.set()

    async def skip(self):
        """Skip the current song."""
        if self.voice_client and (
            self.voice_client.is_playing() or self.voice_client.is_paused()
        ):
            self.voice_client.stop()
        else:
            logger.warning(f"{self.guild}: Skip requested but no song is playing.")

    async def pause(self):
        """Pause playback."""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            self.state = PlayerState.PAUSED

    async def resume(self):
        """Resume playback."""
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            self.state = PlayerState.PLAYING

    async def kill_player(self):
        """Kill the player and stop playback."""
        self.kill = True
        await self.skip()  # This will break the loop if it's running
        await asyncio.sleep(1)  # Give some time for the loop to exit
        if self.loop_state == PlayerLoopState.RUNNING:
            logger.warning("Player loop is still running after kill request.")
            while self.loop_state == PlayerLoopState.RUNNING:
                await asyncio.sleep(0.5)

        await self.vc_disconnect()  # Ensure we disconnect from voice (it should already be disconnected)
        # self.state = PlayerState.DEAD
        self.state = (
            PlayerState.IDLE
        )  # Allow restart of player if needed, switch to DEAD if you want one-time use only
        self.kill = False  # Reset kill flag for potential future use

    def status_embed(self) -> discord.Embed:
        """Generate a status embed for the player."""
        if self.state == PlayerState.DEAD:
            title = "Music Player | Dead"
            color = discord.Color.dark_red()
            embed = discord.Embed(title=title, color=color, description="The player has been killed and is no longer active.")
            return embed
        elif self.state == PlayerState.IDLE:
            title = "Music Player | Idle"
            color = discord.Color.dark_grey()
            embed = discord.Embed(title=title, color=color, description="Join a voice channel and use `/vc-play` to start playing music.")
            return embed
        
        
        embed = discord.Embed(
            title=f"{self.channel.mention} | {self.state.value}",
            color=discord.Color.blue(),
        )
        if self.current_song:
            embed.add_field(
                name=self.current_song.title,
                value=f"By: {self.current_song.artist}\nFrom: {self.current_song.album}",
                inline=False,
            )

        if not self.queue.empty():
            max_display = 5
            queue_list = []
            temp_queue = self.queue._queue.copy()  # Access the internal deque directly
            for idx, song in enumerate(temp_queue):
                if idx >= max_display:
                    queue_list.append(f"...and {self.queue.qsize() - max_display} more")
                    break
                queue_list.append(f"{idx + 1}. {song.title} - {song.artist}")
            embed.add_field(name="Up Next", value="\n".join(queue_list), inline=False)
        return embed

    async def text_channel_controls(self):
        """Experimental: Send playback controls to a delegated text channel."""

        channel_name = self.config.content.control_channel_name
        guild = self.channel.guild
        if not isinstance(guild, discord.Guild):
            logger.error("text_channel_controls called outside of a guild context.")
            return

        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if not channel:
            return  # No designated channel, skip

        # Purge old messages
        if self.status_message is None:
            try:
                await channel.purge(limit=50, check=lambda m: m.author == guild.me)
            except discord.Forbidden:
                logger.warning(
                    f"{guild}: Missing permissions to purge messages in {channel.name}."
                )
                return

        view = PlayerView(None, self) if self.state in (PlayerState.PLAYING, PlayerState.PAUSED) else None
        if self.status_message is None:
            try:
                self.status_message = await channel.send(
                    embed=self.status_embed(),
                    view=view,
                )
            except discord.Forbidden:
                logger.warning(
                    f"{guild}: Missing permissions to send messages in {channel.name}."
                )
                return
        else:
            try:
                await self.status_message.edit(
                    embed=self.status_embed(),
                    view=view,
                )
            except discord.Forbidden:
                logger.warning(
                    f"{guild}: Missing permissions to edit messages in {channel.name}."
                )
                return
            except discord.NotFound:
                # Message was deleted, reset and try again next time
                logger.warning(
                    f"{guild}: Status message was deleted, resetting."
                )
                self.status_message = None
                await self.text_channel_controls()  # Try again to send a new message

class PlayerView(View):
    """A view for controlling playback."""

    def __init__(
        self,
        interaction: discord.Interaction | None,
        player: MusicPlayer,
        timeout: float = 300,
    ):
        super().__init__(timeout=timeout)
        self.interaction = interaction
        self.player = player
        
        # # Test: Add a disabled button with a random label
        # self.add_item(
        #     discord.ui.Button(
        #         label=self.player.current_song.title[:20] if self.player.current_song else "No Song",
        #         style=discord.ButtonStyle.gray,
        #         disabled=True,
        #     )
        # )

    @discord.ui.button(emoji=Emoji.PLAYPAUSE.value, style=discord.ButtonStyle.primary)
    async def play_pause(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Toggle play/pause."""
        if self.player.state not in (
            PlayerState.PLAYING,
            PlayerState.PAUSED,
        ):
            await interaction.response.send_message(
                "Player is not playing or paused.", ephemeral=True
            )
            await self.end_interaction(canceled=True)  # Just end the interaction if not playing or paused
            return

        if self.player.state == PlayerState.PLAYING:
            await self.player.pause()
        else:
            await self.player.resume()
        await interaction.response.edit_message(
            embed=self.player.status_embed(), view=self
        )

    @discord.ui.button(emoji=Emoji.SKIP.value, style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Skip the current song."""
        if self.player.state not in (
            PlayerState.PLAYING,
            PlayerState.PAUSED,
        ):
            await interaction.response.send_message(
                "Player is not playing or paused.", ephemeral=True
            )
            await self.end_interaction(canceled=True)  # Just end the interaction if not playing or paused
            return
        await interaction.response.defer(ephemeral=True)
        await self.player.skip()

        # Only update if we have an interaction context (i.e. not in control channel)
        if self.interaction is not None:
            await self.interaction.edit_original_response(
                embed=self.player.status_embed(), view=self
            )

    @discord.ui.button(emoji=Emoji.STOP.value, style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Stop playback and clear the queue."""
        if self.player.state not in (
            PlayerState.PLAYING,
            PlayerState.PAUSED,
        ):
            await interaction.response.send_message(
                "Player is not playing or paused.", ephemeral=True
            )
            await self.end_interaction(canceled=True)  # Just end the interaction if not playing or paused
            return
        await interaction.response.defer(ephemeral=True)
        await self.player.kill_player()
        await self.end_interaction(canceled=False)

    async def end_interaction(self, canceled: bool = True):
        self.stop()
        try:
            if canceled:
                view = discord.ui.View().add_item(
                    discord.ui.Button(
                        label="Stopped",
                        style=discord.ButtonStyle.gray,
                        disabled=True,
                    )
                )
            else:
                view = None
            if self.interaction is not None:
                await self.interaction.edit_original_response(
                    view=view,
                )
        except discord.HTTPException:
            pass

    async def on_timeout(self):
        await self.end_interaction()