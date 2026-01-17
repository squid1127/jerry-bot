"""Discord cog for interacting with the Music Player Plugin."""

from squid_core.plugin_base import Plugin, PluginCog

from .interactions import MusicSearchView
from .player import GuildMusicPlayer
from .models.db import MusicTrack, MusicPlaylist, MusicPlaylistEntry, MusicPlaylistACL
from .models.enums import PlaybackState, CommandAction
from .ui import MusicControlView

import discord
from discord import app_commands
import asyncio

MUSIC_CONTROL_TIMEOUT = 300.0  # 5 minutes

class MusicPlayerCog(PluginCog):
    """Cog for Music Player Plugin commands."""

    def __init__(self, plugin: Plugin):
        
        super().__init__(plugin)
        self.music_plugin: Plugin = plugin  # Type hint for clarity
        
    async def member_check(
        self, interaction: discord.Interaction
    ) -> discord.VoiceChannel:
        """Check if the member is in a voice channel and return it."""
        if interaction.guild is None or interaction.user is None:
            return
        if interaction.user.voice is None or interaction.user.voice.channel is None:
            await interaction.followup.send(
                "",
                embed=discord.Embed(
                    description="You must be in a voice channel to use music commands.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        return interaction.user.voice.channel

    async def status_embed(self, player: GuildMusicPlayer) -> discord.Embed:
        """Create a status embed for the music player."""
        if player.state == PlaybackState.STOPPED:
            return discord.Embed(
                title=f"Music Player - Stopped",
                description="Use /music-play to start playback.",
                color=discord.Color.red(),
            )
        elif player.state == PlaybackState.PAUSED:
            title = f"{player.channel.mention} - Paused"
            color = discord.Color.orange()
        elif player.state == PlaybackState.PLAYING:
            title = f"{player.channel.mention} - Playing"
            color = discord.Color.green()
        else:
            title = f"{player.channel.mention} - Unknown State"
            color = discord.Color.greyple()

        description = "[No track playing]\n"
        if player.current_track:
            description = f"**{player.current_track.title}**\n"
            if player.current_track.artists:
                description += f" by {', '.join(player.current_track.artists)}\n"
            if player.current_track.album:
                description += f" from **{player.current_track.album}**\n"

        peek = await player.queue.peek()
        if peek:
            description += f"\n**Up Next:** {peek.title}"
            if peek.artists:
                description += f" - {', '.join(peek.artists)}\n"
            else:
                description += "\n"

        if await player.queue.size() > 1:
            description += f"*{(await player.queue.size()) - 1} more tracks*"
            
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
        )
        return embed

    @app_commands.command(
        name="music",
        description="Manage music playback.",
    )
    @app_commands.describe(
        action="Action to perform on the music player (play/pause, stop, skip)."
    )
    @app_commands.guild_only()
    async def music_command(
        self, interaction: discord.Interaction, action: CommandAction = None
    ):
        """Base command for music management."""
        await interaction.response.defer(ephemeral=False)

        voice_channel = await self.member_check(interaction)
        if voice_channel is None:
            return

        # Get or create the guild music player
        guild_player: GuildMusicPlayer = self.music_plugin.get_player(
            interaction.guild
        )

        if action is not None:
            if action == CommandAction.PlayPause:
                if guild_player.state == PlaybackState.PLAYING:
                    await guild_player.pause()
                elif guild_player.state == PlaybackState.PAUSED:
                    await guild_player.resume()
                    
            elif action == CommandAction.Stop:
                await guild_player.stop()
            elif action == CommandAction.Skip:
                await guild_player.skip()
            await asyncio.sleep(1)  # Give time for state to update

        try:
            view = MusicControlView(player=guild_player, timeout=MUSIC_CONTROL_TIMEOUT, context=interaction)
            await view.render()
        except Exception as e:
            self.music_plugin.logger.error(f"Error creating status embed: {e}")
            embed = discord.Embed(
                title="Music Player - Error",
                description="An error occurred while retrieving the music player status.",
                color=discord.Color.red(),
            )
            await interaction.followup.send(
                content="", embed=embed, ephemeral=True
            )

    @app_commands.command(
        name="music-queue",
        description="Add tracks or playlists to the music queue.",
    )
    @app_commands.describe(
        query="Search query for the track or playlist to play."
    )
    @app_commands.guild_only()
    async def music_play(
        self, interaction: discord.Interaction, query: str
    ):
        """Command to play a track or playlist."""
        await interaction.response.defer(ephemeral=True)
        voice_channel = await self.member_check(interaction)
        if voice_channel is None:
            return

        # Get or create the guild music player
        guild_player: GuildMusicPlayer = self.music_plugin.get_player(
            interaction.guild
        )

        # Search for tracks and playlists
        try:
            tracks = await MusicTrack.filter(title__icontains=query)[:25]
            playlists = await MusicPlaylist.filter(name__icontains=query)[:25]
        except Exception as e:
            self.music_plugin.logger.error(f"Error searching for music: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Music Search Error",
                    description="An error occurred while searching for music.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        if not tracks and not playlists:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="No Results Found",
                    description=f"No tracks or playlists found for query: '{query}'",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        
        try:
            await guild_player.set_channel(voice_channel)
        except RuntimeError:
            pass
        except Exception as e:
            self.music_plugin.logger.error(f"Error setting voice channel: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Voice Channel Error",
                    description="An error occurred while connecting to your voice channel.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        view = MusicSearchView(tracks=tracks, playlists=playlists, player=guild_player, timeout=180, interaction=interaction)

        await interaction.followup.send(
            content="",
            embed=discord.Embed(
                title="Search Results",
                description="Select a track or playlist to add to the queue:",
                color=discord.Color.blue(),
            ),
            view=view,
            ephemeral=True,
        )