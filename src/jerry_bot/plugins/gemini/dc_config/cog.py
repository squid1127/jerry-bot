"""Interaction handlers for the Gemini plugin."""

from typing import ClassVar

from squid_core import PluginCog, Plugin
from squid_core.components.perms import PermissionLevel
import discord
from discord import app_commands
from discord.ext import commands

from ..core import UIService
from .utils import create_error_embed, send_ephemeral_response
from .menu import GeminiConfigMenu


class GeminiCog(PluginCog):
    """Cog for Gemini Plugin to handle Discord events."""

    def __init__(
        self,
        plugin: Plugin,
        ui_service: UIService,
    ):
        super().__init__(plugin)
        self._ui_service = ui_service

    @app_commands.command(
        name="gemini-config",
        description="[Gemini] Open the configuration menu for this channel.",
    )
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.guild_install()
    @app_commands.guild_only()
    async def gemini_config(self, interaction: discord.Interaction):
        """Open the Gemini configuration menu for this channel."""
        if not await self.check_permissions(interaction):
            return

        menu = GeminiConfigMenu(self._ui_service, interaction)
        await menu.render()

    @gemini_config.error
    async def gemini_config_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for the gemini-config command."""
        self.plugin.logger.error(f"Error in gemini-config command: {error}")
        await send_ephemeral_response(
            interaction,
            error="An unexpected error occurred while trying to open the Gemini configuration menu. Please try again later.",
        )

    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if the user has permission to interact with the Gemini plugin."""

        def error_message(content: str):
            return create_error_embed(description=content)

        # Only allow interactions within guilds (servers), not in DMs
        if not interaction.guild:
            await interaction.response.send_message(
                embed=error_message("This command can only be used within a server."),
                ephemeral=True,
            )
            return False

        if not (
            await self.plugin.fw.perms.interaction_check(
                interaction, required_level=PermissionLevel.MODERATOR
            )
        ):
            return False  # Interaction check already responds

        # Check bot permissions in the channel
        perms = interaction.channel.permissions_for(interaction.guild.me)  # type: ignore
        if not perms.manage_channels and not perms.send_messages:
            await interaction.response.send_message(
                embed=error_message(
                    "I need the Manage Channels permission in this channel to execute this command."
                ),
                ephemeral=True,
            )
            return False

        return True

    @app_commands.command(
        name="gemini-reset",
        description="[Gemini] Reset the conversation in this channel, clearing all context and history.",
    )
    async def gemini_reset(self, interaction: discord.Interaction):
        """Reset the Gemini conversation in this channel, clearing all context and history."""

        if (
            not isinstance(interaction.channel, discord.TextChannel)
            or not interaction.channel_id
        ):
            await send_ephemeral_response(
                interaction, error="This command can only be used in text channels."
            )
            return

        try:
            exists = self._ui_service.has_conversation(interaction.channel_id)
            if not exists:
                await send_ephemeral_response(
                    interaction,
                    error="There is no active Gemini conversation in this channel to reset.",
                )
                return
            await interaction.response.defer(ephemeral=False)
            await self._ui_service.stop_conversation(interaction.channel_id)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Conversation Cleared",
                    description="The conversation in this channel has been reset. All context and history have been cleared.",
                    color=discord.Color.green(),
                ),
                ephemeral=False,
            )
        except Exception as e:
            self.plugin.logger.error(f"Error resetting Gemini conversation: {e}")
            await send_ephemeral_response(
                interaction,
                error="An unexpected error occurred while trying to reset the Gemini conversation. Please try again later.",
            )
            return

    @gemini_reset.error
    async def gemini_reset_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for the gemini-reset command."""
        self.plugin.logger.error(f"Error in gemini-reset command: {error}")
        await send_ephemeral_response(
            interaction,
            error="An unexpected error occurred while trying to reset the Gemini conversation for this channel. Please try again later.",
        )
