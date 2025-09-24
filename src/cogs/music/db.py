"""MongoDB/redis handling for the music cog."""

import discord
from core import Memory
from motor.motor_asyncio import AsyncIOMotorCollection
import logging

from .schema import song_schema, playlist_schema, song_name, playlist_name
from .types import Song, Playlist, PlaylistEntry

logger = logging.getLogger("jerry.music.db")


class MusicDB:
    """Handles MongoDB operations for the music cog."""

    def __init__(self, db: Memory):
        self.db = db

        self.songs = None
        self.playlists = None

    async def setup(self):
        """Set up the database collections and indexes."""
        if self.db.mongo is None:
            raise RuntimeError("MongoDB is not ready.")

        await self.create_collections()

    async def create_collections(self):
        """Create collections with schema validation."""
        if self.db.mongo_db is None:
            raise RuntimeError("MongoDB database is not selected.")

        collections = await self.db.mongo_db.list_collection_names()

        if song_name not in collections:
            self.songs = await self.db.mongo_db.create_collection(
                song_name,
                validator={"$jsonSchema": song_schema},
            )
            await self.songs.create_index("sha256", unique=True)
            await self.songs.create_index([("title", "text"), ("artist", "text"), ("album", "text")])
            logger.info("Created songs collection with indexes.")
        else:
            self.songs = self.db.mongo_db.get_collection(song_name)

        if playlist_name not in collections:
            self.playlists = await self.db.mongo_db.create_collection(
                playlist_name,
                validator={"$jsonSchema": playlist_schema},
            )
            await self.playlists.create_index(
                [("name", 1), ("guild_id", 1)], unique=True
            )
            await self.playlists.create_index([("name", "text")])
            logger.info("Created playlists collection with indexes.")
        else:
            self.playlists = self.db.mongo_db.get_collection(playlist_name)

        logger.info("MusicDB collections are set up.")

    async def get_playlist(self, name: str, guild_id: str) -> Playlist | None:
        """Get a playlist by name and guild ID."""
        if self.playlists is None:
            raise RuntimeError("Playlists collection is not initialized.")

        data = await self.playlists.find_one({"name": name, "guild_id": guild_id})
        if data:
            entries = [PlaylistEntry(**entry) for entry in data.get("songs", [])]
            return Playlist(
                name=data["name"],
                guild_id=data["guild_id"],
                user_id=data["user_id"],
                songs=entries,
                id=data["_id"],
            )
        return None

    async def get_song(self, sha256: str = None, id=None) -> Song | None:
        """Get a song by SHA256 hash or ID."""
        if self.songs is None:
            raise RuntimeError("Songs collection is not initialized.")

        query = {}
        if sha256:
            query["sha256"] = sha256
        elif id:
            query["_id"] = id
        else:
            raise ValueError("Either sha256 or id must be provided.")

        data = await self.songs.find_one(query)
        if data:
            return Song(
                title=data["title"],
                artist=data["artist"],
                album=data["album"],
                duration=data["duration"],
                filename=data["filename"],
                sha256=data["sha256"],
                imported_at=data["imported_at"],
                id=data["_id"],
            )
        return None

    async def add_song(self, song: Song, overwrite: bool = False) -> Song:
        """
        Add a new song to the database.
        
        Args:
            song (Song): The song to add.
            overwrite (bool): Whether to overwrite an existing song with the same SHA256 hash.
        
        Returns:
            Song: The added song with its database ID.
        Raises:
            ValueError: If a song with the same SHA256 hash already exists and overwrite is False
        """
        if self.songs is None:
            raise RuntimeError("Songs collection is not initialized.")

        if overwrite:
            existing = await self.get_song(sha256=song.sha256)
            if existing:
                logger.info(f"Overwriting existing song {existing.title} in database.")
                await self.songs.delete_one({"_id": existing.id})
        else:
            existing = await self.get_song(sha256=song.sha256)
            if existing:
                raise ValueError(f"Song '{song.title}' already exists in database.")

        song_dict = song.__dict__.copy()
        if "id" in song_dict:
            song_dict.pop("id")
        result = await self.songs.insert_one(song_dict)
        song.id = result.inserted_id
        return song

    async def add_playlist(
        self, playlist: Playlist, overwrite: bool = False
    ) -> Playlist:
        """Add a new playlist to the database."""
        if self.playlists is None:
            raise RuntimeError("Playlists collection is not initialized.")

        # Check if playlist exists
        if not overwrite:
            existing = await self.get_playlist(playlist.name, playlist.guild_id)
            if existing:
                raise ValueError(
                    f"Playlist '{playlist.name}' already exists in this guild."
                )

        else:
            existing = await self.get_playlist(playlist.name, playlist.guild_id)
            if existing:
                await self.playlists.delete_one({"_id": existing.id})

        playlist_dict = playlist.__dict__.copy()
        if "id" in playlist_dict:
            playlist_dict.pop("id")
        if "songs" in playlist_dict:
            playlist_dict["songs"] = [entry.__dict__ for entry in playlist.songs]
        result = await self.playlists.insert_one(playlist_dict)
        playlist.id = result.inserted_id
        return playlist
    
    async def list_playlists(self, guild_id: str) -> list[Playlist]:
        """List all playlists in a guild."""
        if self.playlists is None:
            raise RuntimeError("Playlists collection is not initialized.")
        
        cursor = self.playlists.find({"guild_id": guild_id})
        playlists = []
        async for data in cursor:
            entries = [PlaylistEntry(**entry) for entry in data.get("songs", [])]
            playlists.append(Playlist(
                name=data["name"],
                guild_id=data["guild_id"],
                user_id=data["user_id"],
                songs=entries,
                id=data["_id"],
            ))
        return playlists
    
    async def search_songs(self, query: str, limit: int = 10) -> list[Song]:
        """Search for songs by title or artist."""
        if self.songs is None:
            raise RuntimeError("Songs collection is not initialized.")
        cursor = self.songs.find(
            {"$text": {"$search": query}}
        ).limit(limit)

        results = []
        async for data in cursor:
            results.append(Song(
                title=data["title"],
                artist=data["artist"],
                album=data["album"],
                duration=data["duration"],
                filename=data["filename"],
                sha256=data["sha256"],
                imported_at=data["imported_at"],
                id=data["_id"],
            ))
        return results
    
    async def search_playlists(self, query: str, guild_id: str, limit: int = 10) -> list[Playlist]:
        """Search for playlists by name in a guild."""
        if self.playlists is None:
            raise RuntimeError("Playlists collection is not initialized.")
        cursor = self.playlists.find(
            {"guild_id": guild_id, "$text": {"$search": query}}
        ).limit(limit)

        results = []
        async for data in cursor:
            entries = [PlaylistEntry(**entry) for entry in data.get("songs", [])]
            results.append(Playlist(
                name=data["name"],
                guild_id=data["guild_id"],
                user_id=data["user_id"],
                songs=entries,
                id=data["_id"],
            ))
        return results
    
