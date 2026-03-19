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

    async def process(self, message: discord.Message) -> UserMessage:
        """Convert a Discord message into a UserMessage."""
        if message.guild is None or not isinstance(message.channel, discord.TextChannel):
            raise ValueError("Message must be from a guild channel.")
        
        display_name = message.author.display_name
        if message.author.bot:
            display_name += " [BOT]"
        
        user_message = UserMessage(
            user=Participant(
                id=message.author.id,
                username=message.author.name,
                display_name=display_name,
            ),
            content=await self.generate_content(message),
            raw_content=message.content,
        )
        return user_message
    
    async def generate_content(self, message: discord.Message) -> str:
        """Generate the content for a UserMessage from a Discord message."""
        content = ""
        if message.reference:
            try:
                referenced_message = await message.channel.fetch_message(message.reference.message_id or 0)
                content = f"[[In reply to: {referenced_message.author.display_name}:]]\n[Begin quoted message]\n{self._message_create_content(referenced_message)}\n[End quoted message]\n\n"
                
                
            except (discord.NotFound, discord.Forbidden):
                content = f"[In reply to: Message not found]\n"
                
        content += self._message_create_content(message)
        
        return content
    
    def _message_create_content(self, message: discord.Message) -> str:
        """Create the content for a UserMessage from a Discord message."""
        content = message.content or "[No text content]"
        if message.embeds:
            embed_descriptions = []
            for embed in message.embeds:
                description = f"[Embed{'' if not embed.title else f': {embed.title}'}]"
                if embed.description:
                    description += f"\n{embed.description}"
                if embed.author and embed.author.name:
                    description += f"\n[Author]\n{embed.author.name}"
                for field in embed.fields:
                    description += f"\n[Field: {field.name}]\n{field.value}"
                if embed.footer and embed.footer.text:
                    description += f"\n[Footer]\n{embed.footer.text}"
                if embed.image:
                    description += f"\n[Unsupported Image: {embed.image.url}]"
                embed_descriptions.append(description)
            content += "\n\n" + "\n".join(embed_descriptions)
        
        if message.stickers:
            sticker_descriptions = []
            for sticker in message.stickers:
                description = f"[Unsupported Sticker: {sticker.name} ({sticker.format})]"
                sticker_descriptions.append(description)
            content += "\n\n" + "\n".join(sticker_descriptions)
            
        if message.components:
            component_descriptions = []
            for component in message.components:
                description = f"[Unsupported Component: {component.type}]"
                component_descriptions.append(description)
            content += "\n\n" + "\n".join(component_descriptions)
        
        # Add attachments to the content
        if message.attachments:
            attachment_descriptions = []
            for attachment in message.attachments:
                description = f"[Unsupported Attachment: {attachment.filename} ({attachment.size} bytes)]"
                attachment_descriptions.append(description)
            content += "\n\n" + "\n".join(attachment_descriptions)
        return content