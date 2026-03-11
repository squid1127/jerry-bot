"""Global configuration model for Gemini plugin."""

from typing import Optional, Dict
from pydantic import BaseModel, Field

from .provider_config import ProviderConfig
from ..core.constants import GLOBAL_PROMPT


class GlobalConfig(BaseModel):
    """Pydantic model for Gemini plugin global configuration."""

    default_provider: str = Field(
        ..., description="The default provider to use for Gemini instances.", examples=["gemini", "custom-ollama"]
    )
    providers: Dict[str, ProviderConfig] = Field(
        ...,
        description="A dictionary of provider configurations, keyed by name.",
    )

    friendly_name: Optional[str] = Field(
        None, description="A user-friendly name for the plugin instance.", examples=["Jerry", "AI Assistant"]
    )

    global_prompt: Optional[str] = Field(
        GLOBAL_PROMPT,
        description="A global prompt to prepend to all conversations, containing guidelines and instructions. Defaults to a playful octopus persona named Jerry if not set.",
    )

    message_send_cooldown: float = Field(
        0.5,
        description="The minimum delay in seconds between streamed message chunks sent by the bot.",
        examples=[0.5, 1.0, 2.0]
    )
