"""Cog for Auto Reply Plugin for application commands."""

from squid_core.plugin_base import PluginCog, Plugin
from squid_core import Framework
from squid_core.components.perms import PermissionLevel

import discord
from discord.ext import commands
from discord import app_commands as cmds

from .models.db import AutoReplyIgnore
from .models.enums import IgnoreType

from .ar import AutoReply

class AutoReplyCog(PluginCog):
    """Cog for Auto Reply Plugin for application commands."""

    def __init__(self, plugin: Plugin, ar: AutoReply):
        super().__init__(plugin)
        self.ar = ar

    ar_ignore = cmds.Group(
        name="ar-ignore",
        description="Set auto-reply to ignore/unignore a channel, user, guild, or role.",
        guild_only=True,
        allowed_contexts=cmds.AppCommandContext(guild=True),
        default_permissions=discord.Permissions(manage_channels=True),
    )

    async def _update_ignore(
        self,
        interaction: discord.Interaction,
        ignore_type: IgnoreType,
        target: discord.User | discord.TextChannel | discord.Role | discord.Guild,
        global_ignore: bool,
    ):
        """Helper to update ignore status."""
        await interaction.response.defer(ephemeral=True)

        if global_ignore:
            if not await self.fw.perms.interaction_check(
                interaction, PermissionLevel.ADMIN
            ):
                return

        guild_id_str = None
        if ignore_type is not IgnoreType.GUILD:
            guild_id_str = None if global_ignore else str(interaction.guild.id)

        discord_id = str(target.id)

        existing = await AutoReplyIgnore.get_or_none(
            discord_type=ignore_type,
            discord_id=discord_id,
            guild_id=guild_id_str,
        )

        target_mention = (
            f"**{target.name}**"
            if isinstance(target, discord.Guild)
            else target.mention
        )

        if existing:
            await existing.delete()
            scope = "globally" if global_ignore or ignore_type is IgnoreType.GUILD else f"in {interaction.guild.name}"
            message = f"Stopped ignoring {target_mention} {scope}."
        else:
            await AutoReplyIgnore.create(
                discord_type=ignore_type,
                discord_id=discord_id,
                guild_id=guild_id_str,
            )
            scope = "globally" if global_ignore or ignore_type is IgnoreType.GUILD else f"in {interaction.guild.name}"
            message = f"Now ignoring {target_mention} {scope}."
            if global_ignore and ignore_type in [IgnoreType.CHANNEL, IgnoreType.ROLE]:
                message += " (Warning: Ignoring channels or roles globally has no effect as they are server-specific.)"

        await interaction.followup.send(message, ephemeral=True)

        try:
            await self.ar.load_cache()
            await self.fw.redis.publish(
                "jerry:auto_reply:reload_cache",
                {"type": "ignore_modified", "source": "ar-ignore_command"},
            )
        except Exception as e:
            await interaction.followup.send(
                "Warning: Your ignore settings were saved, but the cache update failed. "
                "Changes may not take effect immediately.",
                ephemeral=True,
            )
            self.plugin.logger.error(
                "Failed to update cache after ar-ignore command.", exc_info=e
            )

    @ar_ignore.command(name="user", description="Toggle ignoring a user.")
    @cmds.describe(
        user="The user to ignore or unignore.",
        global_ignore="Apply this ignore globally across all servers (Admin only).",
    )
    async def ar_ignore_user(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        global_ignore: bool = False,
    ):
        """Toggles ignoring a user for auto-replies."""
        await self._update_ignore(interaction, IgnoreType.USER, user, global_ignore)

    @ar_ignore.command(name="channel", description="Toggle ignoring a channel.")
    @cmds.describe(
        channel="The channel to ignore or unignore.",
        global_ignore="Apply this ignore globally (Admin only, not recommended).",
    )
    async def ar_ignore_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        global_ignore: bool = False,
    ):
        """Toggles ignoring a channel for auto-replies."""
        await self._update_ignore(
            interaction, IgnoreType.CHANNEL, channel, global_ignore
        )

    @ar_ignore.command(name="role", description="Toggle ignoring a role.")
    @cmds.describe(
        role="The role to ignore or unignore.",
        global_ignore="Apply this ignore globally (Admin only, not recommended).",
    )
    async def ar_ignore_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        global_ignore: bool = False,
    ):
        """Toggles ignoring a role for auto-replies."""
        await self._update_ignore(interaction, IgnoreType.ROLE, role, global_ignore)

    @ar_ignore.command(name="server", description="Toggle ignoring this entire server.")
    async def ar_ignore_server(self, interaction: discord.Interaction):
        """Toggles ignoring the current server for auto-replies."""
        await self._update_ignore(
            interaction, IgnoreType.GUILD, interaction.guild, global_ignore=True
        )

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: cmds.AppCommandError
    ):
        """Handles errors for all commands in this cog."""
        message = "An unknown error occurred."
        if isinstance(error, (cmds.MissingPermissions, cmds.CheckFailure)):
            message = "You do not have permission to use this command."
        else:
            self.plugin.logger.error(
                f"An error occurred in a command: {error}", exc_info=error
            )

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)