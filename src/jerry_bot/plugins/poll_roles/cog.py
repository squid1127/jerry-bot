"""Main Cog for PollRoles Plugin."""

import asyncio
from typing import Protocol
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import timezone, datetime, time

from .models import Poll
from .ui import MessageContainer, generic_error_view, PollManagerView
from .manager_protocol import PollRoleManager

# squid_core imports
from squid_core import PluginCog, Plugin, Framework

VOTE_UPDATE_TIMEOUT_SECONDS = (
    15.0  # Timeout for processing vote updates to prevent hanging on locks
)


class PollContextMenu(app_commands.ContextMenu):
    """Context menu command for managing polls."""

    def __init__(self, manager: PollRoleManager):
        super().__init__(
            name="PollRoles - Manage Poll",
            callback=self.manage_poll,
            allowed_contexts=app_commands.AppCommandContext(
                guild=True, dm_channel=False, private_channel=False
            ),
            allowed_installs=app_commands.AppInstallationType(guild=True, user=False)
        )
        self._manager = manager
        self._live_vote_locks: dict[tuple[int, int, int], asyncio.Lock] = (
            {}
        )  # Locks for live vote processing

    async def manage_poll(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        """Context menu command to manage a poll."""

        dc_poll = message.poll
        if not dc_poll:
            await generic_error_view(
                "This message does not contain a poll.", interaction
            )
            return

        if not (interaction.guild_id and interaction.channel_id):
            await generic_error_view(
                "This command can only be used in a guild.", interaction
            )
            return

        if not await self.check_permissions(interaction):
            await generic_error_view(
                "Insufficient permissions detected.\n**You need:** Manage Channels, Manage Roles\n**Bot needs:** Manage Roles",
                interaction,
            )
            return

        # Check if this poll is in our cache
        poll = await self._manager.get_inactive_poll(
            interaction.guild_id, interaction.channel_id, message.id
        )

        view = PollManagerView(interaction, self._manager, poll, message)
        await view.render()

    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if the user has permissions to manage the poll."""
        if not interaction.guild or not interaction.user:
            return False

        member = interaction.guild.get_member(interaction.user.id)
        if not member:
            return False

        bot_member = interaction.guild.get_member(interaction.application_id)
        if not bot_member:
            return False

        return (
            member.guild_permissions.manage_channels
            and member.guild_permissions.manage_roles
            and bot_member.guild_permissions.manage_roles
        )


class PollRolesCog(PluginCog):
    """Cog for PollRoles Plugin."""

    def __init__(self, plugin: Plugin, manager: PollRoleManager):
        super().__init__(plugin)
        self._manager = manager
        self._manage_poll = PollContextMenu(manager)

    async def cog_load(self):
        """Load the PollRoles Cog."""
        self.fw.bot.tree.add_command(
            self._manage_poll
        )  # Register the context menu command

    async def cog_unload(self):
        """Unload the PollRoles Cog."""
        self.fw.bot.tree.remove_command(
            self._manage_poll.name
        )  # Unregister the context menu command

    def get_poll_lock(
        self, guild_id: int, channel_id: int, message_id: int
    ) -> asyncio.Lock:
        """Get the lock for a specific poll, creating it if it doesn't exist."""
        key = (guild_id, channel_id, message_id)
        if key not in self._manage_poll._live_vote_locks:
            self._manage_poll._live_vote_locks[key] = asyncio.Lock()
        return self._manage_poll._live_vote_locks[key]

    @commands.Cog.listener()
    async def on_raw_poll_vote_add(self, payload: discord.RawPollVoteActionEvent):
        """Listener for when a vote is added to a poll."""
        await self._handle_vote_update(payload)

    @commands.Cog.listener()
    async def on_raw_poll_vote_remove(self, payload: discord.RawPollVoteActionEvent):
        """Listener for when a vote is removed from a poll."""
        await self._handle_vote_update(payload)

    @commands.Cog.listener()
    async def on_ready(self):
        """Start the background task to clean up expired polls when the bot is ready."""
        if not self.cleanup_expired_polls.is_running():
            self.cleanup_expired_polls.start()

    async def _handle_vote_update(self, payload: discord.RawPollVoteActionEvent):
        """Handle a vote update, processing role changes if the poll is active."""
        if not (payload.guild_id and payload.channel_id):
            return  # Not in a guild channel, ignore

        key = (payload.guild_id, payload.channel_id, payload.message_id)

        poll = self._manager.get_poll(*key)
        if not (poll and poll.active and poll.live_mode):
            return  # No active poll found for this message

        # Acquire a lock for this poll to prevent concurrent processing
        lock = self.get_poll_lock(*key)

        async with lock:
            poll = self._manager.get_poll(*key)
            if not poll or not poll.active:
                return  # Poll might have been closed while waiting for the lock

            # Fetch the latest poll object from Discord
            channel = self.fw.bot.get_channel(payload.channel_id)
            if not isinstance(channel, discord.TextChannel):
                return  # Channel is not a text channel

            try:
                message = await channel.fetch_message(payload.message_id)
            except discord.NotFound:
                return  # Message was deleted

            if not message.poll:
                return  # Message no longer has a poll

            try:
                await asyncio.wait_for(
                    self._manager.process_role_updates(
                        poll, message.poll, payload.user_id, payload.answer_id
                    ),
                    timeout=VOTE_UPDATE_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                self.plugin.logger.warning(
                    f"Timeout while processing vote update for poll {poll.id}. This may indicate a performance issue or a deadlock."
                )
            except Exception as e:
                self.plugin.logger.error(
                    f"Error processing role updates for poll {poll.id}: {e}"
                )

    @tasks.loop(time=time(hour=0, minute=0, tzinfo=timezone.utc))
    async def cleanup_expired_polls(self):
        """Background task to clean up expired polls."""
        now = datetime.now(timezone.utc)
        expired_polls = await Poll.filter(active=True, expire_by__lte=now).all()

        for poll in expired_polls:
            try:
                await self._manager.close_poll(
                    poll.guild_id, poll.channel_id, poll.message_id
                )
                self.plugin.logger.info(
                    f"Closed expired poll {poll.id} in guild {poll.guild_id}"
                )
            except Exception as e:
                self.plugin.logger.error(f"Error closing expired poll {poll.id}: {e}")
