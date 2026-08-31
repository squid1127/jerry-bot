"""Repository context object"""

from dataclasses import dataclass

from ..config import GlobalConfig
from .channel import ChannelRepository
from .guild import GuildRepository
from .llm_profile import LLMProfileRepository
from .provider import ProviderRegistry


@dataclass(frozen=True, slots=True)
class Repositories:
    """Context object that holds references to all repositories for easy access throughout the plugin."""

    guild_repo: GuildRepository
    channel_repo: ChannelRepository
    llm_profile_repo: LLMProfileRepository
    provider_registry: ProviderRegistry

    global_config: GlobalConfig
