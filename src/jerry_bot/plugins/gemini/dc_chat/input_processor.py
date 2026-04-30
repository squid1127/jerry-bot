"""Input processor for converting Discord messages into Gemini Message objects for processing by the conversation engine."""

from dataclasses import dataclass
from typing import Optional
import discord

from ..models import Message, UserMessage, Participant, Attachment, Embed


@dataclass(frozen=True, slots=True)
class OutputContext:
    """Dataclass representing the output context for a conversation, including channel and guild objects."""

    channel: discord.TextChannel
    guild: discord.Guild


class InputProcessor:
    """Processor for converting Discord messages into Gemini Message objects."""

    async def process(self, message: discord.Message) -> Optional[UserMessage]:
        """Convert a Discord message into a UserMessage."""
        if message.guild is None or not isinstance(
            message.channel, discord.TextChannel
        ):
            raise ValueError("Message must be from a guild channel.")

        display_name = message.author.display_name
        if message.author.bot:
            display_name += " [BOT]"

        content = message.content.strip() if message.content else None
        embeds = self._generate_embeds(message)
        attachments = await self._generate_attachments(message)

        if (
            not content
            and not embeds
            and not attachments
        ):
            return None

        user_message = UserMessage(
            user=Participant(
                id=message.author.id,
                username=message.author.name,
                display_name=display_name,
            ),
            content=content or None,
            embeds=embeds if embeds else None,
            attachments=attachments if attachments else None,
        )
        return user_message

    def _generate_embeds(self, message: discord.Message) -> list[Embed]:
        """Create Embed objects from a Discord message."""
        embeds = []
        for discord_embed in message.embeds:
            if discord_embed.type == "image":
                # Skip simple image embeds often auto-generated for link attachments/URLs
                # We could potentially handle them better if needed.
                continue

            fields = None
            if discord_embed.fields:
                fields = {
                    field.name: field.value
                    for field in discord_embed.fields
                    if field.name and field.value
                }

            embeds.append(
                Embed(
                    title=discord_embed.title,
                    description=discord_embed.description,
                    author=discord_embed.author.name if discord_embed.author else None,
                    fields=fields,
                    footer=discord_embed.footer.text if discord_embed.footer else None,
                )
            )
        return embeds

    async def _generate_attachments(self, message: discord.Message) -> list[Attachment]:
        """Create Attachment objects from a Discord message."""
        attachments = []
        for discord_attachment in message.attachments:
            try:
                # Need to read the content to put in Attachment model
                content = await discord_attachment.read()
                attachments.append(
                    Attachment(
                        filename=discord_attachment.filename,
                        content=content,
                        mime_type=discord_attachment.content_type,
                    )
                )
            except discord.HTTPException:
                pass
        return attachments
