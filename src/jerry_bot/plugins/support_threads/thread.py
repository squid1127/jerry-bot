"""Support Thread Instance"""

from .models.db import SupportThreadConfig
from squid_core import Plugin, Framework

import discord

class SupportThreadInstance:
    """Class representing a support thread instance."""

    def __init__(self, config: SupportThreadConfig, plugin: Plugin):
        self.plugin = plugin
        self.config = config

    @property
    def fw(self) -> Framework:
        """Get the framework instance from the plugin."""
        return self.plugin.fw

    @property
    def channel(self) -> discord.TextChannel | None:
        """Get the support threads channel."""
        return self.fw.bot.get_channel(self.config.threads_channel_id)

    def title_view(self) -> discord.ui.LayoutView:
        """Create a Discord UI view for the support thread title."""
        view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container(accent_color=discord.Color.blue())

        if self.config.description:
            content = self.config.description.replace("\\n", "\n")
        else:
            content = "### Private Support Channel\n\nUse this channel to get help!"
        container.add_item(discord.ui.TextDisplay(content=content))

        btn = discord.ui.Button(
            label="Create",
            style=discord.ButtonStyle.primary,
            custom_id=f"plugin:support_threads:create_thread:{self.config.threads_channel_id}",
        )
        btn.callback = self.create_thread_callback
        container.add_item(discord.ui.ActionRow(btn))

        view.add_item(container)

        return view
    
    def simple_title_view(self, *args, color: discord.Color | None = None) -> discord.ui.LayoutView:
        """Create a Discord UI container inside a view"""
        view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container(accent_color=color)

        for item in args:
            container.add_item(item)

        view.add_item(container)
        return view

    async def create_view_message(
        self, channel: discord.TextChannel
    ) -> discord.Message:
        """Create the view message in the specified channel."""

        # Try purge
        try:
            await channel.purge(limit=100)
        except discord.Forbidden:
            self.plugin.logger.warning(
                f"Missing permissions to purge messages in channel {channel.id} for support thread view message."
            )
        except discord.HTTPException as e:
            self.plugin.logger.error(
                f"Failed to purge messages in channel {channel.id} for support thread view message: {e}"
            )

        try:
            message = await channel.send(view=self.title_view())
            return message
        except discord.Forbidden:
            self.plugin.logger.error(
                f"Missing permissions to send messages in channel {channel.id} for support thread view message."
            )
            raise

    async def auto_update_view_message(self) -> discord.Message | None:
        """Automatically update the view message if it doesn't exist."""
        if self.config.view_message_id is not None:
            try:
                channel = self.channel
                if channel is None:
                    self.plugin.logger.error(
                        f"Support threads channel {self.config.threads_channel_id} not found for guild {self.config.guild_id}."
                    )
                    return

                message = await channel.fetch_message(self.config.view_message_id)
                return message  # Message exists, no need to update
            except discord.NotFound:
                pass  # Message not found, will create a new one

        channel = self.channel
        if channel is None:
            self.plugin.logger.error(
                f"Support threads channel {self.config.threads_channel_id} not found for guild {self.config.guild_id}."
            )
            return

        message = await self.create_view_message(channel)
        self.config.view_message_id = message.id
        await self.config.save()
        return message

    async def init(self) -> None:
        """Initialize the support thread instance."""

        message = await self.auto_update_view_message()
        if message:
            self.fw.bot.add_view(self.title_view(), message_id=message.id)
    
    async def get_existing_threads(self, channel: discord.TextChannel, member: discord.Member) -> list[discord.Thread]:
        """Check for existing support threads by the user in the given channel, and verify they can actually access them."""
        
        existing_threads = []
        for thread in channel.threads:
            if thread.archived or thread.locked:
                continue
            if thread.name.endswith(f"||{member.id}"):
                # Verify user can access the thread
                try:
                    await thread.fetch_member(member.id)
                except discord.NotFound:
                    self.plugin.logger.info(f"User {member.id} cannot access thread {thread.id}, closing it.")
                    await self.close_thread(thread, reason="This support thread has been closed because the creator cannot access it.")
                    continue
                
                existing_threads.append(thread)
        return existing_threads

    async def create_thread_callback(self, interaction: discord.Interaction) -> None:
        """Callback for creating a support thread."""
        await interaction.response.defer(thinking=True, ephemeral=True)

        channel = interaction.channel
        if channel is None:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Error",
                    description="Could not find the channel to create a support thread in.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        
        # Search for existing threads by this user
        existing_threads = await self.get_existing_threads(channel, interaction.user)
        if existing_threads:
            await interaction.followup.send(
                embed=discord.Embed(
                    title=f"⚠️ Thread Exists - {', '.join(thread.mention for thread in existing_threads)}",
                    description="You already have an open support thread.",
                    color=discord.Color.orange(),
                ),
                ephemeral=True,
            )
            return

        mention_role = None
        if self.config.support_role_id:
            mention_role = interaction.guild.get_role(self.config.support_role_id)
            
        thread_channel = await channel.create_thread(name=f"{interaction.user.name}||{interaction.user.id}", type=discord.ChannelType.private_thread, invitable=False)
        try:
            text = interaction.user.mention + (f" -> {mention_role.mention}" if mention_role else "") + ": New support thread created."
            await thread_channel.add_user(interaction.user)
            await thread_channel.send(
                view=self.simple_title_view(
                    discord.ui.TextDisplay(content=text),
                    color=discord.Color.green(),
                )
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Error",
                    description="Could not add you to the support thread due to missing permissions.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        
        await interaction.followup.send(
            embed=discord.Embed(
                title="✅ Thread Created",
                description=f"Visit it here: {thread_channel.mention}",
                color=discord.Color.green(),
            ),
            ephemeral=True,
        )
        
        
    async def handle_thread_member_leave(self, thread: discord.Thread, member: discord.Member) -> None:
        """Handle a member leaving a support thread."""
        
        thread_creator = thread.name.split("||")[-1]
        if str(member.id) != thread_creator:
            return  # Not the thread creator leaving
        
        await self.close_thread(thread, reason="The thread creator has left the thread.")
        
    async def delete_view_message(self) -> None:
        """Delete the view message associated with this support thread instance."""
        if self.config.view_message_id is None:
            return
        
        channel = self.channel
        if channel is None:
            self.plugin.logger.error(
                f"Support threads channel {self.config.threads_channel_id} not found for guild {self.config.guild_id}."
            )
            return
        
        try:
            message = await channel.fetch_message(self.config.view_message_id)
            await message.delete()
        except discord.NotFound:
            pass  # Message already deleted
        except discord.Forbidden:
            self.plugin.logger.error(
                f"Missing permissions to delete view message {self.config.view_message_id} in channel {channel.id}."
            )
            
    async def close_thread(self, thread: discord.Thread, reason: str) -> None:
        """Force close a support thread.
        
        Args:
            thread: The thread to close
            reason: The reason for closing the thread
        """
        try:
            # Send notification
            await thread.send(view=self.simple_title_view(
                discord.ui.TextDisplay(content=reason),
                color=discord.Color.red(),
            ))

            # Rename the thread before archiving it
            if not thread.archived:
                await thread.edit(name=f"{thread.name}-closed")

            # Archive and lock the thread
            await thread.edit(archived=True, locked=True)
        except discord.Forbidden:
            self.plugin.logger.error(
                f"Missing permissions to force close support thread {thread.id} in guild {thread.guild.id}."
            )
            raise
        except discord.HTTPException as e:
            self.plugin.logger.error(
                f"Failed to force close support thread {thread.id} in guild {thread.guild.id}: {e}"
            )
            raise
            
    async def create_thread_for_user(self, user: discord.Member, created_by: discord.Member) -> discord.Thread | None:
        """Create a support thread on behalf of a user.
        
        Args:
            user: The user to create the thread for
            created_by: The member creating the thread on behalf of the user
            
        Returns:
            The created thread, or None if creation failed
        """
        channel = self.channel
        if channel is None:
            self.plugin.logger.error(
                f"Support threads channel {self.config.threads_channel_id} not found for guild {self.config.guild_id}."
            )
            return None
        
        mention_role = None
        if self.config.support_role_id:
            mention_role = channel.guild.get_role(self.config.support_role_id)
            
        try:
            thread_channel = await channel.create_thread(
                name=f"{user.name}||{user.id}",
                type=discord.ChannelType.private_thread,
                invitable=False
            )
            
            text = (
                f"{user.mention} " + 
                (f"-> {mention_role.mention}" if mention_role else "") +
                f": Support thread created by {created_by.mention}."
            )
            
            await thread_channel.add_user(user)
            await thread_channel.send(
                view=self.simple_title_view(
                    discord.ui.TextDisplay(content=text),
                    color=discord.Color.green(),
                )
            )
            
            return thread_channel
            
        except discord.Forbidden:
            self.plugin.logger.error(
                f"Missing permissions to create support thread for user {user.id} in guild {channel.guild.id}."
            )
            return None
        except discord.HTTPException as e:
            self.plugin.logger.error(
                f"Failed to create support thread for user {user.id} in guild {channel.guild.id}: {e}"
            )
            return None