"""Performs SpotDL downloads and automatic imports of songs."""

import os, aiofiles
import hashlib
import asyncio
import logging
import discord
from traceback import format_exception

import spotdl
from spotipy.exceptions import SpotifyException
from yt_dlp import YoutubeDL

from .config import MusicConfig
from .db import MusicDB
from .types import Song, Playlist, PlaylistEntry, DownloadResult

logger = logging.getLogger("jerry.music.downloader")


class SongExistsError(Exception):
    """Raised when a song already exists in the database."""
    pass


class SpotDLError(Exception):
    """Raised when SpotDL encounters an error."""
    pass


class Downloader:
    """Handles downloading and importing songs using SpotDL."""

    def __init__(self, config: MusicConfig, db: MusicDB):
        self.config = config
        self.db = db

        self.semaphore = asyncio.Semaphore(
            self.config.content.spotdl.max_concurrent_downloads
        )
        self.downloader = spotdl.Spotdl(
            client_id=self.config.content.spotdl.client_id,
            client_secret=self.config.content.spotdl.client_secret,
            headless=True,
            # Removed loop parameter - SpotDL will create its own loop
        )
        self.die = False  # Set to True to stop downloads
        self.tasked = 0

        os.makedirs(self.config.songs, exist_ok=True)
        os.makedirs(self.config.imports, exist_ok=True)

    async def query(self, query: str) -> list[spotdl.Song]:
        """Query SpotDL for a song or playlist."""
        self.tasked += 1
        loop = asyncio.get_event_loop()
        try:
            songs = await loop.run_in_executor(
                None, lambda: self.downloader.search([query])
            )
            return songs
        except SpotifyException as e:
            self.tasked -= 1
            logger.error(f"Spotify API error: {e}")
            raise SpotDLError(f"Spotify API error: {e}")
        except Exception as e:
            self.tasked -= 1
            logger.error(f"Error querying {self.config.content.spotdl.name}: {e}")
            raise SpotDLError(f"Error querying {self.config.content.spotdl.name}: {e}")
        finally:
            self.tasked -= 1

    def songs_embed(
        self, songs: list[spotdl.Song], title: str = "Downloaded Songs"
    ) -> discord.Embed:
        """Create a Discord embed listing the downloaded songs."""
        char_limit = 4000
        description = ""
        for i, song in enumerate(songs, start=1):
            line = f"**{i}.** {song.name} - {', '.join(song.artists)}\n"
            if len(description) + len(line) > char_limit:
                description += f"\n*And {len(songs) - i + 1} more...*"
                break
            description += line
        embed = discord.Embed(
            title=title, description=description, color=discord.Color.blue()
        )
        return embed

    async def close(self):
        """Close the downloader."""
        self.die = True
        if self.tasked == 0:
            return
        logger.info("Waiting for ongoing tasks to finish...")
        timeout = 60
        while self.tasked > 0 and timeout > 0:
            await asyncio.sleep(1)
            timeout -= 1
        if self.tasked > 0:
            logger.error("Timed out waiting for tasks to finish.")
        else:
            logger.info("All tasks finished.")

    async def get_download_urls_ordered(self, songs: list[spotdl.Song], batch_size: int = 5) -> list[str]:
        """
        Get download URLs for songs while preserving order.
        
        This method processes songs in batches to maintain the exact correspondence
        between input songs and output URLs, avoiding the order issues that occur
        with SpotDL's multithreaded get_download_urls method.
        
        Args:
            songs: List of SpotDL Song objects to get URLs for
            batch_size: Number of songs to process concurrently per batch
            
        Returns:
            List of download URLs in the same order as input songs (None for failed songs)
        """
        download_urls = []
        
        async def get_single_url(song):
            try:
                loop = asyncio.get_event_loop()
                urls = await loop.run_in_executor(
                    None, lambda: self.downloader.get_download_urls([song])
                )
                return urls[0] if urls else None
            except Exception as e:
                logger.error(f"Error getting download URL for {song.name}: {e}")
                return None
        
        # Process songs in batches to balance performance and reliability
        for i in range(0, len(songs), batch_size):
            batch = songs[i:i + batch_size]
            batch_tasks = [get_single_url(song) for song in batch]
            batch_urls = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Handle exceptions in batch results
            for j, result in enumerate(batch_urls):
                if isinstance(result, Exception):
                    logger.error(f"Error getting URL for {batch[j].name}: {result}")
                    download_urls.append(None)
                else:
                    download_urls.append(result)
            
            # Give the event loop a chance to process other tasks between batches
            if i + batch_size < len(songs):  # Don't sleep after the last batch
                await asyncio.sleep(0.1)
                    
        return download_urls

    async def download_song(self, song: spotdl.Song, url: str) -> DownloadResult:
        """Download a single song using SpotDL and return the file path."""
        if self.die:
            raise SpotDLError("Downloader is shutting down. Cannot download.")

        safe_id = hashlib.sha256(song.url.encode()).hexdigest()
        path = os.path.join(self.config.imports, f"{safe_id}.mp3")
        path_songs = os.path.join(self.config.songs, f"{safe_id}.mp3")
        
        # Use asyncio.to_thread for file system checks to avoid blocking
        if await asyncio.to_thread(os.path.exists, path_songs):
            logger.info(
                f"Song {song.name} already exists at {path_songs}. Skipping download."
            )
            return DownloadResult(song=song, filepath=path_songs, exists_in_fs=True)

        if await asyncio.to_thread(os.path.exists, path):
            logger.info(
                f"Song {song.name} already exists at {path}. Skipping download."
            )
            return DownloadResult(song=song, filepath=path, exists_in_fs=False)

        def download():
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(self.config.imports, f"{safe_id}.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if not filename.endswith(".mp3"):
                    filename = os.path.splitext(filename)[0] + ".mp3"
                return filename

        async with self.semaphore:
            try:
                filepath = await asyncio.to_thread(download)
                return DownloadResult(song=song, filepath=filepath)
            except Exception as e:
                logger.error(f"Error downloading song {song.name}: {e}")
                raise SpotDLError(f"Error downloading song {song.name}: {e}")
            
    async def file_to_sha256(self, filepath: str) -> str:
        """Compute the SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        async with aiofiles.open(filepath, "rb") as f:
            while True:
                byte_block = await f.read(4096)
                if not byte_block:
                    break
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    async def import_song(self, result: DownloadResult) -> Song:
        """Import a downloaded song into the database."""
        song = result.song
        filepath = result.filepath
        async with self.semaphore:
            if filepath is None:
                raise ValueError("Filepath cannot be None when importing a song.")
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"File {filepath} does not exist.")

            # Compute SHA256 hash
            sha256 = await self.file_to_sha256(filepath)

            # Check if song already exists in DB
            existing = await self.db.get_song(sha256=sha256)
            if existing:
                existing_path = os.path.join(self.config.songs, existing.filename)
                # Use asyncio.to_thread for file system operations
                path_exists = await asyncio.to_thread(os.path.exists, existing_path)
                if path_exists:
                    existing_hash = await self.file_to_sha256(existing_path)
                    if existing_hash != sha256:
                        # File differs, replace it
                        await asyncio.to_thread(os.remove, existing_path)
                        await asyncio.to_thread(os.rename, filepath, existing_path)
                        logger.info(
                            f"Replaced differing song file in songs directory: {existing_path}"
                        )
                else:
                    # File missing or different, move the new file to songs directory
                    await asyncio.to_thread(os.rename, filepath, existing_path)
                    logger.info(
                        f"Moved missing song file to songs directory: {existing_path}"
                    )
                return existing
            else:
                if not result.exists_in_fs:
                    # Move file to songs directory
                    safe_id = hashlib.sha256(song.url.encode()).hexdigest()
                    new_filename = f"{safe_id}.mp3"
                    new_filepath = os.path.join(self.config.songs, new_filename)
                    await asyncio.to_thread(os.rename, filepath, new_filepath)
                else:
                    new_filename = os.path.basename(filepath)

            # Create Song object
            song_obj = Song(
                title=song.name,
                artist=", ".join(song.artists),
                album=song.album_name or "Unknown Album",
                duration=float(song.duration),
                filename=new_filename,
                sha256=sha256,
            )

            # Insert into DB
            await self.db.add_song(song_obj, overwrite=True)
            logger.info(f"Imported song {song.name} into database.")
            return song_obj

    async def import_playlist(
        self,
        name: str,
        guild_id: str,
        user_id: str,
        songs: list[Song],
        overwrite: bool = False,
    ) -> Playlist:
        """Create and import a playlist into the database."""
        async with self.semaphore:
            entries = [
                PlaylistEntry(song_id=song.id, order=i) for i, song in enumerate(songs)
            ]
            playlist = Playlist(
                name=name,
                guild_id=guild_id,
                user_id=user_id,
                songs=entries,
            )

            await self.db.add_playlist(playlist, overwrite=overwrite)
            logger.info(f"Imported playlist '{name}' into database.")
            return playlist
        
    async def _safe_update_message(self, interaction: discord.Interaction, action:str, desc:str, color=discord.Color.blue()):
        """Helper to safely update a Discord message, catching exceptions."""
        try:
            await interaction.edit_original_response(
                content="",
                embed=discord.Embed(
                    title=f"{self.config.content.spotdl.name} | {action}",
                    description=desc,
                    color=color,
                ),
                view=None,
            )
        except discord.HTTPException as e:
            try:
                await interaction.channel.send(
                    content="",
                    embed=discord.Embed(
                        title=f"{self.config.content.spotdl.name} | {action}",
                        description=desc,
                        color=color,
                    ),
                )
            except discord.HTTPException as e:
                logger.error(f"Failed to update Discord message during download: {e}")
            
    async def _safe_followup(self, interaction: discord.Interaction, action:str, desc:str, color=discord.Color.blue()):
        """Helper to safely send a Discord follow-up message, catching exceptions."""
        try:
            await interaction.followup.send(
                content="",
                embed=discord.Embed(
                    title=f"{self.config.content.spotdl.name} | {action}",
                    description=desc,
                    color=color,
                ),
            )
        except discord.HTTPException as e:
            try:
                await interaction.channel.send(
                    content="",
                    embed=discord.Embed(
                        title=f"{self.config.content.spotdl.name} | {action}",
                        description=desc,
                        color=color,
                    ),
                )
            except discord.HTTPException as e:
                logger.error(f"Failed to send Discord follow-up message during download: {e}")

    async def interactive_download(
        self,
        interaction: discord.Interaction,
        og_interaction: discord.Interaction,
        name: str,
        songs: list[spotdl.Song],
        timeout: float = 300,
    ):
        """Download songs interactively, sending updates to the user."""
        if self.die:
            await self._safe_followup(
                interaction,
                "Error",
                "Downloader is shutting down. Cannot download.",
                color=discord.Color.red(),
            )
            return
        await self._safe_update_message(
            og_interaction,
            "Starting Download...",
            f"Preparing to download {len(songs)} songs.",
        )

        # Get Download URLs while preserving order
        try:
            download_urls = await self.get_download_urls_ordered(songs, batch_size=self.config.content.spotdl.max_concurrent_downloads)
        except Exception as e:
            error_msg = "".join(format_exception(type(e), e, e.__traceback__))
            logger.error(f"Error getting download URLs: {error_msg}")
            await self._safe_update_message(
                og_interaction,
                "Error",
                f"Error getting download URLs: {e} (Tip: Make sure your query is publicly accessible)",
                color=discord.Color.red(),
            )
            return

        if not download_urls or all(url is None for url in download_urls):
            await self._safe_update_message(
                og_interaction,
                "Error",
                "No valid download URLs found.",
                color=discord.Color.red(),
            )
            return

        # Download Songs
        await self._safe_update_message(
            og_interaction,
            "Downloading songs...",
            "This may take a while depending on the number of songs.",
        )

        # Create list of valid song-url pairs
        valid_pairs = [(song, url) for song, url in zip(songs, download_urls) if url is not None]
        
        for song, url in valid_pairs:
            logger.info(f"Downloading {song.name} from {url}")

        tasks = [
            asyncio.create_task(self.download_song(song, url))
            for song, url in valid_pairs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful_downloads = []
        failed_downloads = []

        for (song, url), result in zip(valid_pairs, results):
            if isinstance(result, DownloadResult):
                successful_downloads.append(result)
            else:
                failed_downloads.append(song)
                if len(failed_downloads) > 5:  # Limit error messages to first 5
                    continue
                await self._safe_followup(
                    og_interaction,
                    "Download Error",
                    f"Failed to download {song.name}: {result}",
                    color=discord.Color.red(),
                )
        
        if len(failed_downloads) > 5:
            await self._safe_followup(
                og_interaction,
                "Download Error",
                f"Failed to download {len(failed_downloads)} songs in total.",
                color=discord.Color.red(),
            )

        if not successful_downloads:
            return

        # Import Songs to DB
        await self._safe_update_message(
            og_interaction,
            "Importing songs...",
            "Almost done...",
        )
        await asyncio.sleep(1)  # Give Discord a moment to update the message

        # Import songs in smaller batches to avoid overwhelming the event loop
        import_results = []
        import_batch_size = 3  # Smaller batches for imports since they involve file I/O
        
        for i in range(0, len(successful_downloads), import_batch_size):
            batch = successful_downloads[i:i + import_batch_size]
            import_tasks = [
                asyncio.create_task(self.import_song(result)) 
                for result in batch
            ]
            batch_results = await asyncio.gather(*import_tasks, return_exceptions=True)
            import_results.extend(batch_results)
            
            # Give the event loop breathing room between import batches
            if i + import_batch_size < len(successful_downloads):
                await asyncio.sleep(0.1)

        failed_imports = []
        for download_result, import_result in zip(successful_downloads, import_results):
            if isinstance(import_result, Song):
                continue  # Successfully imported
            elif isinstance(import_result, SongExistsError):
                # Song already exists, this is not a failure
                continue
            else:
                failed_imports.append(download_result.song)
                if len(failed_imports) > 5:  # Limit error messages to first 5
                    continue
                await self._safe_followup(
                    og_interaction,
                    "Import Error",
                    f"Failed to import {download_result.song.name}: {import_result}",
                    color=discord.Color.red(),
                )
        if len(failed_imports) > 5:
            await self._safe_followup(
                og_interaction,
                "Import Error",
                f"Failed to import {len(failed_imports)} songs in total.",
                color=discord.Color.red(),
            )

        # Create Playlist
        try:
            await self.import_playlist(
                name=name,
                guild_id=str(og_interaction.guild_id),
                user_id=str(og_interaction.user.id),
                songs=[res for res in import_results if isinstance(res, Song)],
                overwrite=True,
            )
        except Exception as e:
            await self._safe_followup(
                og_interaction,
                "Playlist Error",
                f"Failed to create playlist '{name}': {e}\n```\n{'\n'.join(format_exception(e))}\n```",
                color=discord.Color.red(),
            )
            return

        # Success
        await self._safe_update_message(
            og_interaction,
            "Download Complete",
            f"Successfully downloaded {len(successful_downloads)} song{'' if len(successful_downloads) == 1 else 's'} Saved under '{name}'.",
            color=discord.Color.green(),
        )
        try:
            await og_interaction.followup.send(
                content=f"{og_interaction.user.mention}✅",
            )
        except discord.HTTPException:
            try:
                await og_interaction.channel.send(
                    content=f"{og_interaction.user.mention}✅\n(Download of '{name}' complete.)",
                )
            except discord.HTTPException:
                pass