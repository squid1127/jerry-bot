"""Core functionality for the music cog."""

import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import logging

from core import Bot, PermissionLevel

from .db import MusicDB
from .config import MusicConfig
from .downloader import Downloader, SpotDLError
from .interactions import SearchView, PlaySearchView
from .player import MusicPlayer, PlayerNotFoundError, PlaybackAction, PlayerView, PlayerState

logger = logging.getLogger("jerry.music")


class MusicCog(commands.Cog):
    """A music bot cog using spotdl and discord.py[voice]."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.db = MusicDB(bot.memory)
        self.config = MusicConfig(bot.filebroker)
        self.downloader = Downloader(self.config, self.db)
        self.player = MusicPlayer(self.db, self.downloader)

        self.config.load_config()  # For some reason this isn't async
        self.spot_name = self.config.content.spotdl.name

    async def cog_load(self):
        """Method called when the cog is loaded."""
        await self.db.setup()

        logger.info("MusicCog loaded and database setup complete.")

    async def cog_unload(self):
        """Method called when the cog is unloaded."""
        await self.downloader.close()
        logger.info("MusicCog unloaded and downloader closed.")

    async def command_context(
        self, interaction: discord.Interaction, require_approved: bool = True
    ) -> discord.VoiceChannel | None:
        """Get the voice channel from the interaction context."""
        if require_approved and (
            await self.bot.permissions.interaction_check(
                interaction, PermissionLevel.APPROVED
            )
            is False
        ):
            return None

        if interaction.user.voice is None or interaction.user.voice.channel is None:
            await interaction.response.send_message(
                "You must be in a voice channel to use this command.", ephemeral=True
            )
            return None
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return None

        voice_channel = interaction.user.voice.channel
        return voice_channel

    @app_commands.command(
        name="vc-download", description="Download a Spotify playlist or song."
    )
    @app_commands.describe(
        query="The Spotify URL or search query.",
        name="Name to assign to the song/playlist.",
    )
    async def vc_download(
        self, interaction: discord.Interaction, query: str, name: str
    ):
        """Download a song or playlist from Spotify."""
        if (
            await self.bot.permissions.interaction_check(
                interaction, PermissionLevel.APPROVED
            )
            is False
        ):
            return

        # Search for the song or playlist
        await interaction.response.defer()
        try:
            results = await self.downloader.query(query)
        except SpotDLError as e:
            await interaction.followup.send(f"Error querying {self.spot_name}: {e}")
            return

        if not results:
            await interaction.followup.send("No results found.")
            return

        # Give User summary of results and ask for confirmation
        view = SearchView(
            interaction,
            self.downloader.interactive_download,
            {"name": name, "songs": results, "og_interaction": interaction},
            timeout=300,
        )
        await interaction.followup.send(
            embed=self.downloader.songs_embed(
                results, title=f"{self.spot_name} | Search Results"
            ),
            view=view,
        )

    @app_commands.command(
        name="vc-play",
        description="Play a song or playlist in your current voice channel.",
    )
    @app_commands.describe(query="The name of the song or playlist to play.")
    async def vc_play(self, interaction: discord.Interaction, query: str):
        """Play a song or playlist in the user's current voice channel."""
        voice_channel = await self.command_context(interaction)
        if voice_channel is None:
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        # Search for songs and playlists
        song_results = await self.db.search_songs(query)
        playlist_results = await self.db.search_playlists(
            query, str(interaction.guild_id)
        )

        if not song_results and not playlist_results:
            await interaction.followup.send(
                "",
                embed=discord.Embed(
                    title="No Results Found",
                    description="No songs or playlists found matching your query.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # Show search results and let user choos
        view = PlaySearchView(
            interaction=interaction,
            playlist_callback=self.player.play_interactive,
            playlist_kwargs={
                "voice_channel": voice_channel,
                "og_interaction": interaction,
            },
            playlist_results=playlist_results,
            song_callback=self.player.play_interactive,
            song_kwargs={"voice_channel": voice_channel, "og_interaction": interaction},
            song_results=song_results,
            timeout=300,
        )
        await interaction.followup.send(
            embed=discord.Embed(
                title="Search Results",
                description="Select a song or playlist to play.",
                color=discord.Color.blurple(),
            ),
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="vc", description="Fetch status or control playback.")
    @app_commands.describe(action="The action to perform on playback.")
    async def vc(self, interaction: discord.Interaction, action: PlaybackAction = None):
        """Fetch status or control playback."""
        voice_channel = await self.command_context(interaction, require_approved=False)
        if voice_channel is None:
            return
        guild = interaction.guild

        try:
            player = await self.player.get_player(guild, voice_channel)
        except PlayerNotFoundError:
            await interaction.response.send_message(
                "No active playback in this server. (Join a voice channel and use /vc-play to start playing music)",
                ephemeral=True,
            )
            return

        if action is None:
            # Show status
            embed = player.status_embed()
            if player.state in (PlayerState.PLAYING, PlayerState.PAUSED):
                await interaction.response.send_message(
                    embed=embed, view=PlayerView(interaction, player), ephemeral=True
                )
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Perform action
        if action == PlaybackAction.SKIP:
            await player.skip()
            await interaction.response.send_message("⏭️", ephemeral=True)
        elif action == PlaybackAction.PAUSE:
            await player.pause()
            await interaction.response.send_message("⏸️", ephemeral=True)
        elif action == PlaybackAction.RESUME:
            await player.resume()
            await interaction.response.send_message("▶️", ephemeral=True)
        elif action == PlaybackAction.STOP:
            await player.kill_player()
            await interaction.response.send_message("⏹️", ephemeral=True)
