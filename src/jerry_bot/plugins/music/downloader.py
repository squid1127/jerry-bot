"""Downloader module for music plugin."""

from logging import Logger
from pathlib import Path
import traceback
from squid_core.plugin_base import PluginComponent, Plugin
from squid_core.framework import Framework

import spotdl
import asyncio  # SpotDL is not async

from .models import (
    Track,
    Playlist,
    MusicProvider,
    PlaylistType,
    TrackAudio,
    DownloadResult,
    DownloadStatus,
)
from .config import MusicPluginConfig

ytdl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "extractor_args": {
        "youtube": {
            "player_js_version": ["actual"],
        }
    },
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ],
}
spotdl_config = spotdl.DownloaderOptions(
    audio_providers=["youtube-music"]  # Force youtube-music
)


def hash_text(text: str) -> str:
    """Generate a simple hash for the given text."""
    import hashlib

    return hashlib.md5(text.encode("utf-8")).hexdigest()


class MusicDownloader(PluginComponent):
    """Component responsible for downloading music tracks."""

    def __init__(self, plugin: Plugin):
        super().__init__(plugin)
        self.plugin = plugin
        self.client: spotdl.Spotdl | None = None
        self.download_semaphore: asyncio.Semaphore | None = None
        self.search_semaphore: asyncio.Semaphore | None = None
        self.path: Path | None = None
        self.config: MusicPluginConfig | None = None

    async def initialize_client(self, config: MusicPluginConfig):
        """Initialize the Spotdl client with Spotify credentials."""
        loop = asyncio.get_event_loop()
        self.config = config
        try:
            self.client = await loop.run_in_executor(
                None,
                lambda: spotdl.Spotdl(
                    client_id=config.spotify_client_id,
                    client_secret=config.spotify_client_secret,
                    headless=True,
                    downloader_settings=spotdl_config,
                ),
            )
        except Exception as e:
            self.plugin.logger.error(f"Failed to initialize Spotdl client: {e}")
            self.client = None
            return
        self.download_semaphore = asyncio.Semaphore(self.config.concurrent_operations)
        self.search_semaphore = asyncio.Semaphore(1)  # Limit query operations to 1

        self.path = self.plugin.get_working_directory() / "music_downloads"
        self.path.mkdir(parents=True, exist_ok=True)
        self.plugin.logger.info("Spotdl client initialized successfully.")

    async def search(self, query: str) -> list[spotdl.Song]:
        """Search for tracks using Spotdl."""
        self.plugin.logger.info(f"Search: Init - Query: {query}")
        if self.client is None:
            raise RuntimeError("Spotdl client not initialized.")

        if self.search_semaphore is None:
            raise RuntimeError("Search semaphore not initialized.")
        async with self.search_semaphore:
            loop = asyncio.get_event_loop()
            # Spotdl's search method is blocking, so run it in executor
            results = await loop.run_in_executor(
                None, lambda: self.client.search([query])
            )
        self.plugin.logger.info(
            f"Search: Completed - Found {len(results)} results for query: {query}"
        )
        return results

    async def _download_with_semaphore(self, query: "SpotTrackQuery") -> DownloadResult:
        """Download a track using the download semaphore."""
        if self.download_semaphore is None:
            raise RuntimeError("Download semaphore not initialized.")

        async with self.download_semaphore:
            result = await query.auto()
            return result

    async def create_playlist(
        self,
        name: str,
        playlist_type: PlaylistType = PlaylistType.PLAYLIST,
        tracks: list[Track] = [],
    ) -> Playlist:
        """Create a playlist with the given tracks."""
        playlist = Playlist(
            name=name,
            type=playlist_type,
        )

        # Check for existing playlist with same name
        existing = await Playlist.get_or_none(name=name)
        if existing:
            # Wipe existing tracks
            await existing.tracks.clear()
            playlist = existing

        await playlist.save()
        if tracks:
            await playlist.tracks.add(*tracks)
        return playlist

    async def download_many(self, tracks: list[spotdl.Song]) -> list[DownloadResult]:
        """Download multiple tracks concurrently."""
        if self.client is None:
            raise RuntimeError("Spotdl client not initialized.")

        if self.download_semaphore is None:
            raise RuntimeError("Download semaphore not initialized.")

        download_tasks = []
        for track in tracks:
            query = SpotTrackQuery(
                spotdl_track=track,
                client=self.client,
                path=self.path,
                logger=self.plugin.logger,
                config=self.config,
            )
            download_tasks.append(self._download_with_semaphore(query))

        results = await asyncio.gather(*download_tasks)
        return results

    async def quit(self):
        """Clean up resources."""
        pass

    async def db_search(self, query: str) -> list[Track]:
        """Search for tracks in the database matching the query."""
        tracks = await Track.filter(title__icontains=query).all()
        return tracks

    async def db_search_playlists(self, query: str) -> list[Playlist]:
        """Search for playlists in the database matching the query."""
        playlists = await Playlist.filter(name__icontains=query).all()
        for playlist in playlists:
            await playlist.fetch_related("tracks")
        return playlists


