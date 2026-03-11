"""Exception hierarchy for the Gemini plugin.

Inheritance tree
================

.. code-block:: text

    GeminiError
    ├── FatalError                     # Signals that retry attempts should stop immediately
    ├── ConfigurationError             # Invalid or missing configuration
    ├── ChannelError                   # Channel CRUD errors
    │   ├── ChannelNotRegisteredError
    │   └── ChannelAlreadyRegisteredError
    ├── ConversationError              # Conversation-level failures
    │   └── MessageProcessingError     # Failure while processing a queued message
    ├── ProviderError                  # Base for all provider/model errors
    │   ├── ProviderGenerateError      # Generation failed (non-API reason)
    │   ├── ProviderRateLimitError     # Internal / self-imposed rate limit hit
    │   ├── ProviderAPIError           # Upstream API returned an error
    │   │   └── ProviderAPIRateLimitError  # Upstream API rate limit (HTTP 429, etc.)
    │   └── ProviderTimeoutError       # Request to the provider timed out
    ├── FunctionCallError              # Error executing a function call
    └── ContextGenerationError         # Error building model context
"""

from typing import Any, Optional


# ── Base ──────────────────────────────────────────────────────────────────


class GeminiError(Exception):
    """Base exception for the Gemini plugin."""

    def __init__(self, message: str = "", *args: Any, **kwargs: Any):
        self.message = message
        super().__init__(message, *args, **kwargs)


class FatalError(GeminiError):
    """Raised to signal that the current operation should **not** be retried.

    The message queue worker will catch this and immediately give up instead
    of attempting further retries.
    """


# ── Configuration ─────────────────────────────────────────────────────────


class ConfigurationError(GeminiError):
    """Raised when plugin configuration is invalid or missing."""


# ── Channel CRUD ──────────────────────────────────────────────────────────


class ChannelError(GeminiError):
    """Base exception for channel-related operations."""

    def __init__(self, channel_id: int, message: str = "", *args: Any, **kwargs: Any):
        self.channel_id = channel_id
        super().__init__(message or f"Channel error for {channel_id}", *args, **kwargs)


class ChannelNotRegisteredError(ChannelError):
    """Raised when an operation targets a channel that is not registered."""

    def __init__(self, channel_id: int):
        super().__init__(
            channel_id,
            f"Channel {channel_id} is not registered as a Gemini conversation.",
        )


class ChannelAlreadyRegisteredError(ChannelError):
    """Raised when attempting to register a channel that already exists."""

    def __init__(self, channel_id: int):
        super().__init__(
            channel_id,
            f"Channel {channel_id} is already registered as a Gemini conversation.",
        )


# ── Conversation / message processing ────────────────────────────────────


class ConversationError(GeminiError):
    """Raised for conversation-level failures."""


class MessageProcessingError(ConversationError):
    """Raised when the message queue fails to process a message."""


# ── Provider ──────────────────────────────────────────────────────────────


class ProviderError(GeminiError):
    """Base exception for provider-related errors."""

    def __init__(
        self,
        message: str = "",
        *args: Any,
        provider_name: Optional[str] = None,
        **kwargs: Any,
    ):
        self.provider_name = provider_name
        prefix = f"[{provider_name}] " if provider_name else ""
        super().__init__(f"{prefix}{message}", *args, **kwargs)


class ProviderGenerateError(ProviderError):
    """Raised when generation fails for a non-API reason (e.g. bad context)."""


class ProviderRateLimitError(ProviderError):
    """Raised when an internal / self-imposed rate limit is hit.

    This is distinct from an upstream API rate limit and is typically used
    for concurrency or token-budget throttling within the plugin itself.
    """

    def __init__(
        self,
        message: str = "Internal rate limit exceeded",
        *args: Any,
        retry_after: Optional[float] = None,
        **kwargs: Any,
    ):
        self.retry_after = retry_after
        super().__init__(message, *args, **kwargs)


class ProviderAPIError(ProviderError):
    """Raised when the upstream provider API returns an error response."""

    def __init__(
        self,
        message: str = "",
        *args: Any,
        status_code: Optional[int] = None,
        **kwargs: Any,
    ):
        self.status_code = status_code
        status = f" (HTTP {status_code})" if status_code else ""
        super().__init__(f"{message}{status}", *args, **kwargs)


class ProviderAPIRateLimitError(ProviderAPIError):
    """Raised when the upstream provider API returns a rate-limit response (HTTP 429 or equivalent)."""

    def __init__(
        self,
        message: str = "API rate limit exceeded",
        *args: Any,
        retry_after: Optional[float] = None,
        **kwargs: Any,
    ):
        self.retry_after = retry_after
        super().__init__(message, *args, status_code=429, **kwargs)


class ProviderTimeoutError(ProviderError):
    """Raised when a request to the provider times out."""


# ── Function calls ────────────────────────────────────────────────────────


class FunctionCallError(GeminiError):
    """Raised when a function call execution fails."""

    def __init__(
        self,
        message: str = "",
        *args: Any,
        function_name: Optional[str] = None,
        **kwargs: Any,
    ):
        self.function_name = function_name
        prefix = f"Function '{function_name}': " if function_name else ""
        super().__init__(f"{prefix}{message}", *args, **kwargs)


# ── Context generation ────────────────────────────────────────────────────


class ContextGenerationError(GeminiError):
    """Raised when building the model context fails."""
