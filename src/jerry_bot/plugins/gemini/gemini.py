"""Wrapper for Gemini API interactions."""

from .models.config import GlobalConfig
from .models.gemini import GeminiLLMConfig, MessagePart, MessageRole

from google import genai
from google.genai import types as genai_types
from google.genai.chats import AsyncChat, Part
from typing import Optional


class GeminiLLM:
    """A wrapper class for interacting with the Gemini API."""

    def __init__(self, global_config: GlobalConfig, llm_config: GeminiLLMConfig, prompt: Optional[str] = None):
        """
        Initialize the Gemini LLM wrapper.

        Args:
            global_config (GlobalConfig): Global configuration for the Gemini plugin.
            llm_config (GeminiLLMConfig): Specific configuration for the Gemini LLM.
        """
        self.global_config = global_config
        self.config = llm_config
        self.chat_mode: bool = llm_config.chat_mode
        self.chat: AsyncChat | None = None
        self.prompt = prompt

        # Initialize the GenAI client with the provided API key
        self.client = genai.Client(api_key=self.global_config.api_key)

    async def initialize(self):
        """Asynchronously initialize any required resources."""

        if self.chat_mode:
            config = self._generate_config()
            self.chat = self.client.aio.chats.create(model=self.config.model_name, config=config)

    async def send_chat(self, parts: list[MessagePart]) -> None:
        """Send a chat message and receive a response.

        Args:
            parts (list[Part]): List of message parts to send in the chat.

        Returns:
            Content: The response content from the chat.
        """
        if not self.chat:
            await self.initialize()
            if not self.chat:
                raise ValueError("Failed to initialize chat. (Is chat_mode enabled?)")

        gem_parts = self._convert_dc_to_parts(parts)

        response = await self.chat.send_message(gem_parts)
        return self._convert_response_to_dc(response, source=parts[-1]) #! Cannot accurately map source parts

    def _convert_dc_to_parts(self, message_parts: list[MessagePart]) -> list[Part]:
        """Convert custom MessagePart objects to Gemini API Part objects.

        Args:
            message_parts (list[MessagePart]): List of custom message parts.

        Returns:
            list[Part]: List of Gemini API Part objects.
        """
        parts: list[Part] = []
        for mp in message_parts:
            if mp.role == MessageRole.LLM:
                raise ValueError(
                    "Wait, this doesn't make sense. You can't send a message from the LLM to the LLM."
                )
            elif mp.role == MessageRole.USER:
                if mp.discord:
                    header = f"[User: {mp.discord.user.display_name}]"
                else:
                    header = "[User]"
                content = f"{header}\n{mp.content}"
                parts.append(Part(text=content))
            elif mp.role == MessageRole.SYSTEM:
                content = f"[System Message]\n{mp.content}"
                parts.append(Part(text=content))
            elif mp.role == MessageRole.METHOD:
                content = f"[Function Call {mp.call.name}: Respons]e]\n{mp.content}"
                parts.append(Part(text=content))
            else:
                raise ValueError(f"Unknown MessageRole: {mp.role}")
        return parts

    def _convert_response_to_dc(
        self,
        response: genai_types.GenerateContentResponse,
        source: MessagePart | None = None,
    ) -> list[MessagePart]:
        """Convert Gemini API response to custom MessagePart objects.

        Args:
            response (genai_types.GenerateContentResponse): The response from the Gemini API.
            source (MessagePart | None): The original message part that triggered the response.

        Returns:
            list[MessagePart]: List of custom message parts.
        """
        message_parts: list[MessagePart] = []
        for part in response.candidates[0].content.parts:
            if not part.text:
                continue
            if source and source.discord:
                discord_context = source.discord
            else:
                discord_context = None
            message_part = MessagePart(
                role=MessageRole.LLM,
                content=part.text,
                destination=MessageRole.USER,
                discord=discord_context,
            )
            message_parts.append(message_part)
        return message_parts

    def _generate_config(self) -> genai_types.GenerateContentConfig:
        """Generate the configuration for content generation based on GeminiLLMConfig.

        Returns:
            genai_types.GenerateContentConfig: The configuration for content generation.
        """
        tools = None
        # No tool use currently implemented
        
        # Prompt
        if self.prompt:
            prompt = self.prompt
        elif self.config.prompt:
            prompt = self.config.prompt
        else:
            prompt = self.global_config.prompt

        config = genai_types.GenerateContentConfig(
            temperature=self.config.temperature, top_p=self.config.top_p, tools=tools, system_instruction=prompt
        )
        return config
