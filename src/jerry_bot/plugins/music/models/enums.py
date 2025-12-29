"""Enums for Music Player Plugin"""

from enum import Enum

class PlaybackState(Enum):
    """Enumeration for playback states."""
    
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    
class CommandAction(Enum):
    """Enumeration for command actions."""
    
    PlayPause = "play_pause"
    Stop = "stop"
    Skip = "skip"