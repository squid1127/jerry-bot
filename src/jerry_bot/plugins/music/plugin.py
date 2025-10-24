"""Main Plugin Module for Music Player."""

from squid_core.plugin_base import Plugin, PluginCog
from squid_core.framework import Framework

from typing import Callable
import discord
from discord import app_commands
import asyncio

from .downloader import MusicDownloader
from .config import MusicPluginConfig
from .views import ViewQuery, ViewPBSearch, PlaybackStatusInteraction
from .player import MusicPlayer
from .models import Track, Playlist

# Btw "search" = downloader & "db_search" = actual playback search


class MusicPlayerPlugin(Plugin):
    """Music Player Plugin for Jerry Bot."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.cog = MusicPlayerCog(self)
        self.downloader = MusicDownloader(self)
        self.players: dict[int, MusicPlayer] = {}

        self.config: MusicPluginConfig | None = None

    async def load(self):
        """Load the Music Player Plugin."""
        self.config = await self.fw.config.resolve_config(MusicPluginConfig, self)
        self.logger.info("Starting SpotDL - This may take a moment...")
        asyncio.create_task(self.downloader.initialize_client(self.config))
        await self.fw.bot.add_cog(self.cog)

    async def unload(self):
        """Unload the Music Player Plugin."""
        await self.fw.bot.remove_cog(self.cog.__class__.__name__)
        await self.downloader.quit()

    def downloader_initialized(self) -> bool:
        """Check if the downloader client is initialized."""
        return self.downloader.client is not None

    def get_player(self, guild: discord.Guild) -> MusicPlayer:
        """Get or create a MusicPlayer for the given guild."""
        if guild.id not in self.players:
            self.players[guild.id] = MusicPlayer(guild, self.logger)
        return self.players[guild.id]

    async def auto_play(
        self,
        guild: discord.Guild,
        channel: discord.VoiceChannel | None = None,
        track: Track | None = None,
        playlist: Playlist | None = None,
    ):
        """Automatically play a track or playlist in the guild's voice channel."""
        player = self.get_player(guild)

        try:
            await player.switch_channel(channel or player.channel)
        except NotImplementedError as e:
            self.logger.warning(f"Auto Play.Switch: {e}")

        if player.channel is None:
            raise ValueError("Player voice channel is not set.")
        if track is None and playlist is None:
            raise ValueError("Either track or playlist must be provided for auto play.")
        if track:
            player.queue.add(track)
        elif playlist:
            player.queue.add_many(playlist.tracks)

        try:
            await player.start()
        except RuntimeError as e:
            self.logger.warning(f"Auto Play: {e}")


class MusicPlayerCog(PluginCog):
    """Cog for handling music playback commands."""

    def __init__(self, plugin: MusicPlayerPlugin):
        super().__init__(plugin)
        self.plugin: MusicPlayerPlugin = plugin

    @app_commands.command(
        name="vc-download",
        description="Download a track and play it in your voice channel.",
    )
    @app_commands.describe(
        query="The search query for the track.",
        name="Name for the resulting playlist (optional).",
    )
    @app_commands.guild_install()
    @app_commands.guild_only()
    async def vc_download(
        self,
        interaction: discord.Interaction,
        query: str,
        name: str, # Non-optional cuz of discord quirks
    ):
        """Download a track and play it in the user's voice channel."""
        if not self.plugin.downloader_initialized():
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Music Download - Not Ready",
                    description="The music downloader is still initializing. Please try again later.",
                    color=discord.Color.red(),
                )
            )
            return

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Music Download - Searching",
                description="Processing query...",
                color=discord.Color.blue(),
            )
        )
        try:
            results = await self.plugin.downloader.search(query)
        except Exception as e:
            await self.plugin.fw.cli.notify_exception(
                title="Music Plugin - Download Error",
                exception=e,
                plugin=self.plugin.name,
            )

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Music Download - Error",
                    description="Something went wrong while searching for the track. :(",
                    color=discord.Color.red(),
                )
            )
            return

        view = ViewQuery(self.plugin, results, playlist_name=name)
        await view.init_interaction(interaction)

    @app_commands.command(
        name="vc-stop",
        description="Stop and disconnect music player.",
    )
    @app_commands.guild_install()
    @app_commands.guild_only()
    async def vc_stop(
        self,
        interaction: discord.Interaction,
    ):
        """Stop music playback and disconnect from the voice channel."""
        player = self.plugin.get_player(interaction.guild)
        await player.disconnect()
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Music Playback - Stopped",
                description="The music player has been stopped and disconnected from the voice channel.",
                color=discord.Color.green(),
            )
        )

    @app_commands.command(
        name="vc-play",
        description="Search for music to play.",
    )
    @app_commands.describe(
        query="The search query for the track or playlist.",
    )
    @app_commands.guild_install()
    @app_commands.guild_only()
    async def vc_play(
        self,
        interaction: discord.Interaction,
        query: str,
    ):
        """Search for music to add to the queue."""

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Music Download - Searching",
                description="Processing query...",
                color=discord.Color.blue(),
            )
        )
        try:
            tracks = await self.plugin.downloader.db_search(query)
            playlists = await self.plugin.downloader.db_search_playlists(query)
        except Exception as e:
            await self.plugin.fw.cli.notify_exception(
                title="Music Plugin - Download Error",
                exception=e,
                plugin=self.plugin.name,
            )

            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="Music Download - Error",
                    description="Something went wrong while searching for the track. :(",
                    color=discord.Color.red(),
                )
            )
            return
        if not tracks and not playlists:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="Music Download - No Results",
                    description="No tracks or playlists were found for your query.",
                    color=discord.Color.orange(),
                )
            )
            return
        
        await asyncio.sleep(1)  # Small delay to ensure message order

        view = ViewPBSearch(self.plugin, tracks, playlists)
        await view.init_interaction(interaction)


    @app_commands.command(
        name="vc",
        description="Music playback controls.",
    )
    @app_commands.guild_install()
    @app_commands.guild_only()
    async def vc(
        self,
        interaction: discord.Interaction,
    ):
        """Show the music playback controls."""
        player = self.plugin.get_player(interaction.guild)
        view = PlaybackStatusInteraction(self.plugin, player)
        await view.init_interaction(interaction)