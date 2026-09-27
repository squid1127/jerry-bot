"""Configuration model for the TTS plugin."""

from pathlib import Path
from typing import Self

import regex as re
from pydantic import BaseModel, Field, model_validator

from .enums import TTSControlSignal


class TTSServiceConfig(BaseModel):
    """Configuration model for the TTS service command."""

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


class TTSPathConfig(BaseModel):
    """Configuration model for paths related to the TTS system"""

    socket: Path = Field(
        ...,
        description="The path to the socket file used for communication with the TTS service.",
    )
    audio: Path = Field(
        ..., description="The directory where generated audio files are stored"
    )
    soundboard: Path | None = Field(
        None, description="The directory where soundboard files are stored, if enabled"
    )
    relative_to_plugin: bool = Field(
        default=True,
        description="Whether the output_dir is relative to the plugin's directory (True) or the cwd (False).",
    )
    clean_audio_dir: bool = Field(
        default=True,
        description="Whether to clean the audio directory on startup and periodically. If True, all files in the output_dir will erased regularly.",
    )


class TTSVoiceConfig(BaseModel):
    """Configuration model for the TTS voice settings."""

    name: str = Field(..., description="The name of the voice configuration.")

    voice: str = Field(..., description="The voice to use for TTS synthesis.")
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


class TTSRegexRule(BaseModel):
    """Base model for regex-based rules"""

    pattern: str = Field(
        ..., description="The regex pattern to match in the input text."
    )

    case_sensitive: bool = Field(
        default=False,
        description="Whether the regex pattern matching should be case-sensitive.",
    )

    @model_validator(mode="after")
    def validate_re(self) -> Self:
        """Attempt to compile this model's pattern"""
        try:
            re.compile(self.pattern, (re.IGNORECASE if not self.case_sensitive else 0))
        except re.error as e:
            raise ValueError(f"Invalid regex provided: {self.pattern}") from e
        return self


class TTSNormalizeRuleConfig(TTSRegexRule):
    """Configuration model for normalization rules."""

    replacement: str = Field(
        ..., description="The replacement string for the matched pattern."
    )


class TTSControlSignalRule(TTSRegexRule):
    """Configuration model for the playback control signals rule."""

    signal: TTSControlSignal = Field(
        ..., description="The action to execute when the pattern is matched."
    )


class TTSSoundboardRule(TTSRegexRule):
    """Configuration model for soundboard activation rules."""

    path: str = Field(
        ...,
        description="Path of the playback file relative to the soundboard directory.",
    )


class TTSTextProcessing(BaseModel):
    """Configuration model for the text processing system."""

    debug: bool = Field(
        False, description="Enable debug mode, which replies with processed text"
    )
    normalize_rules: list[TTSNormalizeRuleConfig] = Field(
        default_factory=list,
        description="A list of normalization rules for processing input text.",
    )
    control_rules: list[TTSControlSignalRule] = Field(
        default_factory=list,
        description="A list of control rules for performing commands when matched",
    )
    soundboard_rules: list[TTSSoundboardRule] = Field(
        default_factory=list,
        description="A list of soundboard rules for playing set files when matched",
    )


class TTSPluginConfig(BaseModel):
    """Configuration model for the TTS plugin."""

    enabled: bool = Field(
        default=False, description="Whether the TTS plugin is enabled."
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
    text: TTSTextProcessing = Field(
        ..., description="The configuration for the text processing system."
    )
    path: TTSPathConfig = Field(
        ..., description="Paths associated with the TTS plugin."
    )

    voices: list[TTSVoiceConfig] = Field(
        default_factory=list,
        description="A list of available voice configurations for TTS synthesis.",
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
