"""Configuration model for the text-to-speech plugin."""

from pathlib import Path

from pydantic import BaseModel, Field

from .enums import PrefixControlDirective


class TTSServiceConfig(BaseModel):
    """Configuration model for the text-to-speech service command."""

    use: bool = Field(
        default=True,
        description="Whether to run the jerry-bot-tts service command. If False, the plugin will not attempt to run the TTS service.",
    )
    command: str = Field(..., description="The command to run jerry-bot-tts service.")
    args: list[str] = Field(
        default_factory=list,
        description="A list of arguments to pass to the TTS service command.",
    )
    cwd: Path | None = Field(
        default=None,
        description="The working directory from which to run the TTS service command, or None to use the plugin's directory.",
    )


class TTSVoiceConfig(BaseModel):
    """Configuration model for the text-to-speech voice settings."""

    name: str = Field(..., description="The name of the voice configuration.")

    voice: str = Field(
        ..., description="The voice to use for text-to-speech synthesis."
    )
    sample_rate: int = Field(
        ..., description="The sample rate for the generated audio."
    )
    speed: float = Field(..., description="The speed of the generated speech.")
    lang_code: str = Field(
        ..., description="The language code for the TTS voice configuration."
    )
    default: bool = Field(
        default=False, description="Whether this voice configuration is the default."
    )

class TTSPluginConfig(BaseModel):
    """Configuration model for the text-to-speech plugin."""

    enabled: bool = Field(
        default=False, description="Whether the Text-to-Speech plugin is enabled."
    )
    socket_path: Path = Field(
        ...,
        description="The path to the socket file used for communication with the TTS service.",
    )
    output_dir: Path = Field(
        ..., description="The directory where generated audio files will be saved."
    )
    max_concurrent_requests: int = Field(
        default=5,
        description="The maximum number of concurrent TTS requests allowed (defaults to 5).",
    )
    user_timeout: float = Field(
        default=600.0,
        description="Seconds after the last request before the voice client and input system are disconnected and cleaned up (defaults to 600).",
    )

    service: TTSServiceConfig = Field(
        ..., description="The configuration for the TTS service command."
    )

    voices: list[TTSVoiceConfig] = Field(
        default_factory=list,
        description="A list of available voice configurations for text-to-speech synthesis.",
    )

    normalize_rules: dict[str, str] = Field(
        default_factory=dict,
        description="A dict of input rules where keyss are regex patterns and values are replacement strings.",
    )
    control_rules: dict[str, PrefixControlDirective] = Field(
        default_factory=dict,
        description="A dict of control rules where keys are regex patterns and values are control directives.",
    )


    @property
    def default_voice(self) -> TTSVoiceConfig | None:
        """Get the default voice configuration.

        Returns:
            TTSVoiceConfig | None: The default voice configuration, or None if no default is set.
        """
        for voice in self.voices:
            if voice.default:
                return voice
        return None