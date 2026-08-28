"""Listener and user input management for the TTS plugin."""

from logging import Logger

import discord

from .models.config import TTSPluginConfig, TTSVoiceConfig
from .models.exceptions import TTSError
from .models.request import TTSRequest
from .socket import TTSSocketClient
from .voice import TTSVoiceClient


async def reaction(message: discord.Message, emoji: str):
    """Add a reaction to a message and drop any exceptions."""
    try:
        await message.add_reaction(emoji)
    except (discord.HTTPException, discord.Forbidden):
        pass


class TTSListener:
    """A class that listens for a user's input in a specific channel and manages TTS requests for that user."""

    def __init__(
        self,
        member: discord.Member,
        listen_channel: discord.TextChannel,
        voice_config: TTSVoiceConfig,
        config: TTSPluginConfig,
        voice_client: TTSVoiceClient,
        socket_client: TTSSocketClient,
        logger: Logger,
    ):
        """
        Initialize the TTSListener.

        Args:
            member (discord.Member): The Discord member who is listening.
            listen_channel (discord.TextChannel): The channel where the listener is active.
            voice_config (TTSVoiceConfig): The voice configuration for the TTS.
            config (TTSPluginConfig): The plugin configuration.
            voice_client (TTSVoiceClient): The voice client used for TTS playback.
            socket_client (TTSSocketClient): The socket client used for TTS requests.
            logger (Logger): The logger for logging events and errors.
        """
        self.member = member
        self.voice_config = voice_config
        self.listen_channel = listen_channel
        self.voice_client = voice_client
        self.socket_client = socket_client
        self.config = config
        self.logger = logger

    async def handle_message(self, message: discord.Message):
        """
        Handle incoming messages and enqueue TTS requests if applicable.

        Args:
            message (discord.Message): The incoming Discord message.
        """
        if message.channel != self.listen_channel:
            return  # Ignore messages from other channels

        if message.author != self.member:
            return  # Ignore messages from other users

        if not message.content.strip():
            return  # Ignore empty messages

        await self._generate_for_message(message)

    async def _generate_for_message(self, message: discord.Message):
        """
        Generate TTS for the given message and enqueue it for playback.

        Args:
            message (discord.Message): The incoming Discord message.
        """
        try:
            # Generate TTS audio file using the socket client
            response = await self.socket_client.generate_tts(
                TTSRequest.from_voice_config(
                    text=message.content, voice_config=self.voice_config
                )
            )

            if response.filename:
                if not (self.config.output_dir / response.filename).exists():
                    raise FileNotFoundError(
                        f"Generated audio file not found: {response.filename}"
                    )
                # Enqueue the generated audio file for playback
                self.voice_client.enqueue(
                    self.member, self.config.output_dir / response.filename
                )
            else:
                raise ValueError("TTS response failed")

        except TTSError as e:
            self.logger.error(
                f"Error generating TTS for message '{message.content}': {e}"
            )
            await reaction(message, "❌")  # Indicate failure with a reaction
