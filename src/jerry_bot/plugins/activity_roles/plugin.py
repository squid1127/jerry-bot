"""Main plugin file for ActivityRoles plugin."""

import asyncio
from squid_core import Plugin as PluginBase, PluginCog
from squid_core.framework import Framework
from squid_core.decorators import CLICommandDec
from squid_core.components.cli import CLIContext, EmbedLevel

from .activity import ActivityTracker
from .models.db import ActivityRoleConfig

import discord
from discord import app_commands, datetime
from discord.ext import commands
from discord.ext import tasks

from datetime import timedelta, timezone
from pytimeparse.timeparse import timeparse

def parse_timedelta(time_str: str) -> timedelta:
    """Parse a time string into a timedelta object."""
    seconds = timeparse(time_str)
    if seconds is None:
        raise ValueError(f"Invalid time format: {time_str}")
    return timedelta(seconds=seconds)

class ActivityRolesPlugin(PluginBase):
    """Plugin class for ActivityRoles."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.cog = ActivityRolesCog(self)
        self.activity_tracker = ActivityTracker(
            plugin=self,
            redis_namespace=self.fw.redis.namespace_generator(
                plugin_name=self.name,
                internal=True,
            ),
            redis_ttl=3600
        )
        
    async def load(self) -> None:
        """Load the ActivityRoles plugin."""
        if self.fw.redis.client is None:
            raise RuntimeError("Plugin requires Redis to function.")
        
        await self.fw.bot.add_cog(self.cog)
        self.logger.info("ActivityRoles plugin loaded.")

    async def unload(self) -> None:
        """Unload the ActivityRoles plugin."""
        await self.fw.bot.remove_cog(self.cog.__class__.__name__)

    @CLICommandDec(
        name="activity",
        description="Activity Roles Plugin Commands",
    )
    async def cli(self, ctx: CLIContext):
        """CLI command group for Activity Roles Plugin."""
        subcommand = ctx.args[0] if ctx.args else None
        
        if subcommand == "list":
            # List all guilds with activity role configs
            configs = await ActivityRoleConfig.all()
            if not configs:
                await ctx.respond(
                    title="Activity Roles",
                    description="No guilds configured.",
                    level=EmbedLevel.INFO,
                )
                return
            
            description = ""
            for config in configs:
                guild = self.fw.bot.get_guild(config.guild_id)
                guild_name = guild.name if guild else f"Unknown Guild ({config.guild_id})"
                description += f"**{guild_name}** (ID: {config.guild_id})\n"
                description += f"  Active Role: <@&{config.active_role_id}> ({config.active_role_id})\n"
                description += f"  Inactive Role: <@&{config.inactive_role_id}> ({config.inactive_role_id})\n"
                description += f"  Threshold: {config.activity_threshold}\n\n"
            
            await ctx.respond(
                title="Activity Roles - Configured Guilds",
                description=description,
                level=EmbedLevel.INFO,
            )
            
        elif subcommand == "flush":
            # Execute flush cache task
            try:
                await self.activity_tracker.flush_cache()
                await ctx.respond(
                    title="Activity Cache Flushed",
                    description="Successfully flushed activity cache to database.",
                    level=EmbedLevel.SUCCESS,
                )
            except Exception as e:
                await ctx.respond_exception("Cache Flush Failed", e)
                
        elif subcommand == "update":
            # Execute update roles task
            try:
                await self.cog.update_activity_roles()
                await ctx.respond(
                    title="Activity Roles Updated",
                    description="Successfully updated activity roles for all guilds.",
                    level=EmbedLevel.SUCCESS,
                )
            except Exception as e:
                await ctx.respond_exception("Activity Roles Update Failed", e)
        
        elif subcommand == "redis-test":
            # Test Redis connection
            try:
                pong = await self.fw.redis.client.ping()
                if pong:
                    await ctx.respond(
                        title="Redis Connection Test",
                        description="Successfully connected to Redis server.",
                        level=EmbedLevel.SUCCESS,
                    )
                else:
                    await ctx.respond(
                        title="Redis Connection Test",
                        description="Failed to receive PONG from Redis server.",
                        level=EmbedLevel.ERROR,
                    )
            except Exception as e:
                await ctx.respond_exception("Redis Connection Test Failed", e)
                
        elif subcommand == "user":
            user_id = None
            if len(ctx.args) > 1:
                try:
                    user_id = int(ctx.args[1])
                except ValueError:
                    await ctx.respond(
                        title="User Activity Test",
                        description="Invalid user ID. Please provide a numeric user ID.",
                        level=EmbedLevel.ERROR,
                    )
                    return
            
            if user_id is None:
                await ctx.respond(
                    title="User Activity Test",
                    description="Please provide a user ID.",
                    level=EmbedLevel.ERROR,
                )
                return
            
            # Fetch user activity from Redis
            try:
                key_pattern = f"{self.activity_tracker.redis_namespace}:activity:*:{user_id}"
                keys = await self.fw.redis.client.keys(key_pattern)
                if not keys:
                    await ctx.respond(
                        title="User Activity Test - Cache",
                        description=f"No activity found for user ID {user_id}.",
                        level=EmbedLevel.INFO,
                    )
                else:
                    description = ""
                    for key in keys:
                        timestamp = await self.fw.redis.client.get(key)
                        last_active = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
                        guild_id = int(key.decode().split(":")[-2])
                        guild = self.fw.bot.get_guild(guild_id)
                        guild_name = guild.name if guild else f"Unknown Guild ({guild_id})"
                        description += f"**{guild_name}** (ID: {guild_id}) - Last Active: <t:{int(last_active.timestamp())}:R>\n"
                    
                    await ctx.respond(
                        title=f"User Activity ({user_id}) - Cache",
                        description=description,
                        level=EmbedLevel.INFO,
                    )
            except Exception as e:
                await ctx.respond_exception("User Activity Test Failed", e)
                
            # Fetch user activity from Database
            try:
                entries = await self.activity_tracker.get_user_activity(user_id=user_id)
                if not entries:
                    await ctx.respond(
                        title="User Activity Test - DB",
                        description=f"No database activity found for user ID {user_id}.",
                        level=EmbedLevel.INFO,
                    )
                    return
                
                description = ""
                for entry in entries:
                    guild = self.fw.bot.get_guild(entry.guild_id)
                    guild_name = guild.name if guild else f"Unknown Guild ({entry.guild_id})"
                    description += f"**{guild_name}** (ID: {entry.guild_id}) - Last Active: <t:{int(entry.last_active.timestamp())}:R>, Is Active: {entry.is_active}\n"
                
                await ctx.respond(
                    title=f"User Activity ({user_id}) - DB",
                    description=description,
                    level=EmbedLevel.INFO,
                )
            except Exception as e:
                await ctx.respond_exception("User Activity Database Test Failed", e)
                
        else:
            await ctx.respond(
                title="Activity Roles Plugin",
                description="Available subcommands: **list**, **flush**, **update**, **redis-test**, **user**",
                level=EmbedLevel.INFO,
            )

class ActivityRolesCog(PluginCog):
    """
    Cog class for ActivityRoles.
    """

    def __init__(self, plugin: ActivityRolesPlugin):
        self.plugin: ActivityRolesPlugin = plugin
        self.bot = plugin.fw.bot
        self.logger = plugin.logger
        
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Listener for message events to track user activity."""
        if message.author.bot:
            return
        if message.guild is None:
            return
        await self.plugin.activity_tracker.activity(
            guild_id=message.guild.id,
            user_id=message.author.id,
            last_active=message.created_at
        )
        
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        """Listener for voice state updates to track user activity."""
        if member.bot:
            return
        if before.channel != after.channel:
            await self.plugin.activity_tracker.activity(
                guild_id=member.guild.id,
                user_id=member.id,
                last_active=discord.utils.utcnow()
            )
            
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Listener for member join events to track user activity."""
        if member.bot:
            return
        await self.plugin.activity_tracker.activity(
            guild_id=member.guild.id,
            user_id=member.id,
            last_active=discord.utils.utcnow()
        )
        
    @app_commands.command(name="activity-roles", description="Set/update activity roles configuration.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(
        active_role="Role to assign to active members.",
        inactive_role="Role to assign to inactive members.",
        activity_threshold="Time threshold for activity (e.g., '7d' for 7 days)."
    )
    async def activity_roles(
        self,
        interaction: discord.Interaction,
        active_role: discord.Role,
        inactive_role: discord.Role,
        activity_threshold: str
    ) -> None:
        """Command to set or update activity roles configuration."""
        
        await interaction.response.defer(ephemeral=True)
        try:
            threshold_td = parse_timedelta(activity_threshold)
        except ValueError as e:
            await interaction.followup.send(embed=discord.Embed(title="Parsing Error", description=str(e), color=discord.Color.red()))
            return
        
        await self.plugin.activity_tracker.set_guild_config(
            guild_id=interaction.guild.id,
            active_role_id=active_role.id,
            inactive_role_id=inactive_role.id,
            activity_threshold=threshold_td
        )
        
        await interaction.followup.send(embed=discord.Embed(
            title="Activity Roles Configured",
            description=(
                f"Active Role: {active_role.mention}\n"
                f"Inactive Role: {inactive_role.mention}\n"
                f"Activity Threshold: {activity_threshold}"
            ),
            color=discord.Color.green()
        ))
        
    @activity_roles.error
    async def activity_roles_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """Error handler for activity_roles command."""
        # Check permission errors
        if isinstance(error, app_commands.MissingPermissions):
            response = discord.Embed(
                title="Permission Denied",
                description="You do not have permission to manage roles.",
                color=discord.Color.red()
            )
        else:
            # Unexpected errors
            self.logger.error(f"Error in activity_roles command: {error}")
            response = discord.Embed(
                title="Error",
                description="An error occurred while processing the command.",
                color=discord.Color.red()
            )
            
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=response, ephemeral=True)
        else:
            await interaction.followup.send(embed=response, ephemeral=True)
            
            
    @app_commands.command(name="activity-role-add-all", description="Add all missing members to the tracking database, defaulting them to inactive.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    async def activity_role_add_all(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Command to add all missing guild members to the tracking database as inactive."""
        
        await interaction.response.defer(ephemeral=True)
        
        config = await self.plugin.activity_tracker.get_guild_config(interaction.guild.id)
        if config is None:
            await interaction.followup.send(embed=discord.Embed(
                title="Not Configured",
                description="Activity roles are not configured for this guild. Use /activity-roles to set them up.",
                color=discord.Color.red()
            ))
            return
        
        # Get all non-bot members from the guild
        member_ids = [member.id for member in interaction.guild.members if not member.bot]
        
        try:
            # Add missing members to the database
            added_count = await self.plugin.activity_tracker.add_missing_members(
                guild_id=interaction.guild.id,
                member_ids=member_ids
            )
            
            if added_count == 0:
                await interaction.followup.send(embed=discord.Embed(
                    title="No Missing Members",
                    description="All members are already tracked in the database.",
                    color=discord.Color.blue()
                ))
            else:
                await interaction.followup.send(embed=discord.Embed(
                    title="Members Added",
                    description=f"Successfully added {added_count} missing member(s) to the tracking database as inactive.",
                    color=discord.Color.green()
                ))
        except Exception as e:
            self.logger.error(f"Error adding missing members for guild {interaction.guild.id}: {e}")
            await interaction.followup.send(embed=discord.Embed(
                title="Error",
                description="An error occurred while adding members to the database.",
                color=discord.Color.red()
            ))
        
        
        
    @activity_role_add_all.error
    async def activity_role_add_all_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """Error handler for activity_role_add_all command."""
        # Check permission errors
        if isinstance(error, app_commands.MissingPermissions):
            response = discord.Embed(
                title="Permission Denied",
                description="You do not have permission to manage roles.",
                color=discord.Color.red()
            )
        else:
            # Unexpected errors
            self.logger.error(f"Error in activity_role_add_all command: {error}")
            response = discord.Embed(
                title="Error",
                description="An error occurred while processing the command.",
                color=discord.Color.red()
            )
            
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=response, ephemeral=True)
        else:
            await interaction.followup.send(embed=response, ephemeral=True)
            
    

            
    async def update_activity_roles(self) -> None:
        """Update activity roles for all guilds based on user activity."""
        queue = await self.plugin.activity_tracker.update_queue(discord.utils.utcnow())
        await self._update_activity_roles_worker(queue, rate_limit=2.0)
    
    async def _update_activity_roles_worker(self, queue: asyncio.Queue, rate_limit: float) -> None:
        """Worker to process activity role updates with rate limiting."""
        processed = 0
        errors = 0
        
        while not queue.empty():
            update = await queue.get()
            
            try:
                # Fetch the guild
                guild = self.bot.get_guild(update.guild_id)
                if guild is None:
                    self.logger.warning(f"Guild {update.guild_id} not found, skipping.")
                    errors += 1
                    continue
                
                # Fetch the member
                member = guild.get_member(update.user_id)
                if member is None:
                    self.logger.warning(f"Member {update.user_id} not found in guild {update.guild_id}, skipping.")
                    errors += 1
                    continue
                
                # Fetch the config
                config = await ActivityRoleConfig.get_or_none(guild_id=update.guild_id)
                if config is None:
                    self.logger.warning(f"Config not found for guild {update.guild_id}, skipping.")
                    errors += 1
                    continue
                
                # Get the roles
                active_role = guild.get_role(config.active_role_id)
                inactive_role = guild.get_role(config.inactive_role_id)
                
                if active_role is None or inactive_role is None:
                    self.logger.warning(f"Roles not found for guild {update.guild_id}, skipping.")
                    errors += 1
                    continue
                
                # Update roles based on should_be_active
                if update.should_be_active:
                    # User should be active: add active role, remove inactive role
                    if active_role not in member.roles:
                        await member.add_roles(active_role, reason="User marked as active")
                    if inactive_role in member.roles:
                        await member.remove_roles(inactive_role, reason="User marked as active")
                    update.entry.is_active = True
                    self.logger.debug(f"Marked user {update.user_id} as active in guild {update.guild_id}")
                else:
                    # User should be inactive: add inactive role, remove active role
                    if inactive_role not in member.roles:
                        await member.add_roles(inactive_role, reason="User marked as inactive")
                    if active_role in member.roles:
                        await member.remove_roles(active_role, reason="User marked as inactive")
                    update.entry.is_active = False
                    self.logger.debug(f"Marked user {update.user_id} as inactive in guild {update.guild_id}")
                
                # Save the updated entry to the database
                await update.entry.save()
                processed += 1
                
                # Rate limiting
                await asyncio.sleep(rate_limit)
                
            except discord.Forbidden:
                self.logger.error(f"Missing permissions to manage roles for user {update.user_id} in guild {update.guild_id}")
                errors += 1
            except Exception as e:
                self.logger.error(f"Error processing activity role update for user {update.user_id} in guild {update.guild_id}: {e}")
                errors += 1
        
        self.logger.info(f"Processed {processed} activity role updates with {errors} errors.")
        
    # Tasks
    @tasks.loop(minutes=60)
    async def update_activity_roles_task(self) -> None:
        """Periodic task to update activity roles based on user activity."""
        self.logger.info("Running activity roles update task.")
        await self.update_activity_roles()
    
    @tasks.loop(minutes=15)
    async def flush_activity_cache_task(self) -> None:
        """Periodic task to flush activity cache."""
        self.logger.info("Flushing activity cache.")
        await self.plugin.activity_tracker.flush_cache()
        
    async def cog_load(self) -> None:
        """Start periodic tasks when the cog is loaded."""
        self.flush_activity_cache_task.start()
        
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Start the update activity roles task when the bot is ready."""
        if not self.update_activity_roles_task.is_running():
            self.update_activity_roles_task.start()