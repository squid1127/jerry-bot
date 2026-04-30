"""Discord cog for interacting with the Music Player Plugin."""

from squid_core.plugin_base import Plugin, PluginCog

from .interactions import MusicSearchView
from .player import GuildMusicPlayer
from .models.db import MusicTrack, MusicPlaylist
from .models.enums import PlaybackState, CommandAction
from .models.exception import UserFacingInteractionError
from .ui import MusicControlView

import discord
from discord import app_commands
import asyncio
from typing import Protocol

MUSIC_CONTROL_TIMEOUT = 300.0  # 5 minutes


class PlayerManagerProtocol(Protocol):
    """Protocol for the player manager to allow fetching player instances in the cog."""

    def get_player(self, guild: discord.Guild) -> GuildMusicPlayer:
        """Get or create a music player for the specified guild."""
        ...


class MusicPlayerCog(PluginCog):
    """Cog for Music Player Plugin commands."""

    def __init__(self, plugin: Plugin, player_manager: PlayerManagerProtocol) -> None:

        super().__init__(plugin)
        self.player_manager: PlayerManagerProtocol = player_manager

    async def member_check(
        self, interaction: discord.Interaction
    ) -> discord.VoiceChannel | None:
        """Check if the member is in a voice channel and return it."""
        if (
            interaction.guild is None
            or interaction.user is None
            or not isinstance(interaction.user, discord.Member)
        ):
            raise UserFacingInteractionError(
                "Unexpected application context. This command only works in a server."
            )
        if interaction.user.voice is None or interaction.user.voice.channel is None:
            raise UserFacingInteractionError(
                "You must be in a voice channel to use music commands."
            )

        if not isinstance(interaction.user.voice.channel, discord.VoiceChannel):
            raise UserFacingInteractionError(
                "You must be in a voice channel to use music commands."
            )
        return interaction.user.voice.channel

    async def status_embed(self, player: GuildMusicPlayer) -> discord.Embed:
        """Create a status embed for the music player."""
        if player.state == PlaybackState.STOPPED:
            return discord.Embed(
                title="Music Player - Stopped",
                description="Use /music-play to start playback.",
                color=discord.Color.red(),
            )
        elif player.channel is None:
            return discord.Embed(
                title="Music Player - No Channel",
                description="The music player is not connected to a voice channel.",
                color=discord.Color.orange(),
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
        description="[Music] Manage and view playback.",
    )
    @app_commands.describe(
        action="Action to perform on the music player (play/pause, stop, skip)."
    )
    @app_commands.guild_only()
    @app_commands.guild_install()
    async def music_command(
        self, interaction: discord.Interaction, action: CommandAction | None = None
    ):
        """Base command for music management."""
        await interaction.response.defer(ephemeral=False)

        voice_channel = await self.member_check(interaction)
        if voice_channel is None:
            return
        if interaction.guild is None:
            raise UserFacingInteractionError(
                "Unexpected application context. This command only works in a server."
            )

        # Get or create the guild music player
        guild_player: GuildMusicPlayer = self.player_manager.get_player(
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
            view = MusicControlView(
                player=guild_player, timeout=MUSIC_CONTROL_TIMEOUT, context=interaction
            )
            await view.render()
        except Exception as e:
            self.logger.error(f"Error creating status embed: {e}")
            raise UserFacingInteractionError(
                "An error occurred while creating the music player status. Please try again later."
            ) from e

    @music_command.error
    async def music_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for the music_command."""
        await self.handle_command_error(interaction, error)

    @app_commands.command(
        name="music-queue",
        description="[Music] Add tracks or playlists to the queue.",
    )
    @app_commands.describe(query="Search query for the track or playlist to play.")
    @app_commands.guild_only()
    @app_commands.guild_install()
    async def music_play(self, interaction: discord.Interaction, query: str):
        """Command to play a track or playlist."""
        await interaction.response.defer(ephemeral=True)
        voice_channel = await self.member_check(interaction)
        if voice_channel is None:
            return

        if interaction.guild is None:
            raise UserFacingInteractionError(
                "Unexpected application context. This command only works in a server."
            )

        # Get or create the guild music player
        guild_player: GuildMusicPlayer = self.player_manager.get_player(
            interaction.guild
        )

        # Search for tracks and playlists
        tracks = await MusicTrack.filter(title__icontains=query)[:25]
        playlists = await MusicPlaylist.filter(name__icontains=query)[:25]

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

        view = MusicSearchView(
            tracks=tracks,
            playlists=playlists,
            player=guild_player,
            timeout=180,
            interaction=interaction,
        )

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

    @music_play.error
    async def music_play_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for the music_play command."""
        await self.handle_command_error(interaction, error)

    async def handle_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.CommandInvokeError | app_commands.AppCommandError,
    ):
        """Handle errors for music commands and provide user-friendly feedback."""
        original_error = (
            error.original
            if isinstance(error, app_commands.CommandInvokeError)
            else None
        )
        if isinstance(original_error, UserFacingInteractionError):
            embed = discord.Embed(
                description=str(original_error),
                color=discord.Color.red(),
            )
        else:
            self.logger.error(
                f"Unexpected error in music command: {original_error or error}",
                exc_info=original_error or error,
            )
            embed = discord.Embed(
                description="An unexpected error occurred while processing your request. Please try again later.",
                color=discord.Color.red(),
            )

        if interaction.response.is_done():
            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @property
    def logger(self):
        """Convenience property to access the plugin's logger."""
        return self.plugin.logger
