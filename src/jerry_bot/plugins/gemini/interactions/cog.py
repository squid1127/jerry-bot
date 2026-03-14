"""Interaction handlers for the Gemini plugin."""

from typing import ClassVar

from squid_core import PluginCog, Plugin
from squid_core.components.perms import PermissionLevel
import discord
from discord import app_commands
from discord.ext import commands

from ..models import Channel
from ..core.manager import ConversationManager
from .utils import send_ephemeral_response, create_error_embed, UserFacingException
from .channel_editor import ChannelConfigEditor
from .model_editor import ModelConfigEditor

class GeminiCog(PluginCog):
    """Cog for Gemini Plugin to handle Discord events."""

    group: ClassVar[app_commands.Group] = app_commands.Group(
        name="gemini-cfg",
        description="[Gemini] Commands for configuring jerry-gemini.",
        default_permissions=discord.Permissions(manage_channels=True),
        allowed_contexts=app_commands.AppCommandContext(guild=True),
        allowed_installs=app_commands.AppInstallationType(guild=True),
    )

    def __init__(self, plugin: Plugin, conversation_manager: ConversationManager):
        super().__init__(plugin)
        self.conversation_manager = conversation_manager

    @group.command(
        name="channel",
        description="[Gemini] Enable / configure Gemini for this channel.",
    )
    async def enable_channel(self, interaction: discord.Interaction):
        """Start the channel configuration editor for the current channel, allowing the user to set up Gemini for this channel. If Gemini is already enabled for this channel, this will allow the user to edit the existing configuration."""
        if not await self.check_permissions(interaction):
            return

        editor = ChannelConfigEditor(
            conversation_manager=self.conversation_manager, interaction=interaction
        )
        await editor.start()

    @enable_channel.error
    async def enable_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for the enable command."""
        self.plugin.logger.error(f"Error in enable command: {error}")
        await send_ephemeral_response(
            interaction,
            error="An unexpected error occurred while trying to enable Gemini for this channel. Please try again later.",
        )

    @group.command(
        name="model", description="[Gemini] Configure model settings for this channel."
    )
    async def model(self, interaction: discord.Interaction):
        """Configure the model settings for the current channel, including temperature, max tokens, etc."""
        if not await self.check_permissions(interaction):
            return

        editor = ModelConfigEditor(
            conversation_manager=self.conversation_manager, interaction=interaction
        )
        await editor.start()

    @model.error
    async def model_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for the model command."""
        self.plugin.logger.error(f"Error in model command: {error}")
        await send_ephemeral_response(
            interaction,
            error="An unexpected error occurred while trying to configure the model. Please try again later.",
        )

    @group.command(
        name="disable", description="[Gemini] Disable the Gemini for this channel."
    )
    async def disable(self, interaction: discord.Interaction):
        """Disable the Gemini plugin for this channel."""
        if not await self.check_permissions(interaction):
            return
        if not interaction.channel_id or not isinstance(
            interaction.channel, discord.TextChannel
        ):
            await send_ephemeral_response(
                interaction,
                error="Could not determine the channel for this interaction.",
            )
            return

        channel = await self.conversation_manager.get_channel(interaction.channel_id)
        if not channel:
            await send_ephemeral_response(
                interaction, error="Gemini is not enabled for this channel."
            )
            return

        await self.conversation_manager.delete_channel(channel.channel_id)
        await send_ephemeral_response(
            interaction, success="Gemini has been disabled for this channel."
        )

    @disable.error
    async def disable_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for the disable command."""
        self.plugin.logger.error(f"Error in disable command: {error}")
        await send_ephemeral_response(
            interaction,
            error="An unexpected error occurred while trying to disable Gemini for this channel. Please try again later.",
        )
        
    @group.command(
        name="trust", description="[Gemini] Mark this guild as trusted for ephemeral conversations."
    )
    async def trust(self, interaction: discord.Interaction):
        """Mark this channel as trusted for ephemeral conversations, allowing it to be used for temporary conversations that don't require a database entry."""
        if not await self.check_permissions(interaction):
            return
        if not interaction.channel_id or not isinstance(
            interaction.channel, discord.TextChannel
        ):
            await send_ephemeral_response(
                interaction,
                error="Could not determine the channel for this interaction.",
            )
            return
        
        if not interaction.guild_id:
            raise UserFacingException(
                "This command can only be used within a server (guild). Could not determine guild_id from interaction."
            )

        guild = await self.conversation_manager.get_guild(interaction.guild_id, create=True)
        if not guild:
            raise UserFacingException   (
                "An error occurred while trying to access the guild configuration. Please try again later."
            )
            
        updated_guild = await self.conversation_manager.update_guild(guild_id=interaction.guild_id, trusted=not guild.trusted, create=True)
        if not updated_guild:
            raise UserFacingException(
                "An error occurred while trying to update the guild configuration. Please try again later."
            )
        status = "**trusted**" if updated_guild.trusted else "***un*trusted**"
        await send_ephemeral_response(
            interaction, success=f"This guild has been marked as {status} for ephemeral conversations."
        )
    @trust.error
    async def trust_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for the trust command."""
        self.plugin.logger.error(f"Error in trust command: {error}")
        if isinstance(error, UserFacingException):
            await send_ephemeral_response(interaction, error=str(error))
            return
        await send_ephemeral_response(
            interaction,
            error="An unexpected error occurred while trying to update the trust status for this guild. Please try again later.",
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

        conversation = await self.conversation_manager.get_conversation(interaction.channel)
        if not conversation:
            await send_ephemeral_response(
                interaction, error="There is no active Gemini conversation in this channel to reset."
            )
            return

        await self.conversation_manager.stop_conversation(interaction.channel.id, drain=False)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Conversation" + " Dismissed" if conversation.is_ephemeral else "Reset",
                description="Context and history have been cleared.",
                color=discord.Color.green(),
            ),
            ephemeral=False,
        )

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
