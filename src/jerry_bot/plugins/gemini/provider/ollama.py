"""Ollama provider for the Gemini plugin."""

from .base import Provider
from ollama import AsyncClient
import ollama
from ..models import (
    ModelContext,
    ModelContextMessage,
    ModelResponseStream,
    ModelContextRole,
)
from ..config import ProviderConfig, GlobalConfig, ModelConfig
from typing import AsyncIterator
from ..models.exceptions import ProviderAPIError, ProviderGenerateError

class OllamaProvider(Provider):
    """Provider implementation for Ollama LLMs."""

    def __init__(
        self, provider_config: ProviderConfig, global_config: GlobalConfig, name: str
    ):
        super().__init__(provider_config, global_config, name)

        headers = {}
        if provider_config.api_key:
            headers["Authorization"] = f"Bearer {provider_config.api_key}"
        self.client = AsyncClient(provider_config.endpoint, headers=headers)

    async def generate(
        self, context: ModelContext
    ) -> AsyncIterator[ModelResponseStream]:
        """Generate a response from the Ollama model based on the provided context."""
        # Convert ModelContext to Ollama's expected format
        messages = []
        if context.prompt:
            messages.append({"role": "system", "content": context.prompt})

        for msg in context.messages:
            role = "user" if msg.role == ModelContextRole.USER else "assistant"
            messages.append({"role": role, "content": msg.content})

        # Call the Ollama API
        generator = (await self.client.chat(model=context.model.name, messages=messages, stream=True))
        try:
            async for chunk in generator:  # type: ignore
                yield ModelResponseStream(
                    content=chunk["message"]["content"]
                )
        except ollama.RequestError as e:
            raise ProviderAPIError(f"Ollama API request failed: {e}")
        except ollama.ResponseError as e:
            raise ProviderAPIError(f"Ollama API returned an error response: {e}")