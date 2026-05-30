"""Main Module for PollRoles"""

# squid_core imports
import discord
from squid_core import Plugin, PluginCog, Framework

# local imports
from .models import Poll
from .cog import PollRolesCog


class PollRoles(Plugin):
    """PollRoles Plugin."""

    def __init__(self, framework: Framework):
        super().__init__(framework)

        self.polls: dict[tuple[int, int, int], Poll] = {}
        self.cog: PollRolesCog | None = None

    async def load(self):
        """Load the PollRoles Plugin."""
        try:
            await self.load_cache()
        except Exception as e:
            self.logger.error(f"Failed to load PollRoles Plugin: {e}")
        self.cog = PollRolesCog(self, self)
        await self.framework.bot.add_cog(self.cog)

    async def unload(self):
        """Unload the PollRoles Plugin."""
        if self.cog:
            await self.framework.bot.remove_cog(self.cog.qualified_name)

    async def load_cache(self):
        """Load active polls from the database."""
        self.polls.clear()
        # Load all active polls from the database
        active_polls = await Poll.filter(active=True).all()
        for poll in active_polls:
            self.polls[(poll.guild_id, poll.channel_id, poll.message_id)] = poll

    def get_poll(self, guild_id: int, channel_id: int, message_id: int) -> Poll | None:
        """Get a poll by its guild, channel, and message IDs."""
        return self.polls.get((guild_id, channel_id, message_id))

    def add_poll(self, poll: Poll):
        """Add a poll to the in-memory cache."""
        if not poll.active:
            return
        self.polls[(poll.guild_id, poll.channel_id, poll.message_id)] = poll

    def remove_poll(
        self, guild_id: int, channel_id: int, message_id: int
    ) -> Poll | None:
        """Remove a poll from the in-memory cache, returning the removed poll if it existed."""
        return self.polls.pop((guild_id, channel_id, message_id), None)

    async def close_poll(self, guild_id: int, channel_id: int, message_id: int) -> bool:
        """Close a poll, marking it as inactive and removing it from the cache. Returns True if a poll was closed, False if no poll was found."""
        poll = self.get_poll(guild_id, channel_id, message_id)
        if poll:
            poll.active = False
            poll.live_mode = False
            await poll.save()
            self.remove_poll(guild_id, channel_id, message_id)
            self.logger.info(f"Closed poll {poll.id} in guild {poll.guild_id}")
            return True
        return False
    
    async def get_inactive_poll(self, guild_id: int, channel_id: int, message_id: int) -> Poll | None:
        """Get a poll by its guild, channel, and message IDs, including inactive polls."""
        poll = self.get_poll(guild_id, channel_id, message_id)
        if poll:
            return poll
        return await Poll.filter(guild_id=guild_id, channel_id=channel_id, message_id=message_id).first()

    async def process_role_updates(
        self,
        poll: Poll,
        new_object: discord.Poll,
        user_id: int | None,
        answer_id: int | None = None,
    ):
        """Process a poll, reading poll object and diffing to apply role updates. Filter by user_id if provided otherwise process all votes."""

        guild = new_object.message.guild if new_object.message else None
        if not guild:
            raise ValueError("Poll message is not in a guild.")

        self.logger.info(
            f"Processing role updates for poll in {guild} {new_object.message.channel.id if new_object.message else 'Unknown Channel ID'} for user_id {user_id if user_id else 'ALL'}"
        )

        votes: dict[discord.User | discord.Member, list[str]] = {}
        found_user = False
        answer = new_object.get_answer(answer_id) if answer_id else None
        for option in [answer] if answer else new_object.answers:
            async for voter in option.voters():
                if user_id and voter.id != user_id:
                    continue
                found_user = True
                votes.setdefault(voter, []).append(option.text)
        if not found_user and user_id:
            member = guild.get_member(user_id)
            if member:
                votes[member] = (
                    []
                )  # User has no votes but we want to process them anyway

        self.logger.debug(f"Votes to process: {votes}")

        # Process role updates based on votes
        poll_options = {option.text for option in new_object.answers}
        for voter, options in votes.items():
            if not isinstance(voter, discord.Member):
                continue  # Voter is not a member of the guild

            # Fetch the current roles of the voter
            current_roles = set(voter.roles)
            roles_to_add = set()
            roles_to_remove = set()

            # Convert options list into a mapping of option text to whether it's selected or not
            options_set = set(options)
            options_status = {
                option: (option in options_set) for option in poll_options
            }

            for option_text, selected in options_status.items():
                role_id = poll.mapping.get(option_text)
                if not role_id:
                    continue  # No role mapped for this option

                role = guild.get_role(role_id)
                if not role:
                    continue  # Role no longer exists

                if selected and role not in current_roles:
                    roles_to_add.add(role)
                elif not selected and role in current_roles:
                    roles_to_remove.add(role)

            # Apply role updates
            try:
                if roles_to_add:
                    await voter.add_roles(*roles_to_add, reason="Poll role update")
                    self.logger.info(
                        f"Added roles {[role.name for role in roles_to_add]} to user {voter} in guild {guild.name}."
                    )
                if roles_to_remove:
                    await voter.remove_roles(
                        *roles_to_remove, reason="Poll role update"
                    )
                    self.logger.info(
                        f"Removed roles {[role.name for role in roles_to_remove]} from user {voter} in guild {guild.name}."
                    )
            except discord.Forbidden:
                self.logger.warning(
                    f"Missing permissions to update roles for user {voter.id} in guild {guild.id}."
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to update roles for user {voter.id} in guild {guild.id}: {e}"
                )
