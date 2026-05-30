"""Discord Modal for LLM Profile Creation"""

import discord
from discord import ui
from enum import Enum
from typing import Coroutine, Callable

from ..core import UIService
from ..constants import UI_PLUGIN_NAME

class LLMProfileModal(ui.Modal):
    """Modal for creating a new LLM profile for a Discord channel."""

    class ResponseType(Enum):
        """Enum to represent the type of response from the modal."""

        SAVE = "save"
        CANCEL = "cancel"

    def __init__(
        self,
        ui_service: UIService,
        channel_id: int,
        submit_callback: Callable[[discord.Interaction, dict], Coroutine],
        llm_profile_id: int | None = None,
    ):
        """Initialize the modal with necessary services and callbacks.

        Args:
            ui_service (UIService): The UI service to interact with profile data.
            channel_id (int): The ID of the Discord channel for which the profile is being created.
            llm_profile_id (int | None): The ID of the existing LLM profile, if updating. If None, a new profile will be created.
            submit_callback (Callable[[discord.Interaction, dict], Coroutine]): A callback function to handle the submission of the modal, which takes the interaction and a dictionary of the submitted data.
        """
        super().__init__(title=f"{UI_PLUGIN_NAME} Create LLM Profile")
        self.ui_service = ui_service
        self.channel_id = channel_id
        self.llm_profile_id = llm_profile_id
        self.submit_callback = submit_callback

    async def show(self, interaction: discord.Interaction):
        """Show the modal to the user."""
        llm_profile = await self.ui_service.get_llm_profile(self.channel_id, self.llm_profile_id) if self.llm_profile_id else None
    
        # Provider as a select
        providers = self.ui_service.get_providers()
        default_provider = self.ui_service.get_default_provider()
        provider_options = [
            discord.SelectOption(
                label=self.ui_service.get_provider(provider).friendly_name,
                value=provider,
                description=f"Use the {provider} provider",
                default=(llm_profile.provider_name == provider) if llm_profile else (provider == default_provider.name),
            )
            for provider in providers
        ]

        self.provider_select = ui.Select(
            options=provider_options,
            placeholder="Select a provider...",
            required=True,
            min_values=1,
            max_values=1,
        )
        self.add_item(
            ui.Label(
                component=self.provider_select,
                text="Provider",
                description="The AI provider to use for this profile.",
            )
        )
    
        # Model Name
        self.model_name_input = ui.TextInput(
            style=discord.TextStyle.short,
            required=True,
            placeholder="e.g., gpt-4, claude-3-opus",
            default=llm_profile.model_name if llm_profile else "",
        )
        self.add_item(
            ui.Label(
                component=self.model_name_input,
                text="Model Name",
                description="The name of the model to use for this profile. Note that this varies by provider.",
            )
        )

        # Temperature
        self.temperature_input = ui.TextInput(
            style=discord.TextStyle.short,
            required=False,
            placeholder="0.0 to 2.0 (leave blank for default)",
            default=str(llm_profile.temperature) if llm_profile and llm_profile.temperature is not None else "",
        )
        self.add_item(
            ui.Label(
                component=self.temperature_input,
                text="Temperature",
                description="Controls randomness: higher values = more creative.",
            )
        )

        # Top P
        self.top_p_input = ui.TextInput(
            style=discord.TextStyle.short,
            required=False,
            placeholder="0.0 to 1.0 (leave blank for default)",
            default=str(llm_profile.top_p) if llm_profile and llm_profile.top_p is not None else "",
        )

        self.add_item(
            ui.Label(
                component=self.top_p_input,
                text="Top P",
                description="Controls diversity via nucleus sampling.",
            )
        )

        # Top K
        self.top_k_input = ui.TextInput(
            style=discord.TextStyle.short,
            required=False,
            placeholder="e.g., 40 (leave blank for default)",
            default=str(llm_profile.top_k) if llm_profile and llm_profile.top_k is not None else "",
        )
        self.add_item(
            ui.Label(
                component=self.top_k_input,
                text="Top K",
                description="Limits token selection to top K options.",
            )
        )
        
        await interaction.response.send_modal(self)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        model_name = self.model_name_input.value
        provider_name = (
            self.provider_select.values[0] if self.provider_select.values else None
        )

        # Parse optional numeric fields
        temperature = None
        top_p = None
        top_k = None

        if self.temperature_input.value:
            try:
                temperature = float(self.temperature_input.value)
            except ValueError:
                pass

        if self.top_p_input.value:
            try:
                top_p = float(self.top_p_input.value)
            except ValueError:
                pass

        if self.top_k_input.value:
            try:
                top_k = int(self.top_k_input.value)
            except ValueError:
                pass
            
        llm_profile = await self.ui_service.get_llm_profile(self.channel_id, self.llm_profile_id) if self.llm_profile_id else None
        llm_profile = llm_profile or (self.ui_service.get_provider(provider_name).default_llm_profile if provider_name else None)
        if llm_profile:
            provider_name = provider_name or llm_profile.provider_name
            model_name = model_name or llm_profile.model_name
            temperature = temperature if temperature is not None else llm_profile.temperature
            top_p = top_p if top_p is not None else llm_profile.top_p
            top_k = top_k if top_k is not None else llm_profile.top_k

        commit_data = {
            "provider_name": provider_name,
            "model_name": model_name,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
        }

        await self.submit_callback(interaction, commit_data)
