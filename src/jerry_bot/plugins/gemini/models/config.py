"""Config models for squid-core's config system."""

from squid_core.config_types import ConfigOption, ConfigSchema, ConfigRequired
from dataclasses import dataclass
from typing import Optional

from .gemini import GeminiLLMConfig
from ..constants import GEMINI_DEFAULT_PROMPT

@dataclass
class GlobalConfig(ConfigSchema):
    """Configuration schema for the Gemini chatbot plugin."""
    
    api_key: str
    prompt:str
    # More configuration options to be added as needed.
    
    _options = {
        "api_key": ConfigOption(
            name=["plugins", "gemini", "api_key"],
            default=ConfigRequired,
            description="API key for accessing the Gemini chatbot service.",
        ),
        "prompt": ConfigOption(
            name=["plugins", "gemini", "prompt"],
            default=GEMINI_DEFAULT_PROMPT,
            description="Default prompt for the Gemini chatbot.",
        ),
    }
    
@dataclass
class InstanceConfig:
    """Configuration schema for individual Gemini chatbot instances."""
    
    channel_id: int
    global_config: GlobalConfig
    llm_config: GeminiLLMConfig
    
    prompt: Optional[str] = None  # Instance-specific prompt, overrides global if set.
    prompt_extra: Optional[str] = None  # Instance-specific extra prompt information (Appended to global prompt).
    
    def __post_init__(self):
        """Post-initialization to validate instance config values."""
        
        # Validate llm_config
        if not isinstance(self.llm_config, GeminiLLMConfig):
            raise ValueError("llm_config must be an instance of GeminiLLMConfig.")
        if not self.llm_config.chat_mode:
            raise ValueError("Gemini LLM must have chat_mode enabled for chatbot instances.")