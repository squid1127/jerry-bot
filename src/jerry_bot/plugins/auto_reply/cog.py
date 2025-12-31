"""Cog for Auto Reply Plugin for application commands."""

from squid_core.plugin_base import PluginCog, Plugin
from squid_core import Framework
from squid_core.components.perms import PermissionLevel

import discord
from discord.ext import commands
from discord import app_commands as cmds

from .models.db import AutoReplyIgnore
from .models.enums import IgnoreType

class AutoReplyCog(PluginCog):
    """Cog for Auto Reply Plugin for application commands."""

    def __init__(self, plugin: Plugin):
        super().__init__(plugin)

    @cmds.command(
        name="ar-ignore",
        description="Set auto-reply to ignore/unignore a channel, user, guild, or role.",
    )
    @cmds.describe(
        user="Ignore messages from this user.",
        channel="Ignore messages in this channel.",
        server="Ignore messages in this server (Set to true).",
        role="Ignore messages from this role.",
        global_ignore="Ignore messages globally (all servers).",
    )
    @cmds.guild_only()
    @cmds.guild_install()
    @cmds.checks.has_permissions(manage_channels=True)
    async def ar_ignore(
        self,
        interaction: discord.Interaction,
        user: discord.User | None = None,
        channel: discord.TextChannel | None = None,
        server: bool | None = None,
        role: discord.Role | None = None,
        global_ignore: bool = False,
    ):
        """Set auto-reply to ignore a channel, user, guild, or role."""
        guild = server  # Alias for clarity
        
        if global_ignore:
            if not await self.fw.perms.interaction_check(
                interaction,
                PermissionLevel.ADMIN,
            ):
                return
        
        # Check that params are mutually exclusive
        if sum(param is not None and param is not False for param in [user, channel, guild, role]) != 1:
            await interaction.response.send_message(
                "You must specify exactly one of user, channel, guild, or role to ignore.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        
        # Perform the ignore action
        if user is not None:
            # Check if already ignored
            guild_id_str = None if global_ignore else str(interaction.guild.id)
            existing = await AutoReplyIgnore.get_or_none(
                discord_type=IgnoreType.USER,
                discord_id=str(user.id),
                guild_id=guild_id_str,
            )
            if existing is not None:
                await existing.delete()
                scope = "globally" if global_ignore else f"in {interaction.guild.name}"
                await interaction.followup.send(
                    f"Stopped ignoring {user.mention} {scope}.",
                    ephemeral=True,
                )
                
            else:
                await AutoReplyIgnore.create(
                    discord_type=IgnoreType.USER,
                    discord_id=str(user.id),
                    guild_id=guild_id_str,
                )
                scope = "globally" if global_ignore else f"in {interaction.guild.name}"
                await interaction.followup.send(
                    f"Now ignoring {user.mention} {scope}.",
                    ephemeral=True,
                )
                
        elif channel is not None:
            guild_id_str = None if global_ignore else str(interaction.guild.id)
            existing = await AutoReplyIgnore.get_or_none(
                discord_type=IgnoreType.CHANNEL,
                discord_id=str(channel.id),
                guild_id=guild_id_str,
            )
            if existing is not None:
                await existing.delete()
                scope = "globally (Warning: Ignoring channels globally does not do anything as channels are unique to servers. It is not recommended to ignore channels and roles globally)" if global_ignore else f"in {interaction.guild.name}"
                await interaction.followup.send(
                    f"Stopped ignoring {channel.mention} {scope}.",
                    ephemeral=True,
                )
                
            else:
                await AutoReplyIgnore.create(
                    discord_type=IgnoreType.CHANNEL,
                    discord_id=str(channel.id),
                    guild_id=guild_id_str,
                )
                scope = "globally (Warning: Ignoring channels globally does not do anything as channels are unique to servers. It is not recommended to ignore channels and roles globally)" if global_ignore else f"in {interaction.guild.name}"
                await interaction.followup.send(
                    f"Now ignoring {channel.mention} {scope}.",
                    ephemeral=True,
                )
                
        elif guild is True:
            guild_obj = interaction.guild
            # Guild ignores are always global (guild_id should be None)
            # because the discord_id itself is the guild being ignored
            existing = await AutoReplyIgnore.get_or_none(
                discord_type=IgnoreType.GUILD,
                discord_id=str(guild_obj.id),
                guild_id=None,  # Guild ignores are always global
            )
            if existing is not None:
                await existing.delete()
                await interaction.followup.send(
                    f"Stopped ignoring guild **{guild_obj.name}**.",
                    ephemeral=True,
                )
                
            else:
                await AutoReplyIgnore.create(
                    discord_type=IgnoreType.GUILD,
                    discord_id=str(guild_obj.id),
                    guild_id=None,  # Guild ignores are always global
                )
                await interaction.followup.send(
                    f"Now ignoring guild **{guild_obj.name}**.",
                    ephemeral=True,
                )

        elif guild is False:
            # Do nothing
            await interaction.followup.send(
                "Guild ignore set to false; no action taken. To ignore another type (channel, role, user), do not specify this parameter.",
                ephemeral=True,
            )
                
        elif role is not None:
            guild_id_str = None if global_ignore else str(interaction.guild.id)
            existing = await AutoReplyIgnore.get_or_none(
                discord_type=IgnoreType.ROLE,
                discord_id=str(role.id),
                guild_id=guild_id_str,
            )
            if existing is not None:
                await existing.delete()
                scope = "globally (Warning: Ignoring roles globally does not do anything as roles are unique to servers. It is not recommended to ignore channels and roles globally)" if global_ignore else f"in {interaction.guild.name}"
                await interaction.followup.send(
                    f"Stopped ignoring role {role.mention} {scope}.",
                    ephemeral=True,
                )
                
            else:
                await AutoReplyIgnore.create(
                    discord_type=IgnoreType.ROLE,
                    discord_id=str(role.id),
                    guild_id=guild_id_str,
                )
                scope = "globally (Warning: Ignoring roles globally does not do anything as roles are unique to servers. It is not recommended to ignore channels and roles globally)" if global_ignore else f"in {interaction.guild.name}"
                await interaction.followup.send(
                    f"Now ignoring role {role.mention} {scope}.",
                    ephemeral=True,
                )
                
        # Trigger Cache Update (write-through cache)
        try:
            await self.plugin.load_cache()
            # Notify other instances via Redis
            await self.fw.redis.publish(
                "jerry:auto_reply:reload_cache",
                {"type": "ignore_modified", "source": "ar-ignore_command"},
            )
        except Exception as e:
            await interaction.followup.send(
                "Warning: Your ignore settings were saved, but the cache/propagation "
                "step failed. Changes may not take effect immediately on all bot "
                "instances.",
                ephemeral=True,
            )
            self.plugin.logger.error(
                "Failed to update cache after ar-ignore command.",
                exc_info=e,
            )
            
    @ar_ignore.error
    async def ar_ignore_error(
        self,
        interaction: discord.Interaction,
        error: cmds.AppCommandError,
    ):
        """Error handler for ar-ignore command."""
        # Determine the appropriate error message based on the error type
        if isinstance(error, (cmds.MissingPermissions, cmds.CheckFailure)):
            message = "You do not have permission to use this command."
        else:
            message = "An error occurred while processing the command."

        # Decide whether to send an initial response or a followup
        if interaction.response.is_done():
            await interaction.followup.send(
                message,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                message,
                ephemeral=True,
            )