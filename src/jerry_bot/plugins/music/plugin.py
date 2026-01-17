"""Main Plugin Module for Music Player."""

from squid_core.plugin_base import Plugin, PluginCog
from squid_core.framework import Framework
from squid_core.decorators import CLICommandDec, RedisSubscribe
from squid_core.components.cli import CLIContext, EmbedLevel

import discord
from discord import app_commands
import asyncio
from pathlib import Path

import aiofiles

from .imports import ImportManager
from .models.db import MusicTrack, MusicPlaylist, MusicPlaylistEntry
from .player import GuildMusicPlayer
from .cog import MusicPlayerCog

class MusicPlayerPlugin(Plugin):
    """Music Player Plugin for Jerry Bot."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.path: Path = self.get_working_directory()
        self.imports = ImportManager(
            import_directory=self.path / "imports",
            target_directory=self.path / "tracks",
            logger=self.logger,
        )
        self.cog = MusicPlayerCog(self)
        self.players: dict[int, GuildMusicPlayer] = {}

    async def load(self):
        """Load the Music Player Plugin."""
        self.logger.info("Music Player initializing...")
        await self.imports.init_directories()
        await self.framework.bot.add_cog(self.cog)

        self.logger.info("Starting initial import...")
        asyncio.create_task(self.imports.import_all())
        self.logger.info("Music Player initialized.")
        

    async def unload(self):
        """Unload the Music Player Plugin."""
        for guild_id, player in self.players.items():
            await player.stop()
        
        if self.cog is not None:
            await self.framework.bot.remove_cog(self.cog.qualified_name)
            
        self.logger.info("Unloaded Music Player.")


    @CLICommandDec(
        name="music",
        description="Music Player Plugin Commands",
    )
    async def cli(self, ctx: CLIContext):
        """CLI command group for Music Player Plugin."""
        subcommand = ctx.args[0] if ctx.args else None
        if subcommand == "import":
            # Subcommand: Execute import
            try:
                await self.imports.import_all()
            except Exception as e:
                await ctx.respond_exception("Music Import Failed", e)
            else:
                await ctx.respond(
                    title="Music Import",
                    description="Successfully executed music import job.",
                    level=EmbedLevel.SUCCESS,
                )
        elif subcommand == "list":
            # Subcommand: Playlist operations
            playlist = ctx.args[1] if len(ctx.args) > 1 else None
            if playlist:
                operation = ctx.args[2] if len(ctx.args) > 2 else None
                if not operation:
                    # Show playlist details
                    pl = await MusicPlaylist.get_or_none(name=playlist)
                    if pl is None:
                        await ctx.respond(
                            title="Playlist Not Found",
                            description=f"Playlist '{playlist}' does not exist.",
                            level=EmbedLevel.ERROR,
                        )
                        return

                    # Get length of playlist
                    entries = await MusicPlaylistEntry.filter(playlist=pl).order_by("order").prefetch_related("track")
                    
                    # Build description
                    description = f"**Playlist '{pl.name}'** (ID: {pl.id})\n"
                    description += f"Entries: {len(entries)}\n"
                    description += "\nActions: `delete`\n"
                        
                    # Send response
                    await ctx.respond(
                        title=f"Playlist: {pl.name}",
                        description=description,
                        level=EmbedLevel.INFO,
                    )
                elif operation == "delete":
                    # Delete playlist
                    pl = await MusicPlaylist.get_or_none(name=playlist)
                    if pl is None:
                        await ctx.respond(
                            title="Playlist Not Found",
                            description=f"Playlist '{playlist}' does not exist.",
                            level=EmbedLevel.ERROR,
                        )
                        return
                    await MusicPlaylistEntry.filter(playlist=pl).delete()
                    await pl.delete()
                    await ctx.respond(
                        title="Playlist Deleted",
                        description=f"Playlist '{playlist}' has been deleted.",
                        level=EmbedLevel.SUCCESS,
                    )
            else:
                # List all playlists
                playlists = await MusicPlaylist.all()
                description = "\n".join(
                    [f"- {pl.name} (ID: {pl.id})" for pl in playlists]
                ) or "No playlists found."
                await ctx.respond(
                    title="Music Playlists",
                    description=description,
                    level=EmbedLevel.INFO,
                )
        else:
            await ctx.respond(
                title="Music Player Plugin",
                description="Available subcommands: **import**, **list**",
                level=EmbedLevel.INFO,
            )

    def get_player(self, guild: discord.Guild) -> GuildMusicPlayer:
        """Get or create the music player for a guild."""
        if guild.id not in self.players:
            self.players[guild.id] = GuildMusicPlayer(guild, self.logger, self.path / "tracks")
        return self.players[guild.id]