"""Configuration module for music plugin."""

from squid_core.config_types import ConfigOption, ConfigSchema, ConfigRequired, ConfigSource
from dataclasses import dataclass

@dataclass
class MusicPluginConfig(ConfigSchema):
    """Configuration schema for the music plugin."""
    
    spotify_client_id: str
    spotify_client_secret: str
    concurrent_operations: int = 5
    
    download_retry_attempts: int = 3
    download_retry_delay: float = 10.0
    
    _options = {
        "spotify_client_id": ConfigOption(
            name=["plugins", "music", "spotify_client_id"],
            default=ConfigRequired,
            description="Spotify Client ID for accessing Spotify API.",
            sources=[ConfigSource.ENVIRONMENT, ConfigSource.DEFAULT],
        ),
        "spotify_client_secret": ConfigOption(
            name=["plugins", "music", "spotify_client_secret"],
            default=ConfigRequired,
            description="Spotify Client Secret for accessing Spotify API.",
            sources=[ConfigSource.ENVIRONMENT, ConfigSource.DEFAULT],
        ),
        "concurrent_operations": ConfigOption(
            name=["plugins", "music", "concurrent_operations"],
            default=5,
            description="Number of concurrent operations for downloading music.",
        ),
        "download_retry_attempts": ConfigOption(
            name=["plugins", "music", "download_retry_attempts"],
            default=3,
            description="Number of retry attempts for failed downloads.",
        ),
        "download_retry_delay": ConfigOption(
            name=["plugins", "music", "download_retry_delay"],
            default=10.0,
            description="Delay in seconds between download retry attempts.",
        ),
    }