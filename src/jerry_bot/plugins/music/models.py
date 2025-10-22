"""Tortoise ORM models & other types for the music plugin."""

from tortoise import fields, models
from enum import IntEnum
from dataclasses import dataclass

# Enums
class MusicProvider(IntEnum):
    """Enum for supported music providers."""
    
    YOUTUBE = 1
    SPOTIFY = 2
    CUSTOM = 3
    
class PlaylistType(IntEnum):
    """Enum for types of playlists."""
    
    PLAYLIST = 1
    ALBUM = 2
    ARTIST = 3

# Basic Data Models
class TrackAudio(models.Model):
    """Model representing the audio file of a track."""
    
    id = fields.IntField(pk=True)
    track = fields.ManyToManyField("models.Track", related_name="audio_files")
    audio_id = fields.CharField(max_length=255, null=True)  # Unique ID from the provider, if applicable
    file_path = fields.CharField(max_length=1024)  # Path to the audio file
    file_hash = fields.CharField(max_length=64)  # SHA256 hash of the audio file for integrity checks
    preferred = fields.BooleanField(default=False)  # Whether this audio file is preferred
    
    class Meta:
        table = "jerry_music_track_audios"

class Track(models.Model):
    """A music track."""

    id = fields.IntField(pk=True)
    provider_id = fields.CharField(max_length=255)
    provider = fields.IntEnumField(MusicProvider)
    authors = fields.JSONField()  # List of author names
    title = fields.CharField(max_length=255)
    audio_frozen = fields.BooleanField(default=False)  # Whether the audio files are frozen/overridden
        
    class Meta:
        table = "jerry_music_tracks"
        
    # Extra Methods
    async def get_preferred_audio(self) -> TrackAudio | None:
        """Get the preferred audio file for this track."""
        return await TrackAudio.filter(track=self, preferred=True).first()
        
class Playlist(models.Model):
    """A music playlist, or a collection of tracks."""

    id = fields.IntField(pk=True)
    type = fields.IntEnumField(PlaylistType)
    name = fields.CharField(max_length=255)
    tracks = fields.ManyToManyField("models.Track", related_name="playlists")
    
    class Meta:
        table = "jerry_music_playlists"
        
# Extra Classes
class DownloadStatus(IntEnum):
    """Status of a download operation."""
    
    SUCCESS = 1
    FAILED = 2
    SKIPPED = 3

@dataclass
class DownloadResult:
    """Result of a download operation."""
    
    name: str
    status: DownloadStatus
    reason: str | None = None
    traceback: str | None = None
    track: Track | None = None