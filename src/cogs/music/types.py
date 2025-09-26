"""Data types for the music cog."""

from dataclasses import dataclass, field
from datetime import datetime
from bson import ObjectId
from spotdl import Song as spotdlSong
from enum import Enum
from typing import Optional

class SpotifyType(Enum):
    """Enum representing the type of a Spotify object."""

    TRACK = "track"
    ALBUM = "album"
    PLAYLIST = "playlist"
    ARTIST = "artist"

@dataclass(frozen=True, order=False)
class SpotifyID:
    """A Spotify ID, e.g. track ID, album ID, etc."""

    id: str
    spot_type: SpotifyType

    def to_url(self) -> str:
        """Convert the Spotify ID to a URL."""
        return f"https://open.spotify.com/{self.spot_type.value}/{self.id}"

def id_from_url(url: str) -> SpotifyID:
    """Extract a Spotify ID from a URL."""
    parts = url.split("/")
    if len(parts) < 5:
        raise ValueError("Invalid Spotify URL")
    spot_type = parts[3]
    spot_id = parts[4].split("?")[0]  # Remove any query parameters
    try:
        spot_type_enum = SpotifyType(spot_type)
    except ValueError:
        raise ValueError("Invalid Spotify type in URL")
    return SpotifyID(id=spot_id, spot_type=spot_type_enum)

class DataSource(Enum):
    """Enum representing the source of a song, etc. object."""

    SPOTDL = "spotdl"  # Sourced from spotdl, using the downloader.to_song method
    DB = "db"  # Sourced from the database
    FS = "fs"  # Sourced from the filesystem, e.g. a file was found in the music directory. This is only used for SongFile objects.
    MANUAL_IMPORT = "manual_import"  # Manually imported by the user


@dataclass(frozen=False, order=True)
class Song:
    """A song in the music database."""
    # Primary key
    spot_id: SpotifyID
    db_id: Optional[ObjectId] = None # MongoDB ObjectId, if stored in the database

    # Metadata
    title: str
    artist: str # String of artist(s). Due to spotdl limitations, this is a string and not a list.
    album: str = field(default_factory=str) # Album name
    duration: int = 0  # Duration in seconds
    artwork_url: Optional[str] = None  # URL to the artwork image
    
    # File
    filename: Optional[str] = None  # The filename of the song, if downloaded, relative to the music/downloads directory
    sha256: Optional[str] = None  # SHA256 hash of the file, assuming it has been downloaded
    
    # Download info
    download_url: Optional[str] = None  # The URL used to download the song
    download_overridden: bool = False  # Whether the download URL was overridden by the user, and should not be updated automatically
    
    # Source
    source: DataSource = DataSource.DB  # The source of the song object
    last_updated: datetime = field(default_factory=datetime.now)  # Last time the song metadata was updated
    
@dataclass(frozen=True, order=True)
class PlaylistEntry:
    """An entry in a playlist."""

    spot_id: SpotifyID  # The unique track ID, e.g. Spotify track ID. Primary key.
    added_at: datetime = field(default_factory=datetime.now)
    order: int = 0

@dataclass(frozen=False, order=True)
class Playlist:
    """A playlist in the music database."""

    spot_id: SpotifyID  # The unique playlist ID, e.g. Spotify playlist ID. Primary key. Can be any spotify type.
    name: str
    description: str = ""
    guild_id: str  # The ID of the guild the playlist belongs to
    user_id: str  # The ID of the user who created the playlist
    songs: list[PlaylistEntry] = field(default_factory=list)
    
@dataclass(frozen=False)
class DownloadResult:
    """Result of a song download operation."""
    
    song: Optional[Song] = None
    success: bool = False
    error: Optional[str] = None
    file_path: Optional[str] = None
    download_time: float = 0.0  # Time taken to download
    source_spotdl_song: Optional[spotdlSong] = None  # Original SpotDL song object