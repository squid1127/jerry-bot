"""Model definitions for the Gemini plugin, including model context generation and message models."""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.provider_config import ModelConfig

from .message import Message, Participant
from .enums import ModelContextRole
from .function_call import FunctionCall


@dataclass(frozen=True, slots=True)
class ModelContext:
    """Dataclass representing the context for a model response."""

    model: "ModelConfig"
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
