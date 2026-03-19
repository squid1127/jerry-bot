"""Data models for the Gemini plugin."""

from .enums import MessageSource, MessageDestination, ProviderType, ModelContextRole
from .message import (
    Participant,
    BaseMessage,
    UserMessage,
    ModelMessage,
    FunctionResponseMessage,
    SystemMessage,
    ExceptionMessage,
    Message,
)
from .database import ChannelRecord, GuildRecord, LLMProfileRecord
from .function_call import FunctionCall
from .provider import ProviderModel
from .llm import LLMProfile, LLMContext, LLMContextMessage, LLMResponseStream
from .channel import OutputContext, Channel
from .exceptions import (
    GeminiError,
    FatalError,
    ConfigurationError,
    ChannelError,
    ChannelNotRegisteredError,
    ChannelAlreadyRegisteredError,
    ConversationError,
    MessageProcessingError,
    ConversationInactivityTimeoutError,
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
    "FunctionResponseMessage",
    "SystemMessage",
    "ExceptionMessage",
    "Message",
    # Database models
    "ChannelRecord",
    "GuildRecord",
    "LLMProfileRecord",
    # Function call
    "FunctionCall",
    # Provider
    "ProviderModel",
    # Model context
    "LLMProfile",
    "LLMContext",
    "LLMContextMessage",
    "LLMResponseStream",
    # Context
    "OutputContext",
    "Channel",
    # Exceptions
    "GeminiError",
    "FatalError",
    "ConfigurationError",
    "ChannelError",
    "ChannelNotRegisteredError",
    "ChannelAlreadyRegisteredError",
    "ConversationError",
    "MessageProcessingError",
    "ConversationInactivityTimeoutError",
    "ProviderError",
    "ProviderGenerateError",
    "ProviderRateLimitError",
    "ProviderAPIError",
    "ProviderAPIRateLimitError",
    "ProviderTimeoutError",
    "FunctionCallError",
    "ContextGenerationError",
]
