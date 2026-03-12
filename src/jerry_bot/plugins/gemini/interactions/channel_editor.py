"""Interaction-based editor for Gemini channel configuration and management."""

from discord import ui
import discord

from ..core.manager import ConversationManager
from ..models import Channel
from .utils import send_ephemeral_response


class ChannelConfigEditor:
    """UI for editing Gemini channel configuration and managing conversations."""

    def __init__(
        self,
        conversation_manager: ConversationManager,
        interaction: discord.Interaction,
    ):
        if not isinstance(interaction.channel, discord.TextChannel):
            raise ValueError("Interaction must be associated with a text channel.")

        self.conversation_manager = conversation_manager
        self.interaction = interaction
        self.channel: discord.TextChannel = interaction.channel

        self.view = ui.Modal(title="Gemini Channel Editor")

    async def get_channel(self) -> Channel | None:
        """Get the Channel model for the current interaction's channel, or return None if it doesn't exist."""
        channel = await self.conversation_manager.get_channel(self.channel.id)

        return channel

    async def save_channel(
        self, provider_name: str, channel_prompt: str, override_system_prompt: bool
    ):
        """Save the channel configuration to the database, creating or updating the Channel model as needed."""
        channel = await self.get_channel()

        if channel is None:
            # Create new channel record
            channel = await self.conversation_manager.create_channel(
                channel_id=self.channel.id,
                guild_id=self.channel.guild.id,
                provider_name=provider_name,
                provider_overrides={},  # For now we don't have any provider-specific overrides in the UI, but this can be extended in the future
                prompt=channel_prompt,
                override_system_prompt=override_system_prompt,
            )
            return channel
        else:
            updated_channel = await self.conversation_manager.update_channel(
                channel_id=self.channel.id,
                provider_name=provider_name,
                provider_overrides=channel.provider_overrides,  # Preserve existing provider overrides since we don't edit them in the UI yet
                prompt=channel_prompt,
                override_system_prompt=override_system_prompt,
            )

            return updated_channel

    async def start(self):
        """Start the channel configuration editor by displaying the modal to the user and handling the submission."""
        channel = await self.get_channel()

        if channel is None:
            self.view = ui.Modal(title="New Gemini Channel")
        else:
            self.view = ui.Modal(title=f"Edit #{self.channel.name}")
        self.view.on_submit = self.on_submit

        # Fetch possible provider types
        providers = self.conversation_manager.provider_manager.providers
        selected_provider = channel.provider_name if channel else None
        provider_options = [
            discord.SelectOption(
                label=provider.friendly_name,
                value=provider.name,
                default=provider.name == selected_provider,
            )
            for provider in providers.values()
        ]

        # Provider Selection
        self.ui_provider = ui.Select(
            placeholder="Provider...",
            options=provider_options,
            required=True,
            max_values=1,
            min_values=1,
        )
        self.view.add_item(
            ui.Label(
                text="Provider",
                component=self.ui_provider,
                description="Select a LLM provider for this channel.",
            )
        )

        # Channel-specific prompt
        self.ui_channel_prompt = ui.TextInput(
            placeholder="Channel prompt...",
            default=channel.prompt if channel else "",
            required=False,
            style=discord.TextStyle.paragraph,
        )
        self.view.add_item(
            ui.Label(
                text="Channel Prompt",
                component=self.ui_channel_prompt,
                description="Add channel-specific instructions or context for the LLM. This supplements the global system prompt.",
            )
        )

        # Additional options
        options = [
            discord.SelectOption(
                label="Override system prompt",
                value="prompt_override",
                description="Check to exclude global prompt and use only the channel-specific prompt.",
                default=channel.override_system_prompt if channel else False,
            ),
        ]
        self.ui_options_select = ui.Select(
            placeholder="Options...",
            options=options,
            required=False,
            max_values=len(options),
            min_values=0,
        )
        self.view.add_item(
            ui.Label(
                text="Additional Options",
                component=self.ui_options_select,
                description="Configure additional channel-specific options.",
            )
        )

        await self.interaction.response.send_modal(self.view)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle submission of the channel configuration form."""
        
        if not isinstance(interaction.channel, discord.TextChannel) or not interaction.channel_id:
            await send_ephemeral_response(
                interaction, error="This interaction can only be used in text channels."
            )
            return

        selected_provider_name = self.ui_provider.values[0]
        channel_prompt = self.ui_channel_prompt.value
        override_system_prompt = "prompt_override" in self.ui_options_select.values
        
        current_channel_config = (await self.conversation_manager.get_channel(interaction.channel_id))

        await interaction.response.defer(thinking=True, ephemeral=True)
        
        hints: list[str] = []
        if current_channel_config and current_channel_config.provider_name != selected_provider_name:
            hints.append(f"Provider changed to {selected_provider_name}. Make sure to update model settings for this new provider!")
        if override_system_prompt:
            hints.append("System prompt will be overridden. Only the channel-specific prompt will be used.")
        if channel_prompt and len(channel_prompt) > 500:
            hints.append("Channel prompt is quite long. Consider shortening it for better performance and response times.")

        try:
            await self.save_channel(
                provider_name=selected_provider_name,
                channel_prompt=channel_prompt,
                override_system_prompt=override_system_prompt,
            )
        except Exception as e:
            await send_ephemeral_response(interaction, error="An error occurred while saving the channel configuration. Please try again later.")
            self.conversation_manager.logger.error(f"Error saving channel configuration for channel {interaction.channel_id}: {e}")
            return

        await send_ephemeral_response(interaction, success="Channel configuration saved successfully!" + ("\n\n**Hints**:\n- " + "\n- ".join(hints) if hints else ""))
