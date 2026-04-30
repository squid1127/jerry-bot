"""Enums for the Gemini plugin."""

from enum import Enum


class ModelContextRole(Enum):
    """Enum for LLM context roles."""

    USER = "user"
    MODEL = "model"


class MessageSource(Enum):
    """Enum for chat message source."""

    USER = "user"
    MODEL = "model"
    SYSTEM = "system"
    TOOL_CALL = "tool_call"


class MessageDestination(Enum):
    """Enum for chat message destination."""

    MODEL = "model"
    USER = "user"


class ProviderType(Enum):
    """Enum for provider types."""

    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"

class ProviderCapability(Enum):
    """Enum for provider capabilities."""

    TOOL_CALLS = "tool_calls"
    SYSTEM_PROMPT = "system_prompt"
    STREAMING = "streaming"
    MODEL_CHECK = "model_check"
    TOKEN_COUNT = "token_count"