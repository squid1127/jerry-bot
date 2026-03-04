"""Simple queue system for music tracks."""

from .models.db import MusicTrack
from collections import deque
import asyncio
import random

class MusicQueue:
    """A simple async-safe queue for music tracks."""
    def __init__(self):
        self._queue = deque()
        self._lock = asyncio.Lock()  # ensures async-safe access

    async def add(self, track: MusicTrack, position: int = None):
        """
        Add a track to the queue.
        
        Args:
            track (MusicTrack): The track to add.
            position (int, optional): Position to insert the track at. If None, appends to the end.
        """

        async with self._lock:
            if position is None:
                self._queue.append(track)
            else:
                self._queue.insert(position, track)

    async def pop(self) -> MusicTrack | None:
        """
        Pop the next track from the queue.
        
        Returns:
            MusicTrack | None: The next track, or None if the queue is empty.
        """
        
        async with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None

    async def peek(self) -> MusicTrack | None:
        """
        Peek at the next track in the queue without removing it.
        
        Returns:
            MusicTrack | None: The next track, or None if the queue is empty.
        """
        async with self._lock:
            return self._queue[0] if self._queue else None

    async def remove(self, track_id):
        """
        Remove a track from the queue by its ID.
        
        Args:
            track_id: The ID of the track to remove.
        """
        async with self._lock:
            self._queue = deque(t for t in self._queue if t.id != track_id)

    async def clear(self):
        """Clear the entire queue."""
        async with self._lock:
            self._queue.clear()

    async def list(self) -> list[MusicTrack]:
        """Get the queue as a list.
        
        Returns:
            list[MusicTrack]: List of tracks in the queue.
        """
        async with self._lock:
            return list(self._queue)

    async def size(self) -> int:
        """
        Get the current size of the queue.
        
        Returns:
            int: Number of tracks in the queue.
        """
        async with self._lock:
            return len(self._queue)
        
    async def shuffle(self):
        """Shuffle the queue randomly."""
        async with self._lock:
            temp_list = list(self._queue)
            random.shuffle(temp_list)
            self._queue = deque(temp_list)
            
    @property
    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return len(self._queue) == 0