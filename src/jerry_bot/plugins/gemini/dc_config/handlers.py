"""Event handlers for Gemini configuration menu flows"""

import discord
from .state_enums import UIState, LLMProfileTab
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .menu import GeminiConfigMenu


class ChannelHandler:
    """Handles channel-related flows"""

    def __init__(self, menu: "GeminiConfigMenu"):
        self.menu = menu

    async def activate_show(self, interaction: discord.Interaction):
        """Show channel configuration for activation"""
        channel = await self.menu.service.get_channel(
            self.menu.channel_id, active=False
        )
        if channel is None:
            await self.edit_show(interaction)
            return

        await interaction.response.defer()
        try:
            await self.menu.service.set_channel(self.menu.channel_id, active=True)
        except Exception as e:
            await self.menu._handle_error(f"Failed to activate Gemini: {str(e)}")
        await self.menu.render()

    async def edit_show(self, interaction: discord.Interaction):
        """Show channel edit modal"""
        from .channel_modal import GeminiConfigModal

        modal = GeminiConfigModal(
            self.menu.service, self.menu.channel_id, submit_callback=self.edit_submit
        )
        await modal.show(interaction)

    async def edit_submit(self, interaction: discord.Interaction, commit_data: dict):
        """Handle channel configuration submission"""
        await interaction.response.defer()

        try:
            await self.menu.service.set_channel(
                channel_id=self.menu.channel_id,
                guild_id=self.menu.guild_id,
                create=True,
                active=True,
                **commit_data,
            )
        except Exception as e:
            await self.menu._handle_error(f"Failed to activate Gemini: {str(e)}")
            return

        await self.menu.render()

    async def deactivate(self, interaction: discord.Interaction):
        """Deactivate the channel"""
        await interaction.response.defer()
        try:
            await self.menu.service.set_channel(self.menu.channel_id, active=False)
        except Exception as e:
            await self.menu._handle_error(f"Failed to deactivate Gemini: {str(e)}")
        await self.menu.render()


class ProfileHandler:
    """Handles LLM profile-related flows"""

    def __init__(self, menu: "GeminiConfigMenu"):
        self.menu = menu

    async def new_profile_show(self, interaction: discord.Interaction):
        """Show modal to create a new LLM profile"""
        from .llm_profile_modal import LLMProfileModal

        modal = LLMProfileModal(
            self.menu.service,
            self.menu.channel_id,
            submit_callback=self.new_profile_submit,
        )
        await modal.show(interaction)

    async def edit_profile_show(self, interaction: discord.Interaction):
        """Show modal to edit existing LLM profile"""
        from .llm_profile_modal import LLMProfileModal

        values = interaction.data["values"]  # type: ignore
        if not values:
            await self.menu._handle_error("No LLM profile selected.")
            return

        profile_id = int(values[0])
        modal = LLMProfileModal(
            self.menu.service,
            self.menu.channel_id,
            llm_profile_id=profile_id,
            submit_callback=lambda inter, data: self.new_profile_submit(
                inter, data, llm_profile_id=profile_id
            ),
        )
        await modal.show(interaction)

    async def new_profile_submit(
        self,
        interaction: discord.Interaction,
        commit_data: dict,
        llm_profile_id: int | None = None,
    ):
        """Handle LLM profile submission"""
        await interaction.response.defer()

        if commit_data.get("provider_name") and commit_data.get("model_name"):
            provider = self.menu.service.get_provider(commit_data["provider_name"])
            if provider is None:
                await self.menu._handle_error(
                    f"Provider {commit_data['provider_name']} not found."
                )
                return

            if not await self.menu.service.model_exists(
                commit_data["provider_name"], commit_data["model_name"]
            ):
                await self.menu._handle_error(
                    f"Model name {commit_data['model_name']} is not valid for provider {provider.friendly_name}."
                )
                return

        try:
            await self.menu.service.set_llm_profile(
                channel_id=self.menu.channel_id,
                id=llm_profile_id,
                create=True,
                **commit_data,
            )
        except Exception as e:
            await self.menu._handle_error(f"Failed to create LLM profile: {str(e)}")
            return

        await self.menu.render()

    async def toggle_tab(self, interaction: discord.Interaction):
        """Toggle between PROFILE and FAIL_OVER tabs"""
        await interaction.response.defer()
        self.menu.llm_profile_tab = (
            LLMProfileTab.FAIL_OVER
            if self.menu.llm_profile_tab == LLMProfileTab.PROFILE
            else LLMProfileTab.PROFILE  # Toggle between PROFILE(1) and FAIL_OVER(2)
        )
        await self.menu.render()


class GuildHandler:
    """Handles guild/server-related flows"""

    def __init__(self, menu: "GeminiConfigMenu"):
        self.menu = menu

    async def create_guild(self, interaction: discord.Interaction):
        """Create guild record"""
        await interaction.response.defer()
        try:
            await self.menu.service.set_guild(
                guild_id=self.menu.guild_id,
                create=True,
                trusted=False,
                prompt=None,
            )
        except Exception as e:
            await self.menu._handle_error(f"Failed to create guild record: {str(e)}")
            return
        await self.menu.render()

    async def toggle_guild_trust(self, interaction: discord.Interaction):
        """Toggle guild trusted status"""
        await interaction.response.defer()
        guild = await self.menu.service.get_guild(self.menu.guild_id)
        try:
            if guild is None:
                await self.menu.service.set_guild(
                    self.menu.guild_id, create=True, trusted=True
                )
            else:
                await self.menu.service.set_guild(
                    self.menu.guild_id, trusted=not guild.trusted
                )
        except Exception as e:
            await self.menu._handle_error(
                f"Failed to update guild trust status: {str(e)}"
            )
        await self.menu.render()
