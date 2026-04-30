"""Chat message models for Gemini plugin."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Union
from datetime import datetime

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
class Attachment:
    """Dataclass for a chat attachment."""

    filename: str
    content: bytes
    mime_type: Optional[str] = None  # e.g., "image/png", "application/pdf", etc.

@dataclass(frozen=True, slots=True)
class Embed:
    """Dataclass for a chat embed."""

    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    fields: Optional[dict[str, str]] = None  # e.g., {"Field Name": "Field Value"}
    footer: Optional[str] = None
    
    def as_string(self) -> str:
        """Convert the embed to a string representation for model processing."""
        parts = []
        if self.title:
            parts.append(f"[Embed: **{self.title}**]")
        if self.author:
            parts.append(f"by {self.author}")
        if self.description:
            parts.append(self.description)
        if self.fields:
            for name, value in self.fields.items():
                parts.append(f"**{name}:** {value}")
        if self.footer:
            parts.append(f"*{self.footer}*")
        return "\n".join(parts)
    
    def __str__(self) -> str:
        """String representation of the embed for logging or model processing."""
        return self.as_string()


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
    attachments: Optional[list[Attachment]] = None
    embeds: Optional[list[Embed]] = None
    sent_at: datetime = field(default_factory=datetime.now)

    @property
    def source(self) -> MessageSource:
        return MessageSource.USER

    @property
    def destination(self) -> MessageDestination:
        return MessageDestination.MODEL


@dataclass(frozen=True, slots=True)
class ModelMessage(BaseMessage):
    """Chat message from the model to the user."""

    content: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    sent_at: datetime = field(default_factory=datetime.now)

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
class ToolResponseMessage(BaseMessage):
    """Tool response message fed back to the model."""

    function_call: FunctionCall
    response: str
    error: bool = False
    sent_at: datetime = field(default_factory=datetime.now)

    @property
    def source(self) -> MessageSource:
        return MessageSource.TOOL_CALL

    @property
    def destination(self) -> MessageDestination:
        return MessageDestination.MODEL

    @property
    def content(self) -> str:
        """Return textual response content for compatibility with renderers."""
        return self.response


@dataclass(frozen=True, slots=True)
class SystemMessage(BaseMessage):
    """System message to the user."""

    content: str
    sent_at: datetime = field(default_factory=datetime.now)

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
    message: Optional[Message] = (
        None  # The message being processed when the error occurred
    )
    sent_at: datetime = field(default_factory=datetime.now)

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
Message = Union[
    UserMessage,
    ModelMessage,
    ToolResponseMessage,
    SystemMessage,
    ExceptionMessage,
]
