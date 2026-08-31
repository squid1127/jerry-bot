"""IO Models for the text-to-speech plugin."""

from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from .config import TTSVoiceConfig


class TTSRequest(BaseModel):
    """TTS request model"""

    uuid: str = Field(
        ...,
        description="UUID4 string for the request. This is used to uniquely identify the request and the generated audio file.",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    text: str = Field(
        ...,
        description="Text to convert to speech. This should be preprocessed to remove any unwanted characters or formatting.",
    )
    voice: str = Field(
        ...,
        description="Voice to use for TTS. Refer to the documentation for a list of supported voices.",
    )
    speed: float = Field(
        1.0,
        description="Speed of the generated speech.",
        examples=[1.0, 0.5, 2.0],
    )
    sample_rate: int = Field(
        24000,
        description="Sample rate of the generated audio. Note that this changes the playback speed/pitch of the audio. To sound normal, it should be 24000.",
        examples=[24000, 44100, 48000],
    )
    lang_code: str = Field(
        "a",
        description="Language code for the TTS pipeline. This is used to select the correct language for a given voice. The default is 'a', which is American English. Refer to the documentation for a list of supported language codes.",
        examples=["a", "b", "j", "e"],
    )

    @classmethod
    def from_json_bytes(cls, data: bytes) -> "TTSRequest":
        """Create a TTSRequest instance from JSON-encoded bytes

        Args:
            data (bytes): The JSON-encoded bytes representing the TTS request

        Returns:
            TTSRequest: The TTSRequest instance
        """
        try:
            return cls.model_validate_json(data)
        except ValidationError as e:
            raise ValueError(f"Invalid TTS request data: {e}") from e
        
    def to_json_bytes(self) -> bytes:
        """Convert the TTSRequest instance to JSON-encoded bytes

        Returns:
            bytes: The JSON-encoded bytes representing the TTS request
        """
        return self.model_dump_json().encode()
    
    @classmethod
    def from_voice_config(cls, text: str, voice_config: TTSVoiceConfig) -> "TTSRequest":
        """Create a TTSRequest instance from a TTSVoiceConfig.

        Args:
            text (str): The text to convert to speech.
            voice_config (TTSVoiceConfig): The voice configuration to use.

        Returns:
            TTSRequest: The TTSRequest instance.
        """
        return cls(
            uuid=str(uuid4()),
            text=text,
            voice=voice_config.voice,
            speed=voice_config.speed,
            sample_rate=voice_config.sample_rate,
            lang_code=voice_config.lang_code,
        )


class TTSResponse(BaseModel):
    """TTS response model"""

    type: str = Field(..., description="Type of the response", examples=["ack"])
    status: str = Field(
        ..., description="Status of the TTS request", examples=["success", "error"]
    )
    message: str = Field(
        ..., description="Message describing the result of the TTS request"
    )
    uuid: str | None = Field(
        None,
        description="UUID of the generated audio file, if applicable",
        examples=["123e4567-e89b-12d3-a456-426614174000", None],
    )
    filename: str | None = Field(
        None,
        description="Filename of the generated audio file, if applicable",
        examples=["123e4567-e89b-12d3-a456-426614174000.wav", None],
    )

    def to_json_bytes(self) -> bytes:
        """Convert the TTSResponse instance to JSON-encoded bytes

        Returns:
            bytes: The JSON-encoded bytes representing the TTS response
        """
        return self.model_dump_json().encode()

    @classmethod
    def from_json_bytes(cls, data: bytes) -> "TTSResponse":
        """Create a TTSResponse instance from JSON-encoded bytes

        Args:
            data (bytes): The JSON-encoded bytes representing the TTS response

        Returns:
            TTSResponse: The TTSResponse instance
        """
        try:
            return cls.model_validate_json(data)
        except ValidationError as e:
            raise ValueError(f"Invalid TTS response data: {e}") from e