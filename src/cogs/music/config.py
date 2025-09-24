"""Simple configuration for the music cog."""

from core import FileBroker
import yaml
import os
from .schema import MusicSchema

YAML_DEFAULTS = """# Configuration for the music cog
spotdl:
    name: "SpotDL"  # Friendly name of spotdl instance
    # Get these from Spotify's Developer Dashboard
    client_id: "your_spotdl_client_id"
    client_secret: "your_spotdl_client_secret"
    
    # Maximum number of songs to download concurrently
    max_concurrent_downloads: 5

# List of guild IDs where the music bot is disabled
guild_blacklist: [] 
# Name of the channel for music control (e.g. "music-control" -> #music-control) per guild
control_channel_name: "jerry-music-control"
"""


class MusicConfig:
    """Configuration for the music cog."""

    def __init__(self, filebroker: FileBroker):
        self.filebroker = filebroker
        
        self.files = self.filebroker.configure_cog(
            "MusicCog",
            config_file=True,
            config_default=YAML_DEFAULTS,
            cache=True,
            cache_clear_on_init=False,
        )
        self.files.init()

        self.songs = os.path.join(self.files.get_cache_dir(), "songs")
        self.imports = os.path.join(self.files.get_cache_dir(), "imports")
        
        self.content = self.load_config()
        
    def load_config(self) -> MusicSchema:
        """Load the configuration from the YAML file."""
        config = self.files.get_config(cache=False)
            
        return MusicSchema(**config)