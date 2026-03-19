"""Model context generator for Gemini."""

from typing import TYPE_CHECKING, Optional

from ..models import (
    Message,
    LLMContext,
    LLMContextMessage,
    LLMProfile,
    GuildRecord,
    ChannelRecord,
)

if TYPE_CHECKING:
    from ..config.global_config import GlobalConfig
from .message_render import MessageRenderer

from ..core.context import SessionContext


class LLMContextGenerator:
    """Generates the context for a model response based on the conversation history and model configuration."""

    def __init__(
        self,
        context: SessionContext,
    ):
        self.renderer = MessageRenderer()
        self._context = context

    def generate_context(self, messages: list[Message]) -> LLMContext:
        """Generate the model context from a list of messages."""
        rendered_messages = []
        for message in messages:
            rendered_messages.extend(self._message_to_context_message(message))
        return LLMContext(
            prompt=self.make_prompt(),
            messages=rendered_messages,
            profile=self._context.llm_profile,
        )

    def make_prompt(self) -> str:
        """Generate the prompt for the model based on the configuration."""
        # Start with the global prompt if it exists
        prompt_parts: dict[str, str] = {}
        if self._context.channel.override_system_prompt:
            prompt_parts["base"] = self._context.channel.prompt or ""
        
        else:
            if self._context.global_config.global_prompt:
                prompt_parts["base"] = self._context.global_config.global_prompt

            # Add model-specific prompt if it exists
            if self._context.llm_profile.prompt:
                prompt_parts["profile"] = self._context.llm_profile.prompt

            # Add guild-specific prompt if it exists
            if self._context.guild.prompt:
                prompt_parts["guild"] = self._context.guild.prompt

            # Add channel-specific prompt if it exists
            if self._context.channel.prompt:
                prompt_parts["channel"] = self._context.channel.prompt

        # Convert the prompt parts into a single prompt string
        prompt = ""
        for name, part in prompt_parts.items():
            prompt += f"[{name.upper()}]\n{part}\n\n"
        return prompt.strip()

    def _message_to_context_message(self, message: Message) -> list[LLMContextMessage]:
        """Convert a Message object to a ModelContextMessage."""
        rendered_content = self.renderer.render(message)
        return [
            LLMContextMessage(
                role=message.context_role,
                content=rendered_content,
            )
        ]
