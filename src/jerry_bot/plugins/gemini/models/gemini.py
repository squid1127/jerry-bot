"""Models related to Gemini interactions."""

from typing import Optional
from squid_core.config_types import ConfigOption, ConfigSchema, ConfigRequired
from dataclasses import dataclass
from enum import Enum
import discord

@dataclass
class GeminiLLMConfig:
    """Configuration for Gemini LLM integration."""
    
    model_name: str
    temperature: float = 2.0
    top_p: float = 1.0
    
    # Feature toggles
    gemini_url_context: bool = False
    gemini_search: bool = False
    gemini_code_execution: bool = False
    functions: bool = False
    chat_mode: bool = False
    
    prompt: Optional[str] = None  # Custom prompt for the LLM, if any.
    
    def __post_init__(self):
        """Post-initialization to validate config values."""
        
        if self.functions:
            if self.gemini_code_execution or self.gemini_search or self.gemini_url_context:
                raise ValueError("Function calling cannot be enabled with other Gemini features.")
            
class MessageRole(Enum):
    """Enumeration of message roles in Gemini chat."""
    
    USER = "user" # Message from the user
    LLM = "llm"   # Message from the LLM
    METHOD = "method" # Message response from a method call
    SYSTEM = "system" # System-level message
            
@dataclass
class MessagePart:
    """Represents a part of a Gemini chat message.
    
    Attributes:
        role (MessageRole): The role of the message part.
        destination (MessageRole): The intended recipient of the message part.
        content (Optional[str]): The textual content of the message part.
        fp (Optional[str]): File path for content, if applicable.
        discord (Optional["DiscordContext"]): Contextual Discord information.
        call (Optional["FunctionCallContext"]): Context for function calls, if applicable.
        embeds (Optional[list[dict]]): Discord embeds, if the message is to USER.
    """
    
    role: MessageRole
    destination: MessageRole = MessageRole.LLM
    content: Optional[str] = None
    fp: Optional[str] = None
    discord: Optional["DiscordContext"] = None
    call: Optional["FunctionCallContext"] = None
    embeds: Optional[list[dict]] = None # Discord embeds, if the message is to USER.
    
    def __post_init__(self):
        """Post-initialization to validate message part values."""
        
        if self.destination == MessageRole.USER:
            if not (self.content or self.embeds):
                raise ValueError("One of [content, embeds] must be provided for messages to USER.")
        elif self.destination == MessageRole.LLM:
            if not (self.content or self.fp):
                raise ValueError("One of [content, fp] must be provided for messages to LLM.")
        elif self.destination == MessageRole.METHOD:
            if not (self.call):
                raise ValueError("Call must be provided for messages to METHOD.")
            if not isinstance(self.call.args, dict):
                raise ValueError("Args must be a dictionary for messages to METHOD.")
        else:
            raise ValueError("Invalid destination for MessagePart.")
        
@dataclass
class FunctionCallContext:
    """Contextual information for function calls in Gemini."""
    
    call: type # Class of the function being called
    args: dict # Arguments provided for the function call
    name: str # Name of the function being called
    
@dataclass
class FunctionCallParam:
    """Represents a parameter for a function call in Gemini."""
    
    name: str
    type: type
    description: Optional[str] = None
    required: bool = False
    
    def __post_init__(self):
        """Post-initialization to validate parameter values."""
        
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("FunctionCallParam name must be a non-empty string.")

        if not isinstance(self.type, type):
            raise ValueError("FunctionCallParam type must be a type.")
        
        if self.type not in [str, int, float, bool, list, dict]:
            raise ValueError("FunctionCallParam type must be a valid JSON type.")
        
@dataclass
class DiscordContext:
    """Contextual information for Discord interactions, such as message and user details."""
    
    message: Optional[discord.Message] = None
    user: Optional[discord.User] = None
    channel: Optional[discord.abc.Messageable] = None
    guild: Optional[discord.Guild] = None
    interaction: Optional[discord.Interaction] = None
    