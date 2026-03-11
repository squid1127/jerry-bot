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
    FUNCTION = "function"


class MessageDestination(Enum):
    """Enum for chat message destination."""

    MODEL = "model"
    USER = "user"


class ProviderType(Enum):
    """Enum for provider types."""

    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
