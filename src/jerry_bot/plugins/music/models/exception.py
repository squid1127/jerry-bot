"""Exception classes for the music plugin."""

class MusicPluginError(Exception):
    """Base exception class for music plugin errors."""

class MusicPlayerError(MusicPluginError):
    """Exception raised for errors related to the music player."""

class UserFacingInteractionError(MusicPluginError):
    """Exception raised for errors that should be communicated to the user."""
