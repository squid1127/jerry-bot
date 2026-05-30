"""Provider models for Gemini plugin."""

from dataclasses import dataclass
from typing import Dict, Any

from .enums import ProviderType


@dataclass(frozen=True, slots=True)
class ProviderModel:
    """Dataclass for provider configuration."""

    plugin_name: str
    provider_type: ProviderType
    config_data: Dict[str, Any]
