"""OpenRouter provider for the Gemini plugin."""

from .base import Provider
from ..models import LLMContext, LLMResponseStream, ModelContextRole, ProviderCapability
from ..config import ProviderConfig, GlobalConfig
from typing import AsyncIterator
from ..models.exceptions import ProviderAPIError
from openrouter import OpenRouter



class OpenRouterProvider(Provider):
    """Provider implementation for OpenRouter (OpenAI-compatible API)."""

    def __init__(self, provider_config: ProviderConfig, name: str):
        super().__init__(provider_config, name)
        self.client = OpenRouter(
            api_key=provider_config.api_key, http_referer=provider_config.http_referer
        )

    async def generate(self, context: LLMContext) -> AsyncIterator[LLMResponseStream]:
        """Generate a streaming response from OpenRouter based on the provided context."""
        messages = []
        if context.prompt:
            messages.append({"role": "system", "content": context.prompt})

        for msg in context.messages:
            role = "user" if msg.role == ModelContextRole.USER else "assistant"
            messages.append({"role": role, "content": msg.content})

        kwargs = {
            "model": context.profile.model_name,
            "messages": messages,
            "stream": True,
            "cache_control": {"type": "ephemeral"},
        }
        if context.profile.temperature is not None:
            kwargs["temperature"] = context.profile.temperature
        if context.profile.max_tokens is not None:
            kwargs["max_tokens"] = context.profile.max_tokens
        if context.profile.top_p is not None:
            kwargs["top_p"] = context.profile.top_p
        if context.session_id is not None:
            kwargs["session_id"] = context.session_id

        try:
            reasoning_list = []
            stream = await self.client.chat.send_async(**kwargs)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = delta.content or None
                reasoning = getattr(delta, "reasoning", None)
                if content:
                    yield LLMResponseStream(content=content)
                elif reasoning:
                    reasoning_list.append(reasoning)
                    
        except Exception as e:
            raise ProviderAPIError(f"OpenRouter API error: {e}") from e


    @property
    def capabilities(self) -> set[ProviderCapability]:
        """OpenRouter supports tool calls, system prompts, and streaming."""
        return {
            ProviderCapability.SYSTEM_PROMPT,
            ProviderCapability.STREAMING,
        }
