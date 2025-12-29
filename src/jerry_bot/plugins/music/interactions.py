"""Discord interactions and UI for the Music Player Plugin."""

from .player import GuildMusicPlayer
from .models.enums import PlaybackState, CommandAction
from .models.db import MusicTrack, MusicPlaylist, MusicPlaylistEntry
import discord

class MusicSearchView(discord.ui.View):
    """View for music search results."""

    def __init__(
        self,
        tracks: list[MusicTrack],
        playlists: list[MusicPlaylist],
        player: GuildMusicPlayer,
        timeout: float = 120.0,
        interaction: discord.Interaction | None = None,
    ):
        super().__init__(timeout=timeout)
        if len(tracks) > 20:
            tracks = tracks[:20]  # Limit to first 20 tracks
        self.tracks = tracks
        if len(playlists) > 10:
            playlists = playlists[:10]  # Limit to first 10 playlists
        self.playlists = playlists
        self.player = player
        self.interaction = interaction
        
        if tracks:
            track_select = MusicSearchTrackSelect(tracks, player)
            self.add_item(track_select)
        if playlists:
            playlist_select = MusicSearchPlaylistSelect(playlists, player)
            self.add_item(playlist_select)
            
    async def on_timeout(self):
        """Disable all items when the view times out."""
        for item in self.children:
            item.disabled = True
        await self.interaction.edit_original_response(view=self)
        
class MusicSearchTrackSelect(discord.ui.Select):
    """Select menu for music tracks."""

    def __init__(self, tracks: list[MusicTrack], player: GuildMusicPlayer):
        options = [
            discord.SelectOption(
                label=track.title,
                description=", ".join(track.artists) if track.artists else "Unknown Artist",
                value=str(track.id),
            )
            for track in tracks
        ]
        super().__init__(placeholder="Tracks...", options=options, max_values=1)
        self.tracks = tracks
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        track_id = int(self.values[0])
        selected_track = next((t for t in self.tracks if t.id == track_id), None)
        if selected_track is None:
            await interaction.response.send_message(
                "Selected track not found.", ephemeral=True
            )
            return

        await self.player.add_track(selected_track)
        await interaction.response.send_message(
            f"Added **{selected_track.title}** to the queue.", ephemeral=True
        )
        
class MusicSearchPlaylistSelect(discord.ui.Select):
    """Select menu for music playlists."""

    def __init__(self, playlists: list[MusicPlaylist], player: GuildMusicPlayer):
        options = [
            discord.SelectOption(
                label=playlist.name,
                description=playlist.description or None,
                value=str(playlist.id),
            )
            for playlist in playlists
        ]
        super().__init__(placeholder="Playlists...", options=options, max_values=1)
        self.playlists = playlists
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        playlist_id = int(self.values[0])
        selected_playlist = next((p for p in self.playlists if p.id == playlist_id), None)
        if selected_playlist is None:
            await interaction.response.send_message(
                "Selected playlist not found.", ephemeral=True
            )
            return

        await self.player.add_playlist(selected_playlist)
        await interaction.response.send_message(
            f"Added playlist **{selected_playlist.name}** to the queue.", ephemeral=True
        )