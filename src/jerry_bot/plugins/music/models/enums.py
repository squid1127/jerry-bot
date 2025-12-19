"""Enums for Music Player Plugin"""

from enum import Enum

class PlaybackState(Enum):
    """Enumeration for playback states."""
    
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    