class SpotTrackQuery:
    """Represents a query for downloading a music track using Spotdl."""

    def __init__(
        self,
        spotdl_track: spotdl.Song,
        client: spotdl.Spotdl,
        path: Path,
        logger: Logger,
        config: MusicPluginConfig,
    ):
        self.spotdl_track = spotdl_track
        self.client = client
        self.path = path
        self.logger = logger
        self.config = config

        self.url: str | None = None
        self.file_path: Path | None = None
        self.track: Track | None = None

    async def get_url(self) -> str | None:
        """Download the track and return the local file URL."""
        loop = asyncio.get_event_loop()
        # Spotdl's download method is blocking, so run it in executor
        # get_download_urls expects and returns a list of URLs - we provide a single-item list
        urls = await loop.run_in_executor(
            None, lambda: self.client.get_download_urls([self.spotdl_track])
        )

        if urls:
            self.url = urls[0]
            return self.url
        return None

    async def check_audio_exists(self, url: str = None) -> TrackAudio | None:
        """Check if the download URL is already in the database."""
        if url is None:
            url = self.url

        # Check for existing audios (multiple) with the same provider URL
        existing_audios = await TrackAudio.filter(audio_id=hash_text(url)).all()

        if len(existing_audios) == 0:
            return None
        elif len(existing_audios) > 1:
            # This should not happen...be safe and erase all and start fresh
            self.logger.warning(
                f"Multiple existing audios found for URL {url}. Cleaning up duplicates."
            )
            for audio in existing_audios:
                await audio.delete()
            return None
        existing = existing_audios[0]

        if existing:
            path = Path(existing.file_path)
            if path.exists():
                self.file_path = path
            else:
                return None
        return existing

    async def yt_download(self, url: str = None) -> Path | None:
        """Download the track using youtube-dl and return the local file path."""
        if url is None:
            url = self.url

        loop = asyncio.get_event_loop()

        file_id = hash_text(url)
        options = ytdl_opts.copy()
        options["outtmpl"] = str(self.path / f"{file_id}.%(ext)s")

        def download():
            import yt_dlp

            with yt_dlp.YoutubeDL(options) as ytdl:
                info = ytdl.extract_info(url, download=True)
                return ytdl.prepare_filename(info)

        file_path = await loop.run_in_executor(None, download)
        self.file_path = (
            self.path / f"{file_id}.mp3"
        )  # Assuming mp3 extension - YTDLP doesn't account for postprocessing
        if not self.file_path.exists():
            return None
        return self.file_path

    async def yt_download_auto(self, url: str = None) -> Path | None:
        """Download the track using youtube-dl with retries and return the local file path."""
        if url is None:
            url = self.url

        attempts = self.config.download_retry_attempts if self.config else 3
        delay = self.config.download_retry_delay if self.config else 10.0

        for attempt in range(1, attempts + 1):
            try:
                file_path = await self.yt_download(url)
                if file_path is not None:
                    return file_path
            except Exception as e:
                self.logger.error(
                    f"Attempt {attempt} to download {self.spotdl_track.name} failed: {e}"
                )
                if attempt < attempts:
                    self.logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)

        return None

    async def _file_hash(self) -> str | None:
        """Async compute the SHA256 hash of the downloaded file."""
        if self.file_path is None:
            return None

        loop = asyncio.get_event_loop()

        def compute_hash() -> str:
            import hashlib

            sha256 = hashlib.sha256()
            with open(self.file_path, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            return sha256.hexdigest()

        file_hash = await loop.run_in_executor(None, compute_hash)
        return file_hash

    async def _audio_to_model(self) -> TrackAudio:
        """(Async) Convert to TrackAudio model."""
        return TrackAudio(
            audio_id=hash_text(self.url),
            file_path=self.file_path,
            file_hash=await self._file_hash(),
            preferred=True,
        )

    def _to_model(self) -> Track:
        """Convert to Track model."""
        return Track(
            provider_id=self.spotdl_track.url,
            provider=MusicProvider.SPOTIFY,
            authors=self.spotdl_track.artists,
            title=self.spotdl_track.name,
        )

    async def save(self) -> None:
        """Save the track information to the database."""
        track = self._to_model()

        # Fetch track based on provider info
        existing = await Track.get_or_none(
            provider_id=track.provider_id,
            provider=track.provider,
        )

        # If exists, use existing; else save new
        if existing:
            track = existing
        else:
            await track.save()

        # Check if audio already exists
        audio = await self._audio_to_model()
        existing_audio = await TrackAudio.get_or_none(
            file_hash=audio.file_hash,
        )

        if existing_audio:
            # Link existing audio to track if not already linked
            if track not in await existing_audio.track.all():
                await existing_audio.track.add(track)
        else:
            # Save new audio and link to track
            await audio.save()
            await audio.track.add(track)

        self.track = track
        return

    async def auto(self) -> DownloadResult:
        """Automatically download and save the track."""
        try:
            self.logger.info(f"Download: {self.spotdl_track.name} - Starting")
            url = await self.get_url()
            if url is None:
                self.logger.error(
                    f"Download: {self.spotdl_track.name} - Failed to get URL"
                )
                return DownloadResult(
                    name=self.spotdl_track.name,
                    status=DownloadStatus.FAILED,
                    reason="Failed to get download URL",
                    traceback="",
                )

            existing_audio = await self.check_audio_exists(url)
            if existing_audio:
                self.logger.info(
                    f"Track already exists in database: {self.spotdl_track.name}"
                )
                # Fetch track from db

                await self.save()
                return DownloadResult(
                    name=self.spotdl_track.name,
                    status=DownloadStatus.SKIPPED,
                    track=self.track,
                )

            self.logger.info(
                f"Download: {self.spotdl_track.name} - Downloading from {url}"
            )
            file_path = await self.yt_download_auto(url)
            if file_path is None:
                self.logger.error(
                    f"Download: {self.spotdl_track.name} - Failed to download"
                )
                return DownloadResult(
                    name=self.spotdl_track.name,
                    status=DownloadStatus.FAILED,
                    reason="Failed to download track. Method returned no file path.",
                    traceback="",
                )
            self.logger.info(
                f"Download: {self.spotdl_track.name} - Downloaded track to {file_path}"
            )

            await self.save()
            self.logger.info(
                f"Download: {self.spotdl_track.name} - Successfully downloaded and saved track"
            )
            return DownloadResult(
                name=self.spotdl_track.name,
                status=DownloadStatus.SUCCESS,
                track=self.track,
            )
        except Exception as e:
            self.logger.error(f"Error downloading track {self.spotdl_track.name}: {e}")

            self.logger.error(
                f"Download: {self.spotdl_track.name} - Exception: {str(e)}"
            )
            return DownloadResult(
                name=self.spotdl_track.name,
                status=DownloadStatus.FAILED,
                reason=str(e),
                traceback=traceback.format_exc(),
            )
