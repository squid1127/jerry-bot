"""Data types for the music cog."""

from dataclasses import dataclass, field
from datetime import datetime
from bson import ObjectId
from spotdl import Song as spotdlSong

@dataclass(frozen=False, order=True)
class Song:
    """A song in the music database."""

    title: str
    artist: str
    album: str
    duration: float  # Duration in seconds
    filename: str  # The filename of the song, located in the music directory
    sha256: str  # The SHA256 hash of the song
    imported_at: datetime = field(default_factory=datetime.now)
    id: ObjectId = None

@dataclass(frozen=True, order=True)
class PlaylistEntry:
    """An entry in a playlist."""

    song_id: ObjectId
    added_at: datetime = field(default_factory=datetime.now)
    order: int = 0

@dataclass(frozen=False, order=True)
class Playlist:
    """A playlist in the music database."""

    name: str
    guild_id: str  # The ID of the guild the playlist belongs to
    user_id: str  # The ID of the user who created the playlist
    songs: list[PlaylistEntry] = field(default_factory=list)
    id: ObjectId = None

    
@dataclass(frozen=True, order=False)
class DownloadResult:
    """Result of a download operation."""
    
    song: spotdlSong
    filepath: str | None = None
    exists_in_fs: bool = False