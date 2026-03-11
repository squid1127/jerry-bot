"""Manager for LLM providers in the Gemini plugin."""

from typing import ClassVar, Dict, Type

from .base import Provider
from ..config import GlobalConfig
from ..models.enums import ProviderType

from .ollama import OllamaProvider
from .gemini import GeminiProvider
from .openrouter import OpenRouterProvider


class ProviderManager:
    """Manages the initialization and retrieval of LLM providers."""

    PROVIDER_CLASSES: ClassVar[Dict[ProviderType, Type[Provider]]] = {
        ProviderType.OLLAMA: OllamaProvider,
        ProviderType.GEMINI: GeminiProvider,
        ProviderType.OPENROUTER: OpenRouterProvider,
    }

    def __init__(self, global_config: GlobalConfig):
        """Initialize the ProviderManager with the given global configuration."""
        self.global_config = global_config
        self._providers: Dict[str, Provider] = {}

        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize all providers defined in the global configuration."""
        for name, config in self.global_config.providers.items():
            provider_class = self.PROVIDER_CLASSES.get(config.type)
            if not provider_class:
                raise NotImplementedError(
                    f"Provider type '{config.type.value}' for provider '{name}' is not yet implemented."
                )

            # Instantiate the provider and store it
            self._providers[name] = provider_class(config, self.global_config, name)

    def get_provider(self, name: str) -> Provider:
        """
        Get a registered provider by name.

        Args:
            name: The name of the provider to retrieve.

        Returns:
            The initialized Provider instance.

        Raises:
            KeyError: If the provider name is not found in the initialized providers.
        """
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' is not configured.")
        return self._providers[name]

    def get_default_provider(self) -> Provider:
        """
        Get the default provider as defined in the global configuration.

        Returns:
            The default Provider instance.
        """
        return self.get_provider(self.global_config.default_provider)

    @property
    def providers(self) -> Dict[str, Provider]:
        """Get all initialized providers."""
        return self._providers
