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
    "Attachment",
    "BaseMessage",
    # Context
    "Channel",
    "ChannelAlreadyRegisteredError",
    "ChannelError",
    "ChannelNotRegisteredError",
    # Database models
    "ChannelRecord",
    "ConfigurationError",
    "ContextGenerationError",
    "ConversationError",
    "ConversationInactivityTimeoutError",
    "Embed",
    "ExceptionMessage",
    "FatalError",
    # Function call
    "FunctionCall",
    "FunctionCallError",
    # Exceptions
    "GeminiError",
    "GuildRecord",
    "LLMContext",
    "LLMContextMessage",
    # Model context
    "LLMProfile",
    "LLMProfileRecord",
    "LLMResponseStream",
    "Message",
    "MessageDestination",
    "MessageProcessingError",
    # Enums
    "MessageSource",
    "ModelContextRole",
    "ModelMessage",
    # Chat models
    "Participant",
    "ProviderAPIError",
    "ProviderAPIRateLimitError",
    "ProviderCapability",
    "ProviderError",
    "ProviderGenerateError",
    # Provider
    "ProviderModel",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "ProviderType",
    "SystemMessage",
    "ToolResponseMessage",
    "UserMessage",
]
