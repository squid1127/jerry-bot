"""Conversation context models for Gemini plugin."""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Union
import discord

@dataclass(frozen=True, slots=True)
class ChannelContext:
    """Context information for a specific channel."""

    channel: discord.TextChannel
    guild: discord.Guild