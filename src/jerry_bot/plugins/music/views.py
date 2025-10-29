"""Discord UI views for the music plugin."""

from typing import Callable
from squid_core.components.ui import UIView, UIType
from discord import ui, Interaction, ButtonStyle
import discord

import spotdl
import random
import asyncio

from .player import MusicPlayer, PlayerState
from .downloader import MusicDownloader
from .models import Track, DownloadResult, DownloadStatus, Playlist


class ViewQuery(UIView):
    """Main view for querying music tracks."""

    def __init__(
        self, plugin, results: list[spotdl.Song], playlist_name: str | None = None
    ):
        super().__init__(timeout=180.0, ui_type=UIType.INTERACTION)
        self.plugin = plugin
        self.results = results
        self.playlist_name = playlist_name

        embed_description = f"**Found {len(results)} results**:\n"
        self.embed = discord.Embed(
            title="Music Download - Results",
            description=embed_description + self.results_string(results, char_limit=2000), # Plenty of headroom
            color=discord.Color.blue(),
        )
        self.add_button(
            label="Start", style=ButtonStyle.green, callback=self.start_callback
        )

    def results_string(self, results: list[spotdl.Song], char_limit: int = 4000) -> str:
        """Generate a string representation of the search results within a character limit."""
        result_lines = []
        total_length = 0

        for index, song in enumerate(results, start=1):
            line = f"{index}. **{song.name}** - {', '.join(artist for artist in song.artists)}"
            line_length = len(line)

            if total_length + line_length > char_limit:
                break

            result_lines.append(line)
            total_length += line_length

        # Calculate remaining songs
        remaining = len(results) - len(result_lines)
        if remaining > 0:
            result_lines.append(f"*...and {remaining} more.*")

        return "\n".join(result_lines)

    async def start_callback(self, interaction: Interaction):
        """Callback for the Start button."""
        await self.view_transition(
            ViewDownloadProgress(self.plugin, self.results, self.playlist_name)
        )


class ViewDownloadProgress(UIView):
    """View for displaying download progress."""

    def __init__(
        self, plugin, tracks: list[spotdl.Song], playlist_name: str | None = None
    ):
        super().__init__(timeout=None, ui_type=UIType.INTERACTION)
        self.plugin = plugin
        self.tracks = tracks
        self.playlist_name = playlist_name

        self.embed = discord.Embed(
            title="Music Download - In Progress",
            description=f"*Downloading {len(tracks)} track{'' if len(tracks) == 1 else 's'}...*",
            color=discord.Color.blue(),
        )

    def _format_track_list(
        self, results: list[DownloadResult], max_chars: int = 1000
    ) -> str:
        """Format the list of downloaded tracks within a character limit."""
        lines = []
        total_length = 0

        for res in results:
            line = f"- {res.name}"
            line_length = len(line) + 1  # +1 for newline

            if total_length + line_length > max_chars:
                break

            lines.append(line)
            total_length += line_length

        remaining = len(results) - len(lines)
        if remaining > 0:
            lines.append(f"*...and {remaining} more.*")

        return "\n".join(lines)

    async def on_load(self):
        """Start the download process when the view is loaded."""
        description_lines = []

        try:
            results: list[DownloadResult] = await self.plugin.downloader.download_many(
                self.tracks
            )
        except Exception as e:
            await self.plugin.fw.cli.notify_exception(
                title="Music Plugin - Download Error",
                exception=e,
                plugin=self.plugin.name,
            )
            self.embed = discord.Embed(
                title="Music Download - Error",
                description="Something went wrong while downloading the tracks. :(",
                color=discord.Color.red(),
            )
            await self.render()
            return

        try:
            await self.plugin.downloader.create_playlist(
                name=self.playlist_name or f"Playlist {random.randint(100000,999999)}",
                tracks=[
                    res.track
                    for res in results
                    if res.status in (DownloadStatus.SUCCESS, DownloadStatus.SKIPPED)
                ],
            )
        except Exception as e:
            self.plugin.logger.error(f"Error creating playlist: {e}")
            description_lines.append(
                "*However, there was an error creating the playlist.* (Songs will be imported, but not added to a playlist.)\n"
            )
            await self.plugin.fw.cli.notify_exception(
                title="Music Plugin - Playlist Creation Error",
                exception=e,
                plugin=self.plugin.name,
            )
        else:
            description_lines.append(
                f"*Playlist '{self.playlist_name}' created successfully.*\n"
            )

        successful_downloads = [
            res for res in results if res.status == DownloadStatus.SUCCESS
        ]
        skipped_downloads = [
            res for res in results if res.status == DownloadStatus.SKIPPED
        ]
        failed_downloads = [
            res for res in results if res.status == DownloadStatus.FAILED
        ]

        if successful_downloads:
            description_lines.append(
                f"**Successfully downloaded {len(successful_downloads)} track{'' if len(successful_downloads) == 1 else 's'}:**"
            )
            description_lines.append(self._format_track_list(successful_downloads))

        if skipped_downloads:
            description_lines.append(
                f"\n**Skipped {len(skipped_downloads)} track{'' if len(skipped_downloads) == 1 else 's'} (already downloaded):**"
            )
            description_lines.append(self._format_track_list(skipped_downloads))

        if failed_downloads:
            description_lines.append(
                f"\n**Failed to download {len(failed_downloads)} track{'' if len(failed_downloads) == 1 else 's'}:**"
            )
            description_lines.append(self._format_track_list(failed_downloads))

        self.embed = discord.Embed(
            title="Music Download - Completed",
            description="\n".join(description_lines),
            color=(
                discord.Color.green()
                if not failed_downloads
                else discord.Color.orange()
            ),
        )
        await self.render()
        await self.destroy(show_expired=False)


