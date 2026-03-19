"""Input processor for converting Discord messages into Gemini Message objects for processing by the conversation engine."""

from dataclasses import dataclass
import discord

from ..models import Message, UserMessage, Participant


@dataclass(frozen=True, slots=True)
class OutputContext:
    """Dataclass representing the output context for a conversation, including channel and guild objects."""

    channel: discord.TextChannel
    guild: discord.Guild

class InputProcessor:
    """Processor for converting Discord messages into Gemini Message objects."""

    def process(self, message: discord.Message) -> UserMessage:
        """Convert a Discord message into a UserMessage."""
        if message.guild is None or not isinstance(message.channel, discord.TextChannel):
            raise ValueError("Message must be from a guild channel.")
        
        output_context = OutputContext(
            channel=message.channel,
            guild=message.guild,
        )
        user_message = UserMessage(
            user=Participant(
                id=message.author.id,
                username=message.author.name,
                display_name=message.author.display_name,
            ),
            content=message.content,
            raw_content=message.content,
        )
        return user_message