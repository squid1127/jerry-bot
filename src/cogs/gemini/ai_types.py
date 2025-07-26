"""Provides types for AI interactions, including method calls and responses."""

# Discord Types
import discord
import asyncio
from io import BytesIO

# Decorators
from dataclasses import dataclass, field
from enum import Enum


# Responses
class AIResponseSource(Enum):
    """
    Enum for the source of the AI response.
    """

    LLM = "llm"
    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"
    METHOD = "method"


@dataclass
class AIResponse:
    """
    Represents a response from the AI model.
    """

    text: str
    usage: dict = None
    files: list["QueryAttachment"] = field(default_factory=list)
    function_calls: list["AIMethodCall"] = field(default_factory=list)
    embeds: list[dict] = field(
        default_factory=list
    )  # Assuming embeds are represented as dicts
    method_call: "AIMethodCall" = None  # The method call that triggered this response
    source: AIResponseSource = AIResponseSource.LLM


# Query Types
class AIQuerySource(Enum):
    """
    Enum for the source of the AI query.
    """

    USER = "user"
    SYSTEM = "system"
    MODEL = "model"
    AGENT = "agent"
    METHOD = "method"


@dataclass
class AIQueryUserAuthor:
    """
    Represents the user who made the query.
    """

    id: int = None
    username: str = None
    display_name: str = None
    mention: str = None


@dataclass
class AIQueryDiscordRefrences:
    """
    Represents the Discord references for a query.
    """

    message: discord.Message = None
    member: discord.Member = None
    channel: discord.TextChannel = None
    guild: discord.Guild = None


@dataclass
class QueryAttachment:
    """
    Represents an attachment in an AI query.
    """

    attachment_id: str = None
    url: str = None
    filename: str = None
    content_type: str = None
    raw_data: bytes = None
    buffered_data: BytesIO = None  # Buffered data for Discord
    discord_use_buffered_data: bool = True


@dataclass
class AIQuery:
    """
    Represents a chat query to the AI model.
    This can include a message, reaction, or embed.
    """

    message: str = None
    reaction: str = None
    embeds: list[dict] = field(
        default_factory=list
    )  # Assuming embeds are represented as dicts
    attachments: list[QueryAttachment] = field(default_factory=list)
    source: AIQuerySource = AIQuerySource.USER
    author: AIQueryUserAuthor = field(default_factory=AIQueryUserAuthor)
    is_reply: bool = False  # Indicates if this query is a reply to another message
    reply: "AIQuery" = None  # Reference to another AIQuery if this is a reply
    discord: AIQueryDiscordRefrences = field(
        default_factory=AIQueryDiscordRefrences
    )  # Discord references for the query

    response_method: callable = None  # Method to call for live response handling


# Agents
@dataclass
class AIAgentQuery:
    """
    Represents a query to an AI agent.
    This should primarily be plain text, but can also include reactions or embeds.
    """

    prompt: str
    system_prompt: str = None


@dataclass
class AIAgentResponse:
    """
    Represents a response from an AI agent.
    This can include text, embeds, and method calls.
    """

    text: str
    files: list[QueryAttachment] = field(default_factory=list)


# Method Calls
@dataclass
class AIMethodCall:
    """
    Represents a request for a AI Method/function call.
    """

    method_name: str
    arguments: dict = field(default_factory=dict)
    query: AIQuery = None  # The query that triggered the method call (for context)
    method_config: dict = field(default_factory=dict)  # Configuration for the method


class AIMethodStatus(Enum):
    """
    Enum for the status of an AI method call.
    """

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class AIMethodResponse:
    """
    Represents a response from an AI method call. Use response_model and/or response_user to decide where to send the response. Using neither will not send a response and assumes the method is a silent and successful in operation.
    """

    method_name: str  # Name of the method called
    status: AIMethodStatus
    response_user: AIResponse = (
        None  # Output an AIResponse object if the method call was successful
    )
    response_model: str = None  # Return an output to the model rather than the user
    response_model_query: AIQuery = None  # Return a query as an output to the model
