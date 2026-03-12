"""Data models for the Gemini plugin."""

from .enums import MessageSource, MessageDestination, ProviderType, ModelContextRole
from .message import (
    Participant,
    BaseMessage,
    UserMessage,
    ModelMessage,
    SystemMessage,
    ExceptionMessage,
    Message,
)
from .database import Channel, Guild, ModelEntry
from .function_call import FunctionCall
from .provider import ProviderModel
from .model import Model, ModelContext, ModelContextMessage, ModelResponseStream
from .context import ChannelContext
from .exceptions import (
    GeminiError,
    FatalError,
    ConfigurationError,
    ChannelError,
    ChannelNotRegisteredError,
    ChannelAlreadyRegisteredError,
    ConversationError,
    MessageProcessingError,
    ProviderError,
    ProviderGenerateError,
    ProviderRateLimitError,
    ProviderAPIError,
    ProviderAPIRateLimitError,
    ProviderTimeoutError,
    FunctionCallError,
    ContextGenerationError,
)

__all__ = [
    # Enums
    "MessageSource",
    "MessageDestination",
    "ProviderType",
    "ModelContextRole",
    # Chat models
    "Participant",
    "BaseMessage",
    "UserMessage",
    "ModelMessage",
    "SystemMessage",
    "ExceptionMessage",
    "Message",
    # Database models
    "Channel",
    "Guild",
    "ModelEntry",
    # Function call
    "FunctionCall",
    # Provider
    "ProviderModel",
    # Model context
    "Model",
    "ModelContext",
    "ModelContextMessage",
    "ModelResponseStream",
    # Context
    "ChannelContext",
    # Exceptions
    "GeminiError",
    "FatalError",
    "ConfigurationError",
    "ChannelError",
    "ChannelNotRegisteredError",
    "ChannelAlreadyRegisteredError",
    "ConversationError",
    "MessageProcessingError",
    "ProviderError",
    "ProviderGenerateError",
    "ProviderRateLimitError",
    "ProviderAPIError",
    "ProviderAPIRateLimitError",
    "ProviderTimeoutError",
    "FunctionCallError",
    "ContextGenerationError",
]
