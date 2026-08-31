"""Data models for the Gemini plugin."""

from .channel import Channel
from .database import ChannelRecord, GuildRecord, LLMProfileRecord
from .enums import (
    MessageDestination,
    MessageSource,
    ModelContextRole,
    ProviderCapability,
    ProviderType,
)
from .exceptions import (
    ChannelAlreadyRegisteredError,
    ChannelError,
    ChannelNotRegisteredError,
    ConfigurationError,
    ContextGenerationError,
    ConversationError,
    ConversationInactivityTimeoutError,
    FatalError,
    FunctionCallError,
    GeminiError,
    MessageProcessingError,
    ProviderAPIError,
    ProviderAPIRateLimitError,
    ProviderError,
    ProviderGenerateError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from .function_call import FunctionCall
from .llm import LLMContext, LLMContextMessage, LLMProfile, LLMResponseStream
from .message import (
    Attachment,
    BaseMessage,
    Embed,
    ExceptionMessage,
    Message,
    ModelMessage,
    Participant,
    SystemMessage,
    ToolResponseMessage,
    UserMessage,
)
from .provider import ProviderModel

__all__ = [
    # Enums
    "MessageSource",
    "MessageDestination",
    "ProviderType",
    "ModelContextRole",
    "ProviderCapability",
    # Chat models
    "Participant",
    "Attachment",
    "Embed",
    "BaseMessage",
    "UserMessage",
    "ModelMessage",
    "ToolResponseMessage",
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
