"""Schema for the music cog."""

from pydantic import BaseModel, Field

SPOTDL_NAME = "SpotDL"

# BSON schema for songs collection
song_name = "jerry.music.songs"
song_schema = {
    "bsonType": "object",
    "required": ["title", "artist", "album", "duration", "filename", "sha256"],
    "properties": {
        "title": {"bsonType": "string", "description": "The title of the song"},
        "artist": {"bsonType": "string", "description": "The artist of the song"},
        "album": {"bsonType": "string", "description": "The album of the song"},
        "duration": {"bsonType": "double", "description": "Duration in seconds"},
        "filename": {
            "bsonType": "string",
            "description": "The filename of the song, located in the music directory",
        },
        "sha256": {"bsonType": "string", "description": "The SHA256 hash of the song"},
        "imported_at": {
            "bsonType": "date",
            "description": "The date the song was imported",
        },
    },
}

# BSON schema for playlists collection
playlist_name = "jerry.music.playlists"
playlist_schema = {
    "bsonType": "object",
    "required": ["name", "songs", "user_id"],
    "properties": {
        "name": {"bsonType": "string", "description": "The name of the playlist"},
        "guild_id": {
            "bsonType": "string",
            "description": "The ID of the guild the playlist belongs to",
        },
        "user_id": {
            "bsonType": "string",
            "description": "The ID of the user who created the playlist",
        },
        "songs": {
            "bsonType": "array",
            "items": {
                "bsonType": "object",
                "properties": {
                    "song_id": {"bsonType": "objectId"},
                    "added_at": {"bsonType": "date"},
                    "order": {"bsonType": "int"},
                },
            },
            "description": "List of songs in the playlist",
        },
    },
}


# Config File Schema
class SpotDLSchema(BaseModel):
    """Configuration for SpotDL."""

    name: str = Field(SPOTDL_NAME, description="Name of the music source")
    client_id: str = Field(..., description="Spotify Client ID")
    client_secret: str = Field(..., description="Spotify Client Secret")
    max_concurrent_downloads: int = Field(5, description="Max concurrent downloads")


class MusicSchema(BaseModel):
    """Main configuration schema for the music cog."""

    spotdl: SpotDLSchema
    guild_blacklist: list[str] = Field(
        default_factory=list, description="List of blacklisted guild IDs"
    )
    control_channel_name: str = Field(
        "music-control", description="Name of the music control channel (e.g. music-control -> #music-control)"
    )
