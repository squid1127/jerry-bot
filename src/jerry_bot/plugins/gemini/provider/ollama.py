"""Ollama provider for the Gemini plugin."""

from .base import Provider
from ollama import AsyncClient
import ollama
from ..models import (
    LLMContext,
    LLMResponseStream,
    ModelContextRole,
)
from ..config import ProviderConfig, GlobalConfig
from typing import AsyncIterator
from ..models.exceptions import ProviderAPIError, ProviderGenerateError


class OllamaProvider(Provider):
    """Provider implementation for Ollama LLMs."""

    def __init__(self, provider_config: ProviderConfig, name: str):
        super().__init__(provider_config, name)

        headers = {}
        if provider_config.api_key:
            headers["Authorization"] = f"Bearer {provider_config.api_key}"
        self.client = AsyncClient(provider_config.endpoint, headers=headers)

        self.models: list[str] = []  # Cache for model names to avoid repeated API calls

    async def model_exists(self, model_name: str) -> bool:
        """Check if a model exists in Ollama, with caching."""
        if model_name in self.models:
            return True

        try:
            models: ollama.ListResponse = await self.client.list()
            self.models = [str(model.model) for model in models.models]
            return model_name in self.models
        except Exception as e:
            raise ProviderAPIError(f"Error checking model existence: {e}") from e

    async def generate(self, context: LLMContext) -> AsyncIterator[LLMResponseStream]:
        """Generate a response from the Ollama model based on the provided context."""

        # Convert ModelContext to Ollama's expected format
        messages = []
        if context.prompt:
            messages.append({"role": "system", "content": context.prompt})

        for msg in context.messages:
            role = "user" if msg.role == ModelContextRole.USER else "assistant"
            messages.append({"role": role, "content": msg.content})

        model = context.profile.model_name
        if not await self.model_exists(model):
            raise ProviderGenerateError(
                f"Model '{model}' does not exist locally in Ollama. Note: You may need to manually pull the model."
            )

        # Call the Ollama API
        try:
            generator = await self.client.chat(
                model=model, messages=messages, stream=True
            )
            async for chunk in generator:  # type: ignore
                yield LLMResponseStream(content=chunk["message"]["content"])
        except Exception as e:
            raise ProviderAPIError(f"Ollama API returned an error response: {e}") from e
