"""Database Models and Types for Music Player Plugin"""

from tortoise import fields
from tortoise.models import Model
from dataclasses import dataclass, field

class MusicTrack(Model):
    """Model representing a music track in the database.
    
    Attributes:
        file_name (str): The name of the music file.
        title (str): The title of the track.
        artists (list): List of artists for the track.
        album (str): The album name (optional).
        sha256 (str): SHA256 hash of the music file to avoid duplicates.
    """
    
    id = fields.IntField(pk=True)
    file_name = fields.CharField(max_length=255)
    title = fields.CharField(max_length=255)
    artists = fields.JSONField()  # List of artists
    album = fields.CharField(max_length=255, null=True)
    sha256 = fields.CharField(max_length=64, unique=True)
    
    class Meta:
        table = "jerry_music_tracks"
        ordering = ["id"]
    
class MusicPlaylist(Model):
    """Model representing a music playlist in the database.
    
    Attributes:
        name (str): The name of the playlist.
        description (str): Description of the playlist (optional).
    """
    
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    
    class Meta:
        table = "jerry_music_playlists"
        ordering = ["id"]
    
class MusicPlaylistEntry(Model):
    """Model representing an entry in a music playlist.
    
    Attributes:
        playlist (ForeignKey): Reference to the MusicPlaylist.
        track (ForeignKey): Reference to the MusicTrack.
        order (int): The order of the track in the playlist.
    """
    
    id = fields.IntField(pk=True)
    playlist = fields.ForeignKeyField("models.MusicPlaylist", related_name="entries")
    track = fields.ForeignKeyField("models.MusicTrack", related_name="playlist_entries")
    order = fields.IntField()

    class Meta:
        table = "jerry_music_playlist_entries"
        ordering = ["order"]
        
class MusicPlaylistACL(Model):
    """Model representing access control for music playlists.
    
    Attributes:
        playlist (ForeignKey): Reference to the MusicPlaylist.
        user_id (int): ID of the user with access.
    """
    
    id = fields.IntField(pk=True)
    playlist = fields.ForeignKeyField("models.MusicPlaylist", related_name="acls")
    user_id = fields.IntField()
    
    class Meta:
        table = "jerry_music_playlist_acls"
        ordering = ["id"]