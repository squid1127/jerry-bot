"""Constants for Gemini output processing."""

DEFAULT_MAX_CHUNK_SIZE = 1900  # Discord message limit is 2000 characters, leaving room for formatting and metadata
DEFAULT_TYPING_TIMEOUT = 8  # Seconds to wait before timing out the typing indicator if the provider is taking too long to respond

FORBIDDEN_ERROR_MESSAGE = "Bot does not have permission to send messages in this channel."