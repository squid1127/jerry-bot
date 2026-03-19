"""Provider protocol for Gemini plugin providers."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, TYPE_CHECKING

from ..models import LLMContext, LLMProfile, LLMResponseStream
from ..config.provider_config import ProviderConfig

if TYPE_CHECKING:
    from ..config.global_config import GlobalConfig


class Provider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, provider_config: ProviderConfig, name: str):
        self.provider_config = provider_config
        self._name = name

    @abstractmethod
    async def generate(self, context: LLMContext) -> AsyncIterator[LLMResponseStream]:
        """Async iterator                if not event_set and first_message_event is not None:
        first_message_event.set()
        event_set = True method that yields model responses based on the provided context.
        """
        
        yield  # type: ignore
        raise NotImplementedError("Subclasses must implement the generate method.")

    async def model_exists(self, model_name: str) -> bool:
        """Check if a model with the given name exists in the provider. If not implemented by the provider, defaults to True for all models."""
        
        return True  # Default implementation assumes all models exist; override if provider has a fixed model set.

    @property
    def name(self) -> str:
        """Get the name of the provider."""
        return self._name

    @property
    def default_llm_profile(self) -> LLMProfile:
        """Get the default model configuration for this provider."""
        return LLMProfile.from_config(self.provider_config.default_model, self.name)

    @property
    def friendly_name(self) -> str:
        """Get a user-friendly name for the provider, falling back to the provider name if not set."""
        return self.provider_config.friendly_name or self.name
