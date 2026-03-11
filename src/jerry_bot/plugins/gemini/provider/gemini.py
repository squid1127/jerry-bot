"""Gemini provider for the Gemini plugin."""

from .base import Provider
from ..models import (
    ModelContext,
    ModelContextMessage,
    ModelResponseStream,
    ModelContextRole,
)
from ..config import ProviderConfig, GlobalConfig, ModelConfig
from typing import AsyncIterator
from ..models.exceptions import ProviderAPIError, ProviderGenerateError
from google.genai import types, Client


class GeminiProvider(Provider):
    """Provider implementation for Gemini LLMs."""

    def __init__(
        self, provider_config: ProviderConfig, global_config: GlobalConfig, name: str
    ):
        super().__init__(provider_config, global_config, name)
        self.client = Client(api_key=provider_config.api_key)

    async def generate(
        self, context: ModelContext
    ) -> AsyncIterator[ModelResponseStream]:
        """Generate a response from the Gemini model based on the provided context."""
        # Build the contents list from the context messages
        contents = []
        for msg in context.messages:
            role = "user" if msg.role == ModelContextRole.USER else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg.content)])
            )

        config = types.GenerateContentConfig(
            system_instruction=context.prompt or None,
            temperature=context.model.temperature,
            max_output_tokens=context.model.max_tokens,
            top_k=context.model.top_k,
            top_p=context.model.top_p,
        )

        try:
            async for chunk in await self.client.aio.models.generate_content_stream(  # type: ignore[misc]
                model=context.model.name,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    yield ModelResponseStream(content=chunk.text)
        except Exception as e:
            raise ProviderAPIError(f"Gemini API error: {e}")
