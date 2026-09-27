"""Listener and user input management for the TTS plugin."""

from logging import Logger
from pathlib import Path

import discord

from .models.config import (
    TTSControlSignalRule,
    TTSPluginConfig,
    TTSSoundboardRule,
    TTSVoiceConfig,
)
from .models.enums import TTSControlSignal
from .models.exceptions import TTSError, TTSGenerationError, TTSVoiceError
from .models.request import TTSRequest
from .socket import TTSSocketClient
from .text_processor import TextProcessor
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
        owner: discord.Member,
        target: discord.Member,
        listen_channel: discord.TextChannel,
        voice_config: TTSVoiceConfig,
        config: TTSPluginConfig,
        voice_client: TTSVoiceClient,
        socket_client: TTSSocketClient,
        logger: Logger,
        base_path: Path,
    ):
        """
        Initialize the TTSListener.

        Args:
            owner (discord.Member): The owner of the listener, who can manage it.
            target (discord.Member): The Discord member who is listening.
            listen_channel (discord.TextChannel): The channel where the listener is active.
            voice_config (TTSVoiceConfig): The voice configuration for the TTS.
            config (TTSPluginConfig): The plugin configuration.
            voice_client (TTSVoiceClient): The voice client used for TTS playback.
            socket_client (TTSSocketClient): The socket client used for TTS requests.
            logger (Logger): The logger for logging events and errors.
            base_path (Path): The base path compared to the path in the config if output_dir_relative_to_plugin is True, otherwise the base path is the cwd.
        """
        self._target = target
        self._owner = owner
        self.voice_config = voice_config
        self._listen_channel = listen_channel
        self.voice_client = voice_client
        self.socket_client = socket_client
        self.config = config
        self.logger = logger
        self.base_path = base_path
        self.text_processor = TextProcessor(config)

    async def handle_message(self, message: discord.Message):
        """
        Handle incoming messages and enqueue TTS requests if applicable.

        Args:
            message (discord.Message): The incoming Discord message.
        """
        if message.channel != self._listen_channel:
            return  # Ignore messages from other channels

        if message.author != self._target:
            return  # Ignore messages from other users

        if not message.content.strip():
            return  # Ignore empty messages

        if self._owner.voice is None or self._owner.voice.channel is None:
            return  # Ignore if the owner is not in a voice channel

        await self._generate_for_message(message)

    async def _generate_for_message(self, message: discord.Message):
        """
        Generate TTS for the given message and enqueue it for playback.

        Args:
            message (discord.Message): The incoming Discord message.
        """
        raw_text = message.content
        text = self.text_processor.normalize(raw_text)
        tokenized = self.text_processor.tokenize(text)

        next_is_fast = False
        next_is_raw = False
        for token in tokenized:
            if self.config.text.debug and (str(token)):
                await message.reply(str(token))
            
            if isinstance(token, str):
                if not token.strip():
                    continue
                
                await self._handle_generate_tts(
                    raw_text if next_is_raw else token, message, int(next_is_fast) + 1
                )
                next_is_fast = False
                next_is_raw = False

            elif isinstance(token, TTSSoundboardRule):
                if self.soundboard_path is None:
                    continue
                try:
                    self._add_playback(self.soundboard_path / token.path, message)
                except TTSVoiceError:
                    self.logger.exception(
                        f"Error playing soundboard for message id {message.id}"
                    )
                    await reaction(message, "❌")  # Indicate failure with a reaction

            elif isinstance(token, TTSControlSignalRule):
                if token.signal == TTSControlSignal.FAST:
                    next_is_fast = True
                elif token.signal == TTSControlSignal.RAW:
                    next_is_raw = True
                elif token.signal == TTSControlSignal.STOP:
                    await self.voice_client.stop()
                elif token.signal == TTSControlSignal.SKIP:
                    await self.voice_client.skip()

    async def _handle_generate_tts(
        self, text: str, message: discord.Message, speed_multiplier: float
    ):

        try:
            # Generate TTS audio file using the socket client
            response = await self.socket_client.generate_tts(
                TTSRequest.from_voice_config(
                    text=text,
                    voice_config=self.voice_config,
                    speed_multiplier=speed_multiplier,
                )
            )

            if response.filename:

                self._add_playback(self.path / response.filename, message)
            else:
                raise TTSGenerationError("TTS response failed")

        except TTSError:
            self.logger.exception(
                f"Error generating TTS for message id {message.id}"
            )
            await reaction(message, "❌")  # Indicate failure with a reaction

    def _add_playback(self, path: Path, message: discord.Message):
        if not path.exists():
            raise TTSVoiceError(f"File to play does not exist: {path}")
        self.voice_client.enqueue(
            self._owner,
            path,
            lambda e: self._handle_generation_error(message, e),
        )

    async def _handle_generation_error(
        self, message: discord.Message, error: Exception
    ):
        """
        Handle errors that occur during TTS generation.

        Args:
            message (discord.Message): The original Discord message.
            error (Exception): The exception that occurred.
        """
        self.logger.exception(
            f"Error generating TTS for message '{message.content}': {error}"
        )
        await reaction(message, "❌")  # Indicate failure with a reaction

    def update_listen_channel(self, channel: discord.TextChannel):
        self._listen_channel = channel

    @property
    def path(self) -> Path:
        """Get the audio path."""
        return (
            self.base_path / self.config.path.audio
            if self.config.path.relative_to_plugin
            else self.config.path.audio
        )

    @property
    def soundboard_path(self) -> Path | None:
        """Get the soundboard audio path."""
        if self.config.path.soundboard is None:
            return
        elif self.config.path.relative_to_plugin:
            return self.base_path / self.config.path.soundboard
        else:
            return self.config.path.soundboard

    @property
    def owner(self) -> discord.Member:
        """Returns the owner of this listener"""
        return self._owner

    @property
    def target(self) -> discord.Member:
        """Returns the member who this listener is listening to"""
        return self._target

    @property
    def guild(self) -> discord.Guild:
        """Returns the guild this listener is in"""
        return self._listen_channel.guild

    @property
    def listen_channel(self) -> discord.TextChannel:
        """Returns the channel this listener is in"""
        return self._listen_channel
