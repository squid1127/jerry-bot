"""Model context generator for Gemini."""

from typing import TYPE_CHECKING, Optional

from ..models import Message, ModelContext, ModelContextMessage, Model, Guild, Channel
if TYPE_CHECKING:
    from ..config.global_config import GlobalConfig
from .message_render import MessageRenderer


class ContextGenerator:
    """Generates the context for a model response based on the conversation history and model configuration."""
    
    def __init__(self, global_config: "GlobalConfig", guild_config: "Guild", model_config: "Model", channel_config: Optional["Channel"] = None, ephemeral: bool = False):
        self.model_config = model_config
        self.guild_config = guild_config
        self.global_config = global_config

        self.channel_config = channel_config
        self.ephemeral = ephemeral
        self.renderer = MessageRenderer()

    def generate_context(self, messages: list[Message]) -> ModelContext:
        """Generate the model context from a list of messages."""
        rendered_messages = []
        for message in messages:
            rendered_messages.extend(self._message_to_context_message(message))
        return ModelContext(
            prompt=self.make_prompt(),
            messages=rendered_messages,
            model=self.model_config,
        )
        
    def make_prompt(self) -> str:
        """Generate the prompt for the model based on the configuration."""
        # Start with the global prompt if it exists
        prompt_parts: dict[str, str] = {}
        if self.global_config.global_prompt:
            prompt_parts['base'] = self.global_config.global_prompt
    
        # Add model-specific prompt if it exists
        if self.model_config.prompt:
            prompt_parts['model'] = self.model_config.prompt
    
        # Add guild-specific prompt if it exists
        if self.guild_config.prompt:
            prompt_parts['guild'] = self.guild_config.prompt
            
        # Add channel-specific prompt if it exists
        if self.channel_config and self.channel_config.prompt:
            prompt_parts['channel'] = self.channel_config.prompt

        # Convert the prompt parts into a single prompt string
        prompt = ""
        for name, part in prompt_parts.items():
            prompt += f"[{name.upper()}]\n{part}\n\n"
        return prompt.strip()

    def _message_to_context_message(self, message: Message) -> list[ModelContextMessage]:
        """Convert a Message object to a ModelContextMessage."""
        rendered_content = self.renderer.render(message)
        return [ModelContextMessage(
            role=message.context_role,
            content=rendered_content,
        )]