"""Model definitions for the Gemini plugin, including model context generation and message models."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.provider_config import LLMProfileConfig

from .message import Message, Participant
from .enums import ModelContextRole
from .function_call import FunctionCall
from .database import LLMProfileRecord


@dataclass(frozen=True, slots=True)
class LLMProfile:
    """Dataclass representing a specific LLM profile, which may include provider-specific overrides and generic model parameters."""

    model_name: str
    provider_name: str
    overrides: Dict[str, Any] = field(default_factory=dict)
    failover_options: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None  # Optional ID field for database records

    # Generic Model parameters
    prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None

    @classmethod
    def from_config(
        cls, config: "LLMProfileConfig", provider_name: str
    ) -> "LLMProfile":
        """Create a LLMProfile instance from a LLMProfileConfig."""
        return cls(
            model_name=config.name,
            provider_name=provider_name,
            overrides=config.overrides,
            prompt=config.prompt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            top_k=config.top_k,
        )

    @classmethod
    def from_record(cls, entry: LLMProfileRecord) -> "LLMProfile":
        """Create a LLMProfile instance from a LLMProfileRecord database record."""
        return cls(
            model_name=entry.model_name,
            provider_name=entry.provider_name,
            failover_options=entry.failover_options,
            overrides=entry.overrides,
            prompt=entry.prompt,
            temperature=entry.temperature,
            max_tokens=entry.max_tokens,
            top_p=entry.top_p,
            top_k=entry.top_k,
            id=entry.id,
        )

    def to_record(self, **kwargs) -> LLMProfileRecord:
        """Convert this LLMProfile instance into a LLMProfileRecord for database storage."""
        return LLMProfileRecord(
            model_name=self.model_name,
            provider_name=self.provider_name,
            overrides=self.overrides,
            prompt=self.prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            top_k=self.top_k,
            **kwargs,
        )


@dataclass(frozen=True, slots=True)
class LLMContext:
    """Dataclass representing the context for a model response."""

    profile: LLMProfile
    prompt: str
    messages: list["LLMContextMessage"]


@dataclass(frozen=True, slots=True)
class LLMContextMessage:
    """Dataclass representing a message in the model context."""

    role: ModelContextRole
    content: str
    attachment: Optional[Any] = None


@dataclass(frozen=True, slots=True)
class LLMResponseStream:
    """Dataclass representing a streamed response from the model.

    This can contain either content or a function call, and an optional start flag to indicate the beginning of a chunk
    """

    content: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    start: bool = False