class ViewPBSearch(UIView):
    """View for selecting search results for playback."""

    def __init__(self, plugin, tracks: list[Track], playlists: list[Playlist]):
        super().__init__(timeout=180.0, ui_type=UIType.INTERACTION)
        self.plugin = plugin
        self.tracks = tracks
        self.playlists = playlists

        track_options = self.generate_track_options()
        playlist_options = self.generate_playlist_options()
        if track_options:
            self.view.add_item(
                SimpleSelect(
                    plugin,
                    track_options,
                    self.track_selected,
                    placeholder="Tracks...",
                )
            )
        if playlist_options:
            self.view.add_item(
                SimpleSelect(
                    plugin,
                    playlist_options,
                    self.playlist_selected,
                    placeholder="Playlists...",
                )
            )
        self.set_embed()

    def generate_track_options(self) -> list[discord.SelectOption]:
        """Generate select options for tracks."""
        options = []
        for index, track in enumerate(self.tracks, start=1):
            option = discord.SelectOption(
                label=f"{track.title}",
                value=track.id,
                description=", ".join(artist for artist in track.authors)[:100],
            )
            options.append(option)
        return options

    def generate_playlist_options(self) -> list[discord.SelectOption]:
        """Generate select options for playlists."""
        options = []
        for playlist in self.playlists:
            option = discord.SelectOption(
                label=f"{playlist.name}",
                value=playlist.id,
                description=f"{len(playlist.tracks)} track{'' if len(playlist.tracks) == 1 else 's'}",
            )
            options.append(option)
        return options

    def set_embed(self, message: str | None = "") -> discord.Embed:
        """Generate the embed for the view."""
        self.embed = discord.Embed(
            title="Music Playback - Select",
            description=(
                "Select a track or playlist to play from the dropdown menus below."
                + (f"\n\n**{message}**" if message else "")
            ).strip(),
            color=discord.Color.blue(),
        )
        return self.embed

    async def track_selected(self, interaction: Interaction, track_id: str):
        """Callback for when a track is selected."""
        await interaction.response.defer(thinking=False)
        track = next((t for t in self.tracks if str(t.id) == track_id), None)
        if track is None:
            self.set_embed("Selected track not found.")
            await self.render()
            return
        self.plugin.logger.info(f"Track selected: {track.title}")

        # Get channel user is in
        member = interaction.guild.get_member(interaction.user.id)
        if member is None or member.voice is None or member.voice.channel is None:
            self.set_embed("You must be in a voice channel to play music.")
            await self.render()
            return
        channel = member.voice.channel
        if not isinstance(channel, discord.VoiceChannel):
            self.set_embed("You must be in a voice channel to play music.")
            await self.render()
            return

        try:
            await self.plugin.auto_play(interaction.guild, channel=channel, track=track)
            self.set_embed(f"Added: {track.title}")
            await self.render()
        except Exception as e:
            self.plugin.logger.error(f"Error auto-playing track: {e}")
            self.set_embed("Error occurred while trying to play the selected track.")
            await self.render()
            return

    async def playlist_selected(self, interaction: Interaction, playlist_id: str):
        """Callback for when a playlist is selected."""
        await interaction.response.defer(thinking=False)
        playlist = next((p for p in self.playlists if str(p.id) == playlist_id), None)
        if playlist is None:
            self.set_embed("Selected playlist not found.")
            await self.render()
            return

        # Get channel user is in
        member = interaction.guild.get_member(interaction.user.id)
        if member is None or member.voice is None or member.voice.channel is None:
            self.set_embed("You must be in a voice channel to play music.")
            await self.render()
            return
        channel = member.voice.channel
        if not isinstance(channel, discord.VoiceChannel):
            self.set_embed("You must be in a voice channel to play music.")
            await self.render()
            return

        try:
            await self.plugin.auto_play(
                interaction.guild, channel=channel, playlist=playlist
            )
            self.set_embed(f"Added playlist: {playlist.name}")
            await self.render()
        except Exception as e:
            self.plugin.logger.error(f"Error auto-playing playlist: {e}")
            self.set_embed("Error occurred while trying to play the selected playlist.")
            await self.render()
            return


