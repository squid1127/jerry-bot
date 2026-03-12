"""Model definitions for the Gemini plugin, including model context generation and message models."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.provider_config import ModelConfig

from .message import Message, Participant
from .enums import ModelContextRole
from .function_call import FunctionCall
from .database import ModelEntry

@dataclass(frozen=True, slots=True)
class Model:
    """Dataclass representing a model configuration within a provider."""

    name: str
    overrides: Dict[str, Any] = field(default_factory=dict)
    
    # Generic Model parameters
    prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    
    @classmethod
    def from_config(cls, config: "ModelConfig") -> "Model":
        """Create a Model instance from a ModelConfig."""
        return cls(
            name=config.name,
            overrides=config.overrides,
            prompt=config.prompt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            top_k=config.top_k,
        )

    @classmethod
    def from_database_entry(cls, entry: ModelEntry) -> "Model":
        """Create a Model instance from a ModelEntry database record."""
        return cls(
            name=entry.model_name,
            overrides=entry.overrides,
            prompt=entry.prompt,
            temperature=entry.temperature,
            max_tokens=entry.max_tokens,
            top_p=entry.top_p,
            top_k=entry.top_k,
        )
        
    def to_database_entry(self, **kwargs) -> ModelEntry:
        """Convert this Model instance into a ModelEntry for database storage."""
        return ModelEntry(
            model_name=self.name,
            overrides=self.overrides,
            prompt=self.prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            top_k=self.top_k,
            **kwargs
        )

@dataclass(frozen=True, slots=True)
class ModelContext:
    """Dataclass representing the context for a model response."""

    model: Model
    prompt: str
    messages: list["ModelContextMessage"]


@dataclass(frozen=True, slots=True)
class ModelContextMessage:
    """Dataclass representing a message in the model context."""

    role: ModelContextRole
    content: str
    attachment: Optional[Any] = None


@dataclass(frozen=True, slots=True)
class ModelResponseStream:
    """Dataclass representing a streamed response from the model.
    
    This can contain either content or a function call, and an optional start flag to indicate the beginning of a chunk"""

    content: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    start: bool = False
