"""Discord Modal for Gemini Channel Configuration"""

import discord
from discord import ui
from enum import Enum
from typing import Coroutine, Callable

from ..core import UIService
from ..constants import UI_PLUGIN_NAME


class GeminiConfigModal(ui.Modal):
    """Modal for configuring Gemini plugin settings for a Discord channel."""

    class ResponseType(Enum):
        """Enum to represent the type of response from the modal."""

        SAVE = "save"
        CANCEL = "cancel"

    def __init__(
        self, ui_service: UIService, channel_id: int, submit_callback: Callable[[discord.Interaction, dict], Coroutine]
    ):
        """Initialize the modal with necessary services and callbacks.
        
        Args:
            ui_service (UIService): The UI service to interact with channel data.
            channel_id (int): The ID of the Discord channel being configured.
            submit_callback (Callable[[discord.Interaction, dict], Coroutine]): A callback function to handle the submission of the modal, which takes the interaction and a dictionary of the submitted data.
        """
        super().__init__(title=f"{UI_PLUGIN_NAME} Channel Configuration")
        self.ui_service = ui_service
        self.channel_id = channel_id
        self.submit_callback = submit_callback

    async def show(self, interaction: discord.Interaction):
        """Show the modal to the user."""
        channel = await self.ui_service.get_channel(self.channel_id, ignore_active=True)

        # Prompt
        self.prompt_input = ui.TextInput(
            style=discord.TextStyle.long,
            required=False,
            default=channel.prompt if channel else "",
            placeholder="Add extra instructions or context for the AI here.",
        )
        self.add_item(
            ui.Label(
                component=self.prompt_input,
                text="Channel Prompt (optional)",
                description="Extra instructions and context specific to this channel.",
            )
        )

        # Extra options as a select menu
        options = [
            discord.SelectOption(
                label="Override System Prompt",
                value="override_system_prompt",
                description="Whether to override the default system prompt with the channel prompt.",
                default=channel.override_system_prompt if channel else False,
            ),
            discord.SelectOption(
                label="Mention Mode",
                value="mention_mode",
                description="Whether the bot should only respond when mentioned.",
                default=channel.mention_mode if channel else False,
            ),
        ]

        self.options_select = ui.Select(
            options=options,
            placeholder="Select additional options...",
            required=False,
            min_values=0,
            max_values=len(options),
        )
        self.add_item(
            ui.Label(
                component=self.options_select,
                text="Additional Options",
                description="Configure additional settings for this channel.",
            )
        )
        await interaction.response.send_modal(self)
        
    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        prompt = self.prompt_input.value
        selected_options = self.options_select.values
        override_system_prompt = "override_system_prompt" in selected_options
        mention_mode = "mention_mode" in selected_options

        channel = await self.ui_service.get_channel(self.channel_id, ignore_active=True)
        commit_data = {}
        if channel:
            if channel.prompt != prompt:
                commit_data["prompt"] = prompt
            if channel.override_system_prompt != override_system_prompt:
                commit_data["override_system_prompt"] = override_system_prompt
            if channel.mention_mode != mention_mode:
                commit_data["mention_mode"] = mention_mode
        else:
            commit_data = {
                "prompt": prompt,
                "override_system_prompt": override_system_prompt,
                "mention_mode": mention_mode,
            }

        await self.submit_callback(interaction, commit_data)