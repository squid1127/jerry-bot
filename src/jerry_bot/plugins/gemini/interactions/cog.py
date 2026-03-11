"""Interaction handlers for the Gemini plugin."""

from typing import ClassVar

from squid_core import PluginCog, Plugin
from squid_core.components.perms import PermissionLevel
import discord
from discord import app_commands
from discord.ext import commands

from ..models import Channel
from ..core.manager import ConversationManager
from .utils import send_ephemeral_response, create_error_embed
from .editor import ChannelConfigEditor

class GeminiCog(PluginCog):
    """Cog for Gemini Plugin to handle Discord events."""

    group: ClassVar[app_commands.Group] = app_commands.Group(
        name="gemini-config",
        description="Commands for configuring jerry-gemini.",
        default_permissions=discord.Permissions(manage_channels=True),
        allowed_contexts=app_commands.AppCommandContext(guild=True),
        allowed_installs=app_commands.AppInstallationType(guild=True),
    )

    def __init__(self, plugin: Plugin, conversation_manager: ConversationManager):
        super().__init__(plugin)
        self.conversation_manager = conversation_manager

    @group.command(
        name="enable", description="Enable the Gemini in this channel."
    )
    async def enable(self, interaction: discord.Interaction):
        """Start the channel configuration editor for the current channel, allowing the user to set up Gemini for this channel. If Gemini is already enabled for this channel, this will allow the user to edit the existing configuration."""
        if not await self.check_permissions(interaction):
            return
        
        editor = ChannelConfigEditor(conversation_manager=self.conversation_manager, interaction=interaction)
        await editor.start()
        
    @enable.error
    async def enable_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Error handler for the enable command."""
        self.plugin.logger.error(f"Error in enable command: {error}")
        await send_ephemeral_response(
            interaction,
            error="An unexpected error occurred while trying to enable Gemini for this channel. Please try again later.",
        )
        
    @group.command(
        name="disable", description="Disable the Gemini plugin for this channel."
    )
    async def disable(self, interaction: discord.Interaction):
        """Disable the Gemini plugin for this channel."""
        if not await self.check_permissions(interaction):
            return
        if not interaction.channel_id or not isinstance(interaction.channel, discord.TextChannel):
            await send_ephemeral_response(
                interaction,
                error="Could not determine the channel for this interaction."
            )
            return

        channel = await self.conversation_manager.get_channel(interaction.channel_id)
        if not channel:
            await send_ephemeral_response(
                interaction,
                error="Gemini is not enabled for this channel."
            )
            return

        await self.conversation_manager.delete_channel(channel.channel_id)
        await send_ephemeral_response(
            interaction,
            success="Gemini has been disabled for this channel."
        )
        
    @disable.error
    async def disable_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Error handler for the disable command."""
        self.plugin.logger.error(f"Error in disable command: {error}")
        await send_ephemeral_response(
            interaction,
            error="An unexpected error occurred while trying to disable Gemini for this channel. Please try again later.",
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

        if not (await self.plugin.fw.perms.interaction_check(
            interaction, required_level=PermissionLevel.MODERATOR
        )):
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
