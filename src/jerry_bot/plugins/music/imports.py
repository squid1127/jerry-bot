"""Track import and cataloging for the music plugin."""

import asyncio
import logging
from pathlib import Path
import aiofiles, hashlib
import aiofiles.os as aios
import mutagen

from .models.db import MusicTrack, MusicPlaylist, MusicPlaylistEntry
from .models.dataclasses import TrackMetadata


class ImportManager:
    """Manages music track imports and cataloging."""

    def __init__(
        self, import_directory: Path, target_directory: Path, logger: logging.Logger
    ):
        """
        Initialize the ImportManager.

        Args:
            import_directory (Path): Directory to import tracks from.
            target_directory (Path): Directory to store imported tracks.
        """
        self.import_directory = import_directory
        self.target_directory = target_directory
        self.logger = logger

    async def try_import(self, file: Path) -> MusicTrack:
        """
        Attempt to import a music track from the given file.

        Args:
            file (Path): The file to import.
        Returns:
            MusicTrack: The imported music track object.
        """

        # Check is file
        if not file.is_file():
            raise FileNotFoundError(f"File not found: {file}")

        # Compute SHA-256 hash
        file_hash = await self.sha256_file(file)

        # Check if track already exists in database
        existing_track = await MusicTrack.get_or_none(sha256=file_hash)
        if existing_track:
            self.logger.info(f"Track already exists in database: {file.name}")
            return existing_track

        # Move file to target directory with hash as filename
        target_path = self.target_directory / f"{file_hash}{file.suffix}"
        if target_path.exists():
            self.logger.info(f"File already exists in target directory: {target_path}")
            await aios.remove(file) # Remove Duplicate
        else:
            await aios.rename(file, target_path)

        # Extract metadata
        metadata = await self.extract_metadata(target_path)

        # Create new MusicTrack entry
        new_track = await MusicTrack.create(
            file_name=target_path.name,
            title=metadata.title,
            artists=metadata.artists,
            album=metadata.album,
            sha256=file_hash,
        )
        return new_track

    async def import_all(self) -> list[MusicTrack]:
        """
        Import all music tracks from the import directory.

        Args:
            playlist (MusicPlaylist | None): Optional playlist to add imported tracks to.
        Returns:
            list[MusicTrack]: List of imported music tracks.
        """
        imported_tracks = []

        self.logger.info(f"Starting import from {self.import_directory}")

        for item in self.import_directory.iterdir():
            if item.is_file():
                try:
                    track = await self.try_import(item)
                    imported_tracks.append(track)
                    
                    if item.is_file():
                        await aios.remove(item) # Remove file after import
                        self.logger.info(f"Imported and removed file: {item}")

                except Exception as e:
                    self.logger.error(f"Failed to import {item}: {e}")

            if item.is_dir():
                # Subdirectory - import as playlist
                title = item.name
                if len(title) > 255:
                    title = title[:255]
                playlist = await MusicPlaylist.get_or_none(name=title)

                if playlist is not None:
                    # Use existing playlist and replace entries
                    self.logger.info(f"Playlist '{title}' exists. Replacing entries.")
                    await MusicPlaylistEntry.filter(playlist=playlist).delete()
                else:
                    playlist = await MusicPlaylist.create(name=title)
                    self.logger.info(f"Created new playlist '{title}'.")

                for sub_item in item.iterdir():
                    if sub_item.is_file():
                        try:
                            track = await self.try_import(sub_item)
                            await MusicPlaylistEntry.create(
                                playlist=playlist,
                                track=track,
                                order=len(imported_tracks),
                            )
                            imported_tracks.append(track)

                            if sub_item.is_file():
                                await aios.remove(sub_item) # Remove file after import
                                self.logger.info(f"Imported and removed file: {sub_item}")

                        except Exception as e:
                            self.logger.error(
                                f"Failed to import {sub_item}: {e}, skipping."
                            )


                # Remove subdirectory after import
                await aios.rmdir(item)

        self.logger.info(
            f"Finished import. Total tracks imported: {len(imported_tracks)}"
        )
        return imported_tracks

    # * Helper Functions
    async def sha256_file(self, file_path: Path, chunk_size: int = 1024 * 1024) -> str:
        """
        Asynchronously compute the SHA-256 hash of a file.
        Args:
            file_path (Path): The path to the file.
            chunk_size (int): The size of each read chunk. Default is 1MB.
        Returns:
            str: The SHA-256 hash of the file in hexadecimal format.
        """

        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        hash_sha256 = hashlib.sha256()
        async with aiofiles.open(file_path, "rb") as f:
            while True:
                data = await f.read(chunk_size)
                if not data:
                    break
                hash_sha256.update(data)
        return hash_sha256.hexdigest()

    async def extract_metadata(self, file_path: Path) -> TrackMetadata:
        """
        Extract metadata from a music file.

        Args:
            file_path (Path): The path to the music file.
        Returns:
            TrackMetadata: The extracted metadata.
        """

        def extract_sync():
            import re
            
            audio = mutagen.File(file_path)
            title = audio.get("TIT2", "Unknown Track")
            artists_raw = audio.get("TPE1", [])
            
            # Extract and split artists by common separators
            artists = []
            if artists_raw:
                for artist_entry in artists_raw:
                    artist_str = str(artist_entry)
                    # Split by common separators: /, ;, &, or " feat. "
                    split_artists = re.split(r'[/;]|\s+&\s+|\s+feat\.\s+|\s+ft\.\s+', artist_str)
                    artists.extend([a.strip() for a in split_artists if a.strip()])
            
            if not artists:
                artists = ["Unknown Artist"]
            
            album = audio.get("TALB", None)
            length_seconds = audio.info.length if audio.info else 0.0
            

            return TrackMetadata(
                title=str(title),
                artists=artists,
                album=str(album),
                length_seconds=length_seconds,
            )

        # Run the blocking extraction in a thread
        loop = asyncio.get_event_loop()
        metadata = await loop.run_in_executor(None, extract_sync)
        return metadata

    async def init_directories(self):
        """Ensure import and target directories exist."""
        if not self.import_directory.exists():
            await aios.mkdir(self.import_directory)
        if not self.target_directory.exists():
            await aios.mkdir(self.target_directory)
