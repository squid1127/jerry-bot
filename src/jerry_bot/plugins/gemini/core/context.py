"""Conversation session-scoped context object"""

from dataclasses import dataclass, field
from typing import Optional

from ..dc_chat.input_processor import OutputContext

from ..models import Channel, LLMProfile, GuildRecord
from ..provider import Provider
from ..config import GlobalConfig


@dataclass(slots=True, frozen=False)
class SessionContext:
    """Session-scoped context object containing instances related to a conversation session"""

    channel: Channel
    guild: GuildRecord

    output_context: OutputContext
    llm_profiles: list[LLMProfile]
    providers: dict[str, Provider]

    global_config: GlobalConfig

    _current_profile: LLMProfile | None = field(init=False, repr=False)

    def provider_for_profile(self, profile: LLMProfile) -> Optional[Provider]:
        """Get the provider instance associated with a given LLM profile."""
        return self.providers.get(profile.provider_name)

    def set_active_profile(self, profile: LLMProfile) -> None:
        """Set the active LLM profile for this session."""
        if profile not in self.llm_profiles:
            raise ValueError(
                f"Profile {profile.model_name} is not in the list of available profiles"
            )
        self._current_profile = profile

    @property
    def provider(self) -> Provider:
        """Get the provider instance for the primary LLM profile."""
        if not self.llm_profiles:
            raise ValueError("No LLM profiles available")
        provider = self.provider_for_profile(self.llm_profile)
        if not provider:
            raise ValueError(
                f"No provider found for profile {self.llm_profile.model_name}"
            )
        return provider

    @property
    def llm_profile(self) -> LLMProfile:
        """Get the primary LLM profile for this session."""
        if not self.llm_profiles:
            raise ValueError("No LLM profiles available")
        if self._current_profile is None:
            raise ValueError("Current LLM profile has not been set")
        return self._current_profile
