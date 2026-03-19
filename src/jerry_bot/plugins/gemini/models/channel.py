"""Conversation context models for Gemini plugin."""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Union

from .database import ChannelRecord


@dataclass(frozen=True, slots=True)
class Channel:
    """Dataclass representing a channel's configuration and state within the Gemini plugin."""

    channel_id: int
    guild_id: int

    prompt: Optional[str] = None
    is_ephemeral: bool = False
    override_system_prompt: bool = False
    mention_mode: bool = False

    @classmethod
    def from_record(cls, record: ChannelRecord) -> "Channel":
        """Create a Channel instance from a ChannelRecord database record."""

        return cls(
            channel_id=record.channel_id,
            guild_id=record.guild_id,
            prompt=record.prompt,
            is_ephemeral=False,
            override_system_prompt=record.override_system_prompt,
            mention_mode=record.mention_mode,
        )

    @classmethod
    def from_ephemeral_context(
        cls,
        channel_id: int,
        guild_id: int,
        override_system_prompt: bool = False,
    ) -> "Channel":
        """Create a Channel instance for an ephemeral conversation."""
        return cls(
            channel_id=channel_id,
            guild_id=guild_id,
            is_ephemeral=True,
            override_system_prompt=override_system_prompt,
        )
