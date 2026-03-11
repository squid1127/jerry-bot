"""OpenRouter provider for the Gemini plugin."""

from .base import Provider
from ..models import (
    ModelContext,
    ModelResponseStream,
    ModelContextRole,
)
from ..config import ProviderConfig, GlobalConfig
from typing import AsyncIterator
from ..models.exceptions import ProviderAPIError
from openrouter import OpenRouter

from logging import getLogger

logger = getLogger(__name__)


class OpenRouterProvider(Provider):
    """Provider implementation for OpenRouter (OpenAI-compatible API)."""

    def __init__(
        self, provider_config: ProviderConfig, global_config: GlobalConfig, name: str
    ):
        super().__init__(provider_config, global_config, name)
        self.client = OpenRouter(
            api_key=provider_config.api_key,
        )

    async def generate(
        self, context: ModelContext
    ) -> AsyncIterator[ModelResponseStream]:
        """Generate a streaming response from OpenRouter based on the provided context."""
        messages = []
        if context.prompt:
            messages.append({"role": "system", "content": context.prompt})

        for msg in context.messages:
            role = "user" if msg.role == ModelContextRole.USER else "assistant"
            messages.append({"role": role, "content": msg.content})

        kwargs = {
            "model": context.model.name,
            "messages": messages,
            "stream": True,
        }
        if context.model.temperature is not None:
            kwargs["temperature"] = context.model.temperature
        if context.model.max_tokens is not None:
            kwargs["max_tokens"] = context.model.max_tokens
        if context.model.top_p is not None:
            kwargs["top_p"] = context.model.top_p

        try:
            stream = await self.client.chat.send_async(**kwargs)
            logger.info(f"OpenRouterProvider.generate called with kwargs: {kwargs}")
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = delta.content or None
                reasoning = getattr(delta, "reasoning", None)
                if content:
                    yield ModelResponseStream(content=content)
                elif reasoning:
                    logger.info(f"Reasoning token: {reasoning!r}")
        except Exception as e:
            raise ProviderAPIError(f"OpenRouter API error: {e}") from e
