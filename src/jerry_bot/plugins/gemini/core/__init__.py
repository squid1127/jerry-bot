"""Core conversation management and message processing for the Gemini plugin."""

from .constants import GLOBAL_PROMPT
from .conversation import Conversation
from .message_queue import MessageQueue

# NOTE: ConversationManager is intentionally not imported here to avoid a
# circular import with the config package (config → core.constants → core/__init__ → manager → config).
# Import it directly: ``from .core.manager import ConversationManager``

__all__ = [
    "GLOBAL_PROMPT",
    "Conversation",
    "MessageQueue",
]
