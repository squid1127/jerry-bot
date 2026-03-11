"""Provider and model configuration models for Gemini plugin."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator

from ..models.enums import ProviderType

class ModelConfig(BaseModel):
    """Pydantic model for individual model configuration within a provider."""

    name: str = Field(..., description="The name of the model.")
    overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="Any provider-specific overrides for this model.",
    )

    # Generic Model parameters
    prompt: Optional[str] = Field(
        None, description="An optional prompt template to use with this model."
    )
    temperature: Optional[float] = Field(
        None, description="Sampling temperature for the model (0.0 - 2.0)."
    )
    max_tokens: Optional[int] = Field(
        None, description="Maximum number of tokens to generate in the response."
    )
    top_p: Optional[float] = Field(
        None, description="Nucleus sampling probability for the model (0.0 - 1.0)."
    )
    top_k: Optional[int] = Field(
        None, description="Top-k sampling parameter for the model (integer)."
    )


class ProviderConfig(BaseModel):
    """Pydantic model for provider configuration."""

    type: ProviderType = Field(..., description="The type of the provider.")
    friendly_name: Optional[str] = Field(
        None, description="A user-friendly name for the provider."
    )
    default_model: ModelConfig = Field(
        ..., description="The default model configuration for this provider."
    )

    global_rate_limit: Optional[int] = Field(
        None,
        description="An optional global rate limit for this provider (requests per minute).",
    )
    instance_rate_limit: Optional[int] = Field(
        None,
        description="An optional rate limit for individual chat instances using this provider (requests per minute).",
    )

    endpoint: Optional[str] = Field(
        None,
        description="Optional API endpoint for the provider (if applicable, e.g., for custom or self-hosted providers).",
    )
    api_key: Optional[str] = Field(
        None,
        description="Optional API key or authentication token for the provider (if applicable).",
    )
    
    @model_validator(mode="after") # type: ignore
    def validate_provider_config(cls, config: "ProviderConfig") -> "ProviderConfig": 
        """Custom validation logic for provider configuration."""
        if config.type == ProviderType.GEMINI and not config.api_key:
                raise ValueError("Gemini provider requires an API key.")
        
        elif config.type == ProviderType.OLLAMA and not config.endpoint:
            raise ValueError("Ollama provider requires an API endpoint.")
        
        elif config.type == ProviderType.OPENROUTER and not config.api_key:
            raise ValueError("OpenRouter provider requires an API key.")
        
        return config