"""Interaction-based editor for Gemini model configuration within a channel."""

from discord import ui
import discord

from ..core.manager import ConversationManager
from ..models import Channel, Model
from .utils import send_ephemeral_response


class ModelConfigEditor:
    """UI for editing model configuration for a specific channel."""

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

        self.view = ui.Modal(title="Model Configuration")

    async def get_channel(self) -> Channel | None:
        """Get the Channel model for the current interaction's channel, or return None if it doesn't exist."""
        channel = await self.conversation_manager.get_channel(self.channel.id)
        return channel

    async def get_current_model(self, channel: Channel) -> Model | None:
        """Get the current model configuration for the channel."""
        if channel.model:
            return Model.from_database_entry(await channel.model)

        # Fallback to provider's default model
        provider = self.conversation_manager.provider_manager.get_provider(
            channel.provider_name
        )
        if provider:
            return provider.default_model

        return None

    async def save_model(
        self,
        model_name: str,
        temperature: float | None,
        max_tokens: int | None,
        top_p: float | None,
        top_k: int | None,
    ) -> Model:
        """Create and save the model configuration."""
        model = Model(
            name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
        )

        await self.conversation_manager.update_channel_model(
            channel_id=self.channel.id,
            model=model,
        )

        return model

    async def start(self):
        """Start the model configuration editor by displaying the modal to the user."""
        channel = await self.get_channel()

        if channel is None:
            await send_ephemeral_response(
                self.interaction,
                error="Gemini is not enabled for this channel. Use `/gemini-cfg enable` first.",
            )
            return

        current_model = await self.get_current_model(channel)
        provider = self.conversation_manager.provider_manager.get_provider(
            channel.provider_name
        )

        self.view = ui.Modal(title=f"Model Config: #{self.channel.name}")
        self.view.on_submit = self.on_submit

        # Model Name input
        default_model_name = ""
        if current_model:
            default_model_name = current_model.name
        elif provider:
            default_model_name = provider.default_model.name

        self.ui_model = ui.TextInput(
            placeholder=(
                f"e.g., {default_model_name}"
                if default_model_name
                else "e.g., llama3.1:8b"
            ),
            default=default_model_name,
            required=True,
            style=discord.TextStyle.short,
        )
        self.view.add_item(
            ui.Label(
                text="Model Name",
                component=self.ui_model,
                description="The name of the model to use (provider-specific).",
            )
        )

        # Temperature
        self.ui_temperature = ui.TextInput(
            placeholder="0.0 - 2.0 (e.g., 0.7)",
            default=(
                str(current_model.temperature)
                if current_model and current_model.temperature is not None
                else ""
            ),
            required=False,
            style=discord.TextStyle.short,
        )
        self.view.add_item(
            ui.Label(
                text="Temperature",
                component=self.ui_temperature,
                description="Controls randomness. Lower = more focused, Higher = more creative. Leave empty for default.",
            )
        )

        # Max Tokens
        self.ui_max_tokens = ui.TextInput(
            placeholder="e.g., 2048",
            default=(
                str(current_model.max_tokens)
                if current_model and current_model.max_tokens is not None
                else ""
            ),
            required=False,
            style=discord.TextStyle.short,
        )
        self.view.add_item(
            ui.Label(
                text="Max Tokens",
                component=self.ui_max_tokens,
                description="Maximum tokens to generate. Leave empty for default.",
            )
        )

        # Top P
        self.ui_top_p = ui.TextInput(
            placeholder="0.0 - 1.0 (e.g., 0.9)",
            default=(
                str(current_model.top_p)
                if current_model and current_model.top_p is not None
                else ""
            ),
            required=False,
            style=discord.TextStyle.short,
        )
        self.view.add_item(
            ui.Label(
                text="Top P",
                component=self.ui_top_p,
                description="Nucleus sampling threshold. Leave empty for default.",
            )
        )

        # Top K
        self.ui_top_k = ui.TextInput(
            placeholder="e.g., 40",
            default=(
                str(current_model.top_k)
                if current_model and current_model.top_k is not None
                else ""
            ),
            required=False,
            style=discord.TextStyle.short,
        )
        self.view.add_item(
            ui.Label(
                text="Top K",
                component=self.ui_top_k,
                description="Limits vocabulary to top K tokens. Leave empty for default.",
            )
        )

        await self.interaction.response.send_modal(self.view)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle submission of the model configuration form."""
        model_name = self.ui_model.value.strip()

        if not model_name:
            await send_ephemeral_response(
                interaction, error="Model name cannot be empty."
            )
            return

        # Parse and validate inputs
        try:
            temperature = (
                float(self.ui_temperature.value)
                if self.ui_temperature.value.strip()
                else None
            )
            if temperature is not None and (temperature < 0 or temperature > 2):
                await send_ephemeral_response(
                    interaction, error="Temperature must be between 0 and 2."
                )
                return
        except ValueError:
            await send_ephemeral_response(
                interaction, error="Temperature must be a valid number."
            )
            return

        try:
            max_tokens = (
                int(self.ui_max_tokens.value)
                if self.ui_max_tokens.value.strip()
                else None
            )
            if max_tokens is not None and max_tokens <= 0:
                await send_ephemeral_response(
                    interaction, error="Max tokens must be a positive integer."
                )
                return
        except ValueError:
            await send_ephemeral_response(
                interaction, error="Max tokens must be a valid integer."
            )
            return

        try:
            top_p = float(self.ui_top_p.value) if self.ui_top_p.value.strip() else None
            if top_p is not None and (top_p < 0 or top_p > 1):
                await send_ephemeral_response(
                    interaction, error="Top P must be between 0 and 1."
                )
                return
        except ValueError:
            await send_ephemeral_response(
                interaction, error="Top P must be a valid number."
            )
            return

        try:
            top_k = int(self.ui_top_k.value) if self.ui_top_k.value.strip() else None
            if top_k is not None and top_k <= 0:
                await send_ephemeral_response(
                    interaction, error="Top K must be a positive integer."
                )
                return
        except ValueError:
            await send_ephemeral_response(
                interaction, error="Top K must be a valid integer."
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            await self.save_model(
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                top_k=top_k,
            )
        except Exception as e:
            await send_ephemeral_response(
                interaction,
                error="An error occurred while saving the model configuration. Please try again later.",
            )
            self.conversation_manager.logger.error(
                f"Error saving model configuration for channel {interaction.channel_id}: {e}"
            )
            return

        await send_ephemeral_response(
            interaction, success="Model configuration saved successfully!"
        )
