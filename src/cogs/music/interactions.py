"""Discord interactions/ui for the music cog."""

import asyncio
import discord
from discord.ext import commands
from discord.ui import View

from .player import MusicPlayer, PlayerState


class SearchView(View):
    """A view for /vc-download search results."""

    def __init__(
        self,
        interaction: discord.Interaction,
        callback: callable = None,
        kwargs: dict = None,
        timeout: float = 300,
    ):
        super().__init__(timeout=timeout)
        self.value = None
        self.interaction = interaction
        self.download = callback
        self.kwargs = kwargs if kwargs else {}

    @discord.ui.button(label="Download", style=discord.ButtonStyle.primary)
    async def download_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Download the selected songs."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message(
                "This is not your interaction.", ephemeral=True
            )
            return
        self.value = True
        self.kwargs["interaction"] = interaction
        await self.download(**self.kwargs)
        await self.end_interaction(canceled=False)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Cancel the import."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message(
                "This is not your interaction.", ephemeral=True
            )
            return
        self.value = False
        await self.end_interaction()

    async def end_interaction(self, canceled: bool = True):
        self.stop()
        try:
            if canceled:
                view = discord.ui.View().add_item(
                    discord.ui.Button(
                        label="Canceled",
                        style=discord.ButtonStyle.gray,
                        disabled=True,
                    )
                )
            else:
                view = None
            await self.interaction.edit_original_response(
                view=view,
            )
        except discord.HTTPException:
            pass

    async def on_timeout(self):
        await self.end_interaction()


class PlaySearchView(View):
    """A view for /vc-play search results."""

    def __init__(
        self,
        interaction: discord.Interaction,
        playlist_callback: callable = None,
        playlist_kwargs: dict = None,
        playlist_results: list = None,
        song_callback: callable = None,
        song_kwargs: dict = None,
        song_results: list = None,
        timeout: float = 300,
    ):
        super().__init__(timeout=timeout)
        self.value = None
        self.interaction = interaction
        self.playlist_callback = playlist_callback
        self.playlist_kwargs = playlist_kwargs if playlist_kwargs else {}
        self.playlist_results = playlist_results if playlist_results else []
        self.song_callback = song_callback
        self.song_kwargs = song_kwargs if song_kwargs else {}
        self.song_results = song_results if song_results else []

        # Add a select for playlists if there are any
        if self.playlist_results:
            self.add_item(self.Playlists(self))
        # Add a select for songs if there are any
        if self.song_results:
            self.add_item(self.Songs(self))

    async def end_interaction(self, canceled: bool = True):
        self.stop()
        try:
            if canceled:
                view = discord.ui.View().add_item(
                    discord.ui.Button(
                        label="Canceled",
                        style=discord.ButtonStyle.gray,
                        disabled=True,
                    )
                )
            else:
                view = None
            await self.interaction.edit_original_response(
                view=view,
            )
        except discord.HTTPException:
            pass

    async def on_timeout(self):
        await self.end_interaction()

    class Playlists(discord.ui.Select):
        """A select for choosing a playlist."""

        def __init__(self, view: "PlaySearchView"):
            options = [
                discord.SelectOption(
                    label=playlist.name,
                    description=f"{len(playlist.songs)} songs",
                    value=str(index),
                )
                for index, playlist in enumerate(view.playlist_results)
            ]
            super().__init__(
                placeholder="Playlists",
                min_values=1,
                max_values=1,
                options=options,
            )
            self.my_view = view  # There's already a view attribute

        async def callback(self, interaction: discord.Interaction):
            """Handle the select."""
            if interaction.user.id != self.my_view.interaction.user.id:
                await interaction.response.send_message(
                    "This is not your interaction.", ephemeral=True
                )
                return
            index = int(self.values[0])
            playlist = self.view.playlist_results[index]
            self.view.playlist_kwargs["playlist"] = playlist
            self.view.playlist_kwargs["interaction"] = interaction
            await self.view.playlist_callback(**self.view.playlist_kwargs)
            await self.view.end_interaction(canceled=False)

    class Songs(discord.ui.Select):
        """A select for choosing a song."""

        def __init__(self, view: "PlaySearchView"):
            options = [
                discord.SelectOption(
                    label=song.title,
                    description=song.artist,
                    value=str(index),
                )
                for index, song in enumerate(view.song_results)
            ]
            super().__init__(
                placeholder="Songs",
                min_values=1,
                max_values=1,
                options=options,
            )
            self.my_view = view

        async def callback(self, interaction: discord.Interaction):
            """Handle the select."""
            if interaction.user.id != self.my_view.interaction.user.id:
                await interaction.response.send_message(
                    "This is not your interaction.", ephemeral=True
                )
                return
            index = int(self.values[0])
            song = self.view.song_results[index]
            self.view.song_kwargs["song"] = song
            self.view.song_kwargs["interaction"] = interaction
            await self.view.end_interaction(canceled=False)
            await self.view.song_callback(**self.view.song_kwargs)
