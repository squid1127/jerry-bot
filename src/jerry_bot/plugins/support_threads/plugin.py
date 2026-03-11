"""Main plugin file for SupportThreads plugin."""

import asyncio
from squid_core import Plugin as PluginBase, PluginCog, Framework

from .models.db import SupportThreadConfig
from .thread import SupportThreadInstance

import discord
from discord import app_commands, datetime
from discord.ext import commands
from discord.ext import tasks

class SupportThreadsPlugin(PluginBase):
    """Plugin class for SupportThreads."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.cog = SupportThreadsCog(self)
        self._instances: dict[int, SupportThreadInstance] = {}

    async def load(self) -> None:
        """Load the SupportThreads plugin."""
        await self.load_instances()
        await self.fw.bot.add_cog(self.cog)
        self.logger.info("SupportThreads plugin loaded.")

    async def unload(self) -> None:
        """Unload the SupportThreads plugin."""
        await self.fw.bot.remove_cog(self.cog.__class__.__name__)
        self._instances.clear()

    async def load_instances(self) -> None:
        """Load existing support thread instances from the database."""
        configs = await SupportThreadConfig.all()
        for config in configs:
            instance = SupportThreadInstance(config, self)
            self._instances[config.threads_channel_id] = instance

    @property
    def instances(self) -> dict[int, SupportThreadInstance]:
        """Get the dictionary of support thread instances."""
        return self._instances

    def get_instance(self, channel_id: int) -> SupportThreadInstance | None:
        """Get a support thread instance by channel ID."""
        return self._instances.get(channel_id, None)

    def get_guild_instances(self, guild_id: int) -> list[SupportThreadInstance]:
        """Get all support thread instances for a specific guild."""
        return [
            instance
            for instance in self._instances.values()
            if instance.config.guild_id == guild_id
        ]


class SupportThreadsCog(PluginCog):
    """
    Cog class for SupportThreads.
    """

    support_group = app_commands.Group(
        name="support",
        description="Commands for managing support threads.",
        default_permissions=discord.Permissions(manage_channels=True),
        allowed_contexts=app_commands.AppCommandContext(guild=True),
        allowed_installs=app_commands.AppInstallationType(guild=True),
    )

    def __init__(self, plugin: SupportThreadsPlugin):
        self.plugin: SupportThreadsPlugin = plugin
        self.bot = plugin.fw.bot
        self.logger = plugin.logger

        super().__init__(plugin)

    async def apply_recommended_permissions(
        self, channel: discord.TextChannel, support_role: discord.Role | None
    ) -> None:
        """Apply recommended permissions to the support threads channel."""
        overwrites = {
            channel.guild.default_role: discord.PermissionOverwrite(
                send_messages=False,
                send_messages_in_threads=True,
                create_public_threads=False,
                create_private_threads=False,
            ),
            channel.guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_messages=True,
                manage_channels=True,
            ),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                manage_messages=True, manage_threads=True
            )

        await channel.edit(overwrites=overwrites)

    @support_group.command(
        name="setup", description="[SupportThreads] Setup support threads in the guild."
    )
    @app_commands.describe(
        channel="The channel where support threads will be created.",
        apply_perms="Whether to apply recommended permissions to the channel.",
        support_role="The role assigned to support staff (optional).",
        description="A description for the support threads (optional). Markdown formatted. Include a heading. Use \\n for new lines.",
    )
    async def setup_support_threads(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        apply_perms: bool,
        support_role: discord.Role = None,
        description: str = None,
    ):
        """Setup support threads in the guild."""
        await interaction.response.defer(ephemeral=True)

        # Try to apply recommended permissions
        if apply_perms:
            try:
                await self.apply_recommended_permissions(channel, support_role)
            except discord.Forbidden:
                self.plugin.logger.warning(
                    f"Missing permissions to edit channel {channel.id} for support thread setup."
                )
                embed = discord.Embed(
                    title="⚠️ Permission Warning",
                    description=f"Could not apply recommended permissions to {channel.mention}. Please ensure the bot has the necessary permissions.",
                    color=0xFFA500,  # Orange
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            except discord.HTTPException as e:
                self.plugin.logger.error(
                    f"Failed to edit channel {channel.id} for support thread setup: {e}"
                )
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"An error occurred while applying permissions to {channel.mention}.",
                    color=0xFF0000,  # Red
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            embed = discord.Embed(
                title="✅ Permissions Applied",
                description=f"Recommended permissions have been applied to {channel.mention}.",
                color=0x00FF00,  # Green
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        # Check if configuration already exists
        existing_config = await SupportThreadConfig.filter(
            guild_id=interaction.guild.id
        ).first()
        if existing_config:
            embed = discord.Embed(
                title="⚠️ Already Configured",
                description="Support threads are already configured in this guild.",
                color=0xFFA500,  # Orange
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Create new configuration
        config = SupportThreadConfig(
            guild_id=interaction.guild.id,
            threads_channel_id=channel.id,
            support_role_id=support_role.id if support_role else None,
            description=description,
        )
        await config.save()

        # Create and store the new support thread instance
        instance = SupportThreadInstance(config, self.plugin)
        await instance.init()
        self.plugin.instances[channel.id] = instance

        # Send confirmation message
        embed = discord.Embed(
            title="✅ Setup Complete",
            description=f"Support threads have been set up in {channel.mention}.",
            color=0x00FF00,  # Green
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @setup_support_threads.error
    async def setup_support_threads_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for setup_support_threads command."""
        self.logger.error(f"Error in setup_support_threads command: {error}")
        embed = discord.Embed(
            title="❌ Error",
            description="An error occurred while setting up support threads.",
            color=0xFF0000,  # Red
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @support_group.command(
        name="close", description="[SupportThreads] Close the current thread."
    )
    @app_commands.guild_only()
    async def force_close_thread(self, interaction: discord.Interaction):
        """Force close the current support thread."""
        await interaction.response.defer(ephemeral=True)

        # Check if we're in a thread
        if not isinstance(interaction.channel, discord.Thread):
            embed = discord.Embed(
                title="❌ Error",
                description="This command can only be used in a thread.",
                color=0xFF0000,  # Red
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        thread = interaction.channel

        # Check if this is a support thread
        if thread.parent is None:
            embed = discord.Embed(
                title="❌ Error",
                description="Could not find the parent channel for this thread.",
                color=0xFF0000,  # Red
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        instance = self.plugin.get_instance(thread.parent.id)
        if instance is None:
            embed = discord.Embed(
                title="❌ Error",
                description="This is not a support thread.",
                color=0xFF0000,  # Red
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Force close the thread
        try:
            await instance.close_thread(
                thread,
                reason=f"This support thread has been closed by {interaction.user.mention}.",
            )

            embed = discord.Embed(
                title="✅ Thread Closed",
                description="The support thread has been force closed.",
                color=0x00FF00,  # Green
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except (discord.Forbidden, discord.HTTPException):
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to close the thread. Please check bot permissions.",
                color=0xFF0000,  # Red
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @force_close_thread.error
    async def force_close_thread_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for force_close_thread command."""
        self.logger.error(f"Error in force_close_thread command: {error}")
        embed = discord.Embed(
            title="❌ Error",
            description="An error occurred while force closing the thread.",
            color=0xFF0000,  # Red
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @support_group.command(
        name="create", description="[SupportThreads] Create a support thread on behalf of a user."
    )
    @app_commands.describe(user="The user to create a support thread for.")
    async def create_for_user(
        self, interaction: discord.Interaction, user: discord.Member
    ):
        """Create a support thread on behalf of a user."""
        await interaction.response.defer(ephemeral=True)

        # Find the support thread instance for this guild
        instances = self.plugin.get_guild_instances(interaction.guild.id)
        if not instances:
            embed = discord.Embed(
                title="❌ Error",
                description="Support threads are not configured in this guild.",
                color=0xFF0000,  # Red
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Use the first instance (assuming one per guild)
        instance = instances[0]
        channel = instance.channel

        if channel is None:
            embed = discord.Embed(
                title="❌ Error",
                description="Could not find the support threads channel.",
                color=0xFF0000,  # Red
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Check for existing threads
        existing_threads = await instance.get_existing_threads(channel, user)
        if existing_threads:
            if len(existing_threads) == 1:
                description = f"{user.mention} already has an open support thread: {existing_threads[0].mention}"
            else:
                description = f"{user.mention} already has open support threads: {', '.join(thread.mention for thread in existing_threads)}"
            embed = discord.Embed(
                title="⚠️ Thread Exists",
                description=description,
                color=0xFFA500,  # Orange
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Create the thread on behalf of the user
        thread_channel = await instance.create_thread_for_user(
            user, created_by=interaction.user
        )

        if thread_channel:
            embed = discord.Embed(
                title="✅ Thread Created",
                description=f"Support thread created for {user.mention}: {thread_channel.mention}",
                color=0x00FF00,  # Green
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to create the support thread.",
                color=0xFF0000,  # Red
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @create_for_user.error
    async def create_for_user_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for create_for_user command."""
        self.logger.error(f"Error in create_for_user command: {error}")
        embed = discord.Embed(
            title="❌ Error",
            description="An error occurred while creating the support thread.",
            color=0xFF0000,  # Red
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        """Update view messages for all support thread instances on bot ready."""
        for instance in self.plugin.instances.values():
            await instance.init()

    @commands.Cog.listener()
    async def on_thread_member_leave(
        self, thread: discord.Thread, member: discord.Member
    ):
        """Handle thread member leave events to close support threads if needed."""
        instance = self.plugin.get_instance(thread.parent.id)
        if instance is None:
            return

        self.plugin.logger.info(
            f"Handling member leave for thread {thread.id} in guild {thread.guild.id}."
        )
        await instance.handle_thread_member_leave(thread, member)

    @support_group.command(
        name="disable", description="[SupportThreads] Delete support threads configuration in the guild."
    )
    async def delete_support_threads(self, interaction: discord.Interaction):
        """Delete support threads configuration in the guild."""
        await interaction.response.defer(ephemeral=True)

        # Find existing configuration
        existing_config = await SupportThreadConfig.filter(
            guild_id=interaction.guild.id
        ).first()
        if not existing_config:
            embed = discord.Embed(
                title="⚠️ Not Configured",
                description="Support threads are not configured in this guild.",
                color=0xFFA500,  # Orange
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Delete configuration
        await existing_config.delete()

        # Try to delete the view message
        instance = self.plugin.get_instance(existing_config.threads_channel_id)
        if instance:
            await instance.delete_view_message()

        # Remove instance from plugin
        if existing_config.threads_channel_id in self.plugin.instances:
            del self.plugin.instances[existing_config.threads_channel_id]

        # Send confirmation message
        embed = discord.Embed(
            title="✅ Deletion Complete",
            description="Support threads configuration has been deleted for this guild.",
            color=0x00FF00,  # Green
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @delete_support_threads.error
    async def delete_support_threads_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Error handler for delete_support_threads command."""
        self.logger.error(f"Error in delete_support_threads command: {error}")
        embed = discord.Embed(
            title="❌ Error",
            description="An error occurred while deleting support threads configuration.",
            color=0xFF0000,  # Red
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
