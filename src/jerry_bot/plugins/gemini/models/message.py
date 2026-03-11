"""Chat message models for Gemini plugin."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, Union
import discord

from .enums import MessageSource, MessageDestination, ModelContextRole
from .function_call import FunctionCall

@dataclass(frozen=True, slots=True)
class Participant:
    """Dataclass for a chat user."""

    id: int
    username: str
    display_name: Optional[str] = None

    @property
    def name(self) -> str:
        """Get the display name if available, otherwise the username."""
        return self.display_name or self.username

    @property
    def mention(self) -> str:
        """Get the Discord mention string for the user."""
        return f"<@{self.id}>"


@dataclass(frozen=True, slots=True)
class BaseMessage(ABC):
    """Base class for all chat messages."""

    @property
    @abstractmethod
    def source(self) -> MessageSource:
        """Get the message source."""
        pass

    @property
    @abstractmethod
    def destination(self) -> MessageDestination:
        """Get the message destination."""
        pass
    
    @property
    def context_role(self) -> ModelContextRole:
        """Get the model context role corresponding to the message source."""
        if self.source == MessageSource.MODEL:
            return ModelContextRole.MODEL
        return ModelContextRole.USER

@dataclass(frozen=True, slots=True)
class UserMessage(BaseMessage):
    """Chat message from a user to the model."""

    user: Participant
    content: Optional[str] = None
    attachments: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate that at least content or attachments is provided."""
        if self.content is None and self.attachments is None:
            raise ValueError(
                "Content or attachments must be provided for user messages."
            )

    @property
    def source(self) -> MessageSource:
        return MessageSource.USER

    @property
    def destination(self) -> MessageDestination:
        return MessageDestination.MODEL

    @classmethod
    def from_discord_message(cls, message: discord.Message) -> "UserMessage":
        """Create a UserMessage instance from a Discord message."""
        user = Participant(
            id=message.author.id,
            username=message.author.name,
            display_name=message.author.display_name,
        )

        return cls(user=user, content=message.content)


@dataclass(frozen=True, slots=True)
class ModelMessage(BaseMessage):
    """Chat message from the model to the user."""

    content: Optional[str] = None
    function_call: Optional[FunctionCall] = None

    def __post_init__(self):
        """Validate that at least content or function_call is provided."""
        if self.content is None and self.function_call is None:
            raise ValueError(
                "Content or function call must be provided for model messages."
            )

    @property
    def source(self) -> MessageSource:
        return MessageSource.MODEL

    @property
    def destination(self) -> MessageDestination:
        return MessageDestination.USER


@dataclass(frozen=True, slots=True)
class SystemMessage(BaseMessage):
    """System message to the user."""

    content: str

    @property
    def source(self) -> MessageSource:
        return MessageSource.SYSTEM

    @property
    def destination(self) -> MessageDestination:
        return MessageDestination.USER


@dataclass(frozen=True, slots=True)
class ExceptionMessage(BaseMessage):
    """Internal message representing an exception during processing.

    Attributes:
        error: The exception that occurred.
        fatal: Whether this error should halt the conversation.
        source: The source of the message, depending on where the error occurred (default is SYSTEM).
    """

    error: Exception
    fatal: bool = False  # Indicates if this error should halt the conversation
    message: Optional[Message] = None  # The message being processed when the error occurred

    @property
    def source(self) -> MessageSource:
        return MessageSource.SYSTEM

    @property
    def destination(self) -> MessageDestination:
        if self.fatal or self.source == MessageSource.MODEL:
            return (
                MessageDestination.USER
            )  # Fatal errors should be communicated to the user

        return (
            MessageDestination.MODEL
        )  # Non-fatal errors passed to model for handling/logging
        
    @property
    def content(self) -> str:
        """Get the string representation of the error for logging or model processing."""
        return str(self.error)


# Type alias for uniform handling in pipelines
Message = Union[UserMessage, ModelMessage, SystemMessage, ExceptionMessage]
