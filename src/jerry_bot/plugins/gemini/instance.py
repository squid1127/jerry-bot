"""Chatbot instances for JerryGemini"""

import logging
import discord
from .gemini import GeminiLLM
from .models.config import InstanceConfig
from .models.gemini import MessagePart, MessageRole


class JerryGeminiInstance:
    """A JerryGemini chatbot instance, representing a Discord channel that listens for messages."""

    def __init__(self, config: InstanceConfig, logger: logging.Logger):
        """
        Initialize the JerryGeminiInstance.

        Args:
            config (InstanceConfig): The configuration for this Gemini instance.
            logger (logging.Logger): Logger instance for logging.
        """
        self.config = config
        self.logger = logger

        if self.config.prompt:
            prompt = self.config.prompt + "\n" + (self.config.prompt_extra or "")
        else:
            prompt = (
                self.config.global_config.prompt
                + "\n"
                + (self.config.prompt_extra or "")
            )

        self.llm: GeminiLLM = GeminiLLM(
            config.global_config, config.llm_config, prompt=prompt
        )

        self.logger.info(
            f"Initialized JerryGeminiInstance for channel {self.config.channel_id}"
        )

    async def process_message(self, message: MessagePart) -> None:
        """Process one incoming message, based on destination.

        Args:
            message (MessagePart): The incoming message to process.
        """
        return await self.process_messages([message])

    async def process_messages(self, messages: list[MessagePart]) -> None:
        """Process an incoming message, based on destination. This method will either send all parts simultaneously or process them sequentially, depending on their destinations.

        Args:
            messages (list[MessagePart]): The incoming messages to process.
        """

        try:

            # Determine if destination types are mixed
            destinations = {msg.destination for msg in messages}
            if len(destinations) > 1:
                # Mixed destinations: process sequentially
                for msg in messages:
                    if msg.destination == MessageRole.LLM:
                        responses = await self._send_messages_model(msg)
                        # Recursively process LLM responses
                        await self.process_messages(responses)

                    elif msg.destination == MessageRole.USER:
                        await self._send_user_response(msg)

            else:
                # Single destination: process all at once
                destination = destinations.pop()
                if destination == MessageRole.LLM:
                    responses = await self._send_messages_model(messages)
                    # Recursively process LLM responses
                    await self.process_messages(responses)

                # User messages are always sent individually
                elif destination == MessageRole.USER:
                    for msg in messages:
                        await self._send_user_response(msg)

        except Exception as e:
            from traceback import format_exc

            self.logger.error(
                f"Error processing messages in channel {self.config.channel_id}: {e}\n{format_exc()}"
            )

            # If discord user context is available, send error message
            context = messages[0].discord if messages else None
            if context:
                error_msg = MessagePart(
                    role=MessageRole.SYSTEM,
                    destination=MessageRole.USER,
                    discord=context,
                    embeds=[
                        {
                            "title": "Error",
                            "description": "An error occurred while processing your message. Please try again later.",
                            "color": 0xFF0000,
                        }
                    ],
                )
                try:
                    await self._send_user_response(error_msg)
                except Exception as e2:
                    self.logger.warning(
                        f"Failed to send error message to Discord: {e2}"
                    )

    async def _send_messages_model(
        self, messages: list[MessagePart]
    ) -> list[MessagePart]:
        """Send messages to the Gemini LLM and get the response. Requires a list of messages.

        Args:
            messages (list[MessagePart]): The messages to send.
        """
        response = await self.llm.send_chat(messages)
        return response

    async def _send_user_response(self, message: MessagePart) -> None:
        """Send a response back to the user via Discord.

        Args:
            message (MessagePart): The message to send back to the user.
        """
        channel = message.discord.channel
        if channel:
            if message.embeds:
                embeds = [discord.Embed.from_dict(embed) for embed in message.embeds]
                parts = self.auto_split(message.content or "")
                part = parts.pop(0) if parts else ""
                await channel.send(content=part, embeds=embeds)
                for part in parts:
                    await channel.send(content=part)
            else:
                # Auto-split if message exceeds Discord limits
                parts = self.auto_split(message.content or "")
                for part in parts:
                    await channel.send(content=part)
            self.logger.info(
                f"Sent message to Discord channel {channel.id}: {message.content if message.content else '[Empty Message]'}"
            )
        else:
            self.logger.error("No Discord channel found to send the message.")

    def auto_split(self, content: str, max_length: int = 1990) -> list[str]:
        """Automatically split a message into parts if it exceeds the character limit.

        Args:
            content (str): The content to split.
            max_length (int, optional): The maximum length of each part. Defaults to 1990.

        Returns:
            list[str]: A list of message parts, each under the character limit.
        """

        if len(content) <= max_length:
            return [content]

        parts = []
        while len(content) > max_length:
            split_index = content.rfind("\n", 0, max_length)
            if split_index == -1:
                split_index = max_length
            parts.append(content[:split_index].strip())
            content = content[split_index:].strip()
        if content:
            parts.append(content)
        return parts
