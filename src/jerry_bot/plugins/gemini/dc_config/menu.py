"""Main UI menu for Gemini configuration"""

import discord
from discord import ui

from .state_enums import LLMProfileTab, UIState
from ..core import UIService
from ..constants import UI_PLUGIN_NAME

from .handlers import ChannelHandler, ProfileHandler, GuildHandler
from .renderers import MenuRenderer


class GeminiConfigMenu(ui.LayoutView):
    """Main UI menu for Gemini configuration"""

    def __init__(self, service: UIService, interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.service = service
        self.interaction = interaction
        self.state = UIState.OVERVIEW
        self.llm_profile_tab = LLMProfileTab.PROFILE
        self._error_message: str | None = None

        # Initialize handlers
        self.channel_handler = ChannelHandler(self)
        self.profile_handler = ProfileHandler(self)
        self.guild_handler = GuildHandler(self)

        # Initialize renderer
        self.renderer = MenuRenderer(service, self)

    async def render(self):
        """Renders the menu"""
        self.clear_items()

        if self.state == UIState.OVERVIEW:
            self.add_item(
                await self.renderer.render_overview(self.channel_id, self.guild_id)
            )
        elif self.state == UIState.ERROR:
            self.add_item(
                await self.renderer.render_error(self._error_message or "Unknown error")
            )

        await self._update_self()

    # Channel-related flows
    async def flow_activate_show(self, interaction: discord.Interaction):
        """Delegate to channel handler"""
        await self.channel_handler.activate_show(interaction)

    async def flow_edit_show(self, interaction: discord.Interaction):
        """Delegate to channel handler"""
        await self.channel_handler.edit_show(interaction)

    async def flow_deactivate(self, interaction: discord.Interaction):
        """Delegate to channel handler"""
        await self.channel_handler.deactivate(interaction)

    # Profile-related flows
    async def flow_new_llm_profile_show(self, interaction: discord.Interaction):
        """Delegate to profile handler"""
        await self.profile_handler.new_profile_show(interaction)

    async def flow_edit_llm_profile_show(self, interaction: discord.Interaction):
        """Delegate to profile handler"""
        await self.profile_handler.edit_profile_show(interaction)

    async def flow_tab_next(self, interaction: discord.Interaction):
        """Delegate to profile handler"""
        await self.profile_handler.toggle_tab(interaction)

    # Guild-related flows
    async def flow_create_guild(self, interaction: discord.Interaction):
        """Delegate to guild handler"""
        await self.guild_handler.create_guild(interaction)

    async def flow_toggle_guild_trust(self, interaction: discord.Interaction):
        """Delegate to guild handler"""
        await self.guild_handler.toggle_guild_trust(interaction)

    # State management flows
    async def flow_back_to_overview(self, interaction: discord.Interaction):
        """Return to overview state"""
        await interaction.response.defer()
        self.state = UIState.OVERVIEW
        await self.render()

    async def _update_self(self):
        """Updates the menu message"""
        if self.interaction.response.is_done():
            await self.interaction.edit_original_response(view=self)
        else:
            await self.interaction.response.send_message(view=self, ephemeral=True)

    async def _handle_error(self, error_message: str):
        """Handles errors by updating the state and re-rendering the menu"""
        self._error_message = error_message
        self.state = UIState.ERROR
        await self.render()

    @property
    def channel_id(self) -> int:
        """Returns the channel ID associated with this menu"""
        if self.interaction.channel_id is None:
            raise ValueError("Interaction does not have a channel ID")
        return self.interaction.channel_id

    @property
    def guild_id(self) -> int:
        """Returns the guild ID associated with this menu"""
        if self.interaction.guild_id is None:
            raise ValueError("Interaction does not have a guild ID")
        return self.interaction.guild_id