class SimpleSelect(discord.ui.Select):
    """Select menu for choosing a playlist to play from."""

    def __init__(
        self,
        plugin,
        options: list[discord.SelectOption],
        callback: Callable,
        placeholder: str = "Select a playlist...",
    ):
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
        )
        self.plugin = plugin
        self.callback_func = callback

    async def callback(self, interaction: Interaction):
        """Callback for when a playlist is selected."""
        await self.callback_func(interaction, self.values[0])

class PlaybackStatusInteraction(UIView):
    """View for displaying playback status."""

    def __init__(self, plugin, player: MusicPlayer):
        super().__init__(timeout=None, ui_type=UIType.INTERACTION)
        self.plugin = plugin
        self.player = player
        self.player.add_update_listener(self.refresh)
        self.alive = True
        
        self.add_pb_controls()
        self.set_embed()

    def set_embed(self) -> discord.Embed:
        """Generate the embed for the view."""
        description = "No track is currently playing."
        if self.player.state == PlayerState.PLAYING or self.player.state == PlayerState.PAUSED:
            current_track = self.player.current_track
            if current_track:
                description = f"**{current_track.title}** \n{', '.join(artist for artist in current_track.authors)}"
            else:
                description = "No track is currently playing."
        
        self.embed = discord.Embed(
            title=f"{self.player.state.value}" + (f" - {self.player.channel.mention}" if self.player.channel else ""),
            description=description,
            color=discord.Color.blue(),
        )
        return self.embed
    
    def add_pb_controls(self):
        """Add playback control buttons."""
        if self.player.queue.can_back:
            self.add_button(label="⏮️", style=ButtonStyle.gray, callback=self.previous)
        if self.player.state == PlayerState.PLAYING:
            self.add_button(label="⏸️", style=ButtonStyle.gray, callback=self.pause_resume)
        elif self.player.state == PlayerState.PAUSED:
            self.add_button(label="▶️", style=ButtonStyle.gray, callback=self.pause_resume)
        if self.player.queue.can_skip:
            self.add_button(label="⏭️", style=ButtonStyle.gray, callback=self.skip)
        if self.player.state in (PlayerState.PLAYING, PlayerState.PAUSED):
            self.add_button(label="⏹️", style=ButtonStyle.gray, callback=self.stop)

    async def refresh(self):
        """Refresh the view."""
        if not self.alive:
            return
        self.view.clear_items()
        self.player.remove_update_listener(self.refresh)
        await self.view_transition(PlaybackStatusInteraction(self.plugin, self.player))
        
    async def skip(self, interaction: Interaction):
        """Skip the current track."""
        await self.player.skip()
    async def previous(self, interaction: Interaction):
        """Play the previous track."""
        await self.player.previous()
    async def pause_resume(self, interaction: Interaction):
        """Toggle pause/resume."""
        if self.player.state == PlayerState.PLAYING:
            await self.player.pause()
        elif self.player.state == PlayerState.PAUSED:
            await self.player.play()
    async def stop(self, interaction: Interaction):
        """Stop playback."""
        await self.player.stop(clear=True)