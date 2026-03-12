"""Global configuration model for Gemini plugin."""

from typing import Optional, Dict
from pydantic import BaseModel, Field

from .provider_config import ProviderConfig, ModelConfig
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
    
    ephemeral_mode: EphemeralConfig = Field(
        ...,
        description="Configuration for ephemeral conversations, which are temporary conversations created when the bot is mentioned in approved guilds. This allows you to specify different behavior and settings for ephemeral interactions compared to regular conversations."
    )

class EphemeralConfig(BaseModel):
    """Configuration for ephemeral messages, which are only visible to the user who triggered them."""

    enabled: bool = Field(
        False,
        description="Whether to enable ephemeral mode.",
    )
    timeout_seconds: int = Field(
        300,
        description="The number of seconds of inactivity after which an ephemeral conversation will time out and be deleted. Defaults to 300 seconds (5 minutes).",
        examples=[60, 300, 600]
    )
    model: ModelConfig = Field(
        ...,
        description="The model configuration to use for ephemeral conversations. This allows you to specify a different model or provider for ephemeral interactions compared to regular conversations.",
    )