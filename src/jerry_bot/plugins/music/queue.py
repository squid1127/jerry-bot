"""Music player module."""

import asyncio
import random
from enum import IntEnum
from typing import Literal
from .models import Track, Playlist


class MusicQueue:
    """
    Class representing a music queue.
    """
    
    def __init__(self):
        self._queue: list[Track] = []
        self._history: list[Track] = []
        
    def peak_next(self) -> Track | None:
        """Return the next track in the queue without removing it."""
        if self.is_empty():
            return None
        return self._queue[0]
        
    def pop_next(self) -> Track | None:
        """Remove and return the next track in the queue."""
        if self.is_empty():
            return None
        track = self._queue.pop(0)
        self._history.append(track)
        return track
        
    def add(self, track: Track) -> None:
        """Add a track to the end of the queue."""
        self._queue.append(track)
        
    def add_many(self, tracks: list[Track]) -> None:
        """Add multiple tracks to the end of the queue."""
        self._queue.extend(tracks)
        
    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return len(self._queue) == 0
    
    def skip(self) -> None:
        """Skip the current track."""
        if not self.is_empty():
            self.pop_next()
            
    def back(self) -> None:
        """Go back to the previous track."""
        if self._history:
            track = self._history.pop()
            self._queue.insert(0, track)
            
    def clear(self) -> None:
        """Clear the queue."""
        self._queue.clear()
        self._history.clear()
        
    def get_queue(self) -> list[Track]:
        """Get the current queue as a list of tracks."""
        return self._queue.copy()
    
    def get_history(self) -> list[Track]:
        """Get the history of played tracks."""
        return self._history.copy()
    
    @property
    def can_skip(self) -> bool:
        """Check if there is a next track to skip to."""
        return len(self._queue) > 1
    @property
    def can_back(self) -> bool:
        """Check if there is a previous track to go back to."""
        return len(self._history) > 1 # At least two tracks in history to go back (current + previous)
    @property
    def size(self) -> int:
        """Get the size of the queue."""
        return len(self._queue)