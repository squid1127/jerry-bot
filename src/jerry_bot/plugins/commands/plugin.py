"""Main plugin file for Commands plugin."""

from squid_core.plugin_base import Plugin as PluginBase, PluginCog
from squid_core.framework import Framework

from enum import Enum
import aiohttp, bs4
import asyncio

import discord
from discord import app_commands

class CommandsPlugin(PluginBase):
    """Plugin class for Commands."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.cog = StaticCommands(self)

    async def load(self) -> None:
        """Load the Commands plugin."""
        await self.fw.bot.add_cog(self.cog)

    async def unload(self) -> None:
        """Unload the Commands plugin."""
        await self.fw.bot.remove_cog(self.cog.__class__.__name__)


class StaticCommands(PluginCog):
    """
    #! Reused from legacy Jerry Bot + minor modifications

    Static commands that don't really do much, including api commands
    """

    def __init__(self, plugin: CommandsPlugin):
        self.plugin: CommandsPlugin = plugin
        self.bot = plugin.fw.bot
        self.logger = plugin.logger
        self.perms = plugin.fw.perms

        self.dev_excuses = "http://developerexcuses.com/"

        self.cat = "https://cataas.com/cat"
        self.cat_title = "Cataas - Cat as a Service"
        
        self.random = "https://www.random.org/integers"
        
        self.api_command_semaphore = asyncio.Semaphore(2)  # Limit to 2 concurrent API commands
        self._http_session: aiohttp.ClientSession | None = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create a shared HTTP session."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session
    
    async def cog_unload(self):
        """Clean up resources when cog is unloaded."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

    @app_commands.command(
        name="ping-jerry",
        description="Is Jerry alive?",
    )
    async def ping_command(self, interaction: discord.Interaction):
        if not await self.perms.interaction_check(interaction):
            return

        # Get latency
        latency = self.bot.latency * 1000
        await interaction.response.send_message(f"Pong! 🏓\nLatency: {latency:.2f}ms")

    @app_commands.command(
        name="help-jerry",
        description="Get help with Jerry",
    )
    @app_commands.guild_install()
    async def help_command(self, interaction: discord.Interaction):
        if not await self.perms.interaction_check(interaction):
            return

        embed = discord.Embed(
            title="Jerry Bot",
            description="I'm Jerry, a bot created by CubbScratchStudios. I'm designed as a server-specific bot, meaning I have features that are unique to each server I'm in. However, I also have some global features that are available in all servers.",
            color=discord.Color.red(),
        )

        embed.add_field(
            name="Global Commands",
            value="""Here are some commands that are available in all servers:
- `/ping-jerry` - Check if Jerry is alive
- `/help-jerry` - This command
More to come soon!""",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="my-code-sucks",
        description="Helps you with your stupid code",
    )
    async def my_code_sucks_command(self, interaction: discord.Interaction):
        """Gives you a random excuse for your code not working"""
        if not await self.perms.interaction_check(interaction):
            return

        # Request headers
        headers = {
            "User-Agent": "JerryBot/1.0",
            "Accept": "text/plain",
        }
        await interaction.response.defer(thinking=True)
        
        # Semaphore to limit concurrent API commands
        async with self.api_command_semaphore:
            session = await self._get_session()
            async with session.get(self.dev_excuses, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = bs4.BeautifulSoup(html, "html.parser")
                    excuse_tag = soup.find("center")
                    excuse = (
                        excuse_tag.find("a").text
                        if excuse_tag and excuse_tag.find("a")
                        else "No excuse found."
                    )
                    await interaction.followup.send(f"||*{excuse}*||")
                else:
                    await interaction.followup.send(
                        "Sorry, I can't help you. It's just that bad. :P"
                    )

    # Mention command (idk why)
    class MentionType(Enum):
        EVERYONE = "everyone"
        HERE = "here"
        USER = "user"

    class MentionMode(Enum):
        INTERACTION = "Interaction (Followup)"
        MESSAGE = "Message (Send as bot)"
        EPHEMERAL = "Ephemeral (Copyable)"

    async def generate_mention_list(
        self, guild: discord.Guild, mention_type: MentionType, role: discord.Role = None
    ) -> list[str]:
        if role:
            members = role.members
        else:
            # Use guild.members which is cached instead of fetching all members
            # This requires the Members intent to be enabled
            members = guild.members
            if not members:
                # Fallback to fetch if cache is empty (shouldn't happen with proper intents)
                self.logger.warning(
                    "Guild members cache is empty. Fetching members from API (slow). "
                    "Ensure Members intent is enabled."
                )
                members = []
                async for member in guild.fetch_members(limit=None):
                    members.append(member)
        
        # Use list comprehension for better performance
        if mention_type == self.MentionType.EVERYONE:
            mentions = [member.mention for member in members if not member.bot]
        elif mention_type in (self.MentionType.HERE, self.MentionType.USER):
            mentions = [
                member.mention 
                for member in members 
                if not member.bot and member.status != discord.Status.offline
            ]
        else:
            mentions = []
        
        return mentions

    def compress_mentions(
        self, mentions: list[str], max_length: int = 2000
    ) -> list[str]:
        chunks = []
        current_chunk_parts = []
        current_length = 0
        for mention in mentions:
            mention_len = len(mention)
            # Account for the space separator
            needed_length = mention_len + (1 if current_chunk_parts else 0)
            
            if current_length + needed_length > max_length:
                # Start a new chunk
                if current_chunk_parts:
                    chunks.append(" ".join(current_chunk_parts))
                current_chunk_parts = [mention]
                current_length = mention_len
            else:
                current_chunk_parts.append(mention)
                current_length += needed_length
        
        # Add the last chunk
        if current_chunk_parts:
            chunks.append(" ".join(current_chunk_parts))
        return chunks

    @app_commands.command(
        name="at-everyone", description="Mentions everyone in the server, user by user."
    )
    @app_commands.describe(
        yes="Confirm you want to do this, which you probably don't.",
        type="Simple filters for who to mention",
        mode="How to send the mentions",
        role="Filter by a specific role",
    )
    @app_commands.guild_install()  # Cannot be used in a user context (members not available)
    @app_commands.guild_only()  # No dms
    async def at_everyone_command(
        self,
        interaction: discord.Interaction,
        yes: bool = False,
        type: MentionType = MentionType.EVERYONE,
        role: discord.Role = None,
        mode: MentionMode = MentionMode.INTERACTION,
    ):
        """Mentions everyone in the server, user by user."""
        if not await self.perms.interaction_check(interaction):
            return

        if not yes:
            await interaction.response.send_message(
                "",
                embed=discord.Embed(
                    title="Are you sure?",
                    description="Are you sure this is a good idea? You're gonna get banned bro :( Don't care? Then run the command again with `yes` set to `true`.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        if role is None or role.is_default():
            role = None  # No role filter
            # Check permissions
            if not interaction.user.guild_permissions.mention_everyone:
                await interaction.response.send_message(
                    "",
                    embed=discord.Embed(
                        title="Sorry bud",
                        description="You need the `Mention Everyone` permission to do this command without a role filter. Technically this is 100% still possible since Discord only cares if *I* have the permission, but I'm not going to allow that because that would not be nice.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return
        else:
            # Check permissions, need to be able to mention the role
            if (
                not interaction.user.guild_permissions.mention_everyone
                and not role.mentionable
            ):
                await interaction.response.send_message(
                    "",
                    embed=discord.Embed(
                        title="Sorry bud",
                        description="You need the `Mention Everyone` permission to do this command without a role filter. Technically this is 100% still possible since Discord only cares if *I* have the permission, but I'm not going to allow that because that would not be nice.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return
        await interaction.response.defer(
            ephemeral=(mode != self.MentionMode.INTERACTION)
        )
        try:
            mentions = await self.generate_mention_list(interaction.guild, type, role)
            if not mentions:
                await interaction.followup.send("No members to mention.")
                return

            chunks = self.compress_mentions(mentions)
            if mode == self.MentionMode.INTERACTION:
                for chunk in chunks:
                    await interaction.followup.send(chunk)
            elif mode == self.MentionMode.MESSAGE:
                for chunk in chunks:
                    await interaction.channel.send(chunk)
                await interaction.followup.send("✅ Sent all mentions.", ephemeral=True)
            elif mode == self.MentionMode.EPHEMERAL:
                for chunk in chunks:
                    await interaction.followup.send(chunk, ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                "Missing necessary permissions running this command.",
                ephemeral=True,
            )
        except Exception as e:
            self.logger.error(f"Error in at_everyone_command: {e}")
            await interaction.followup.send("Something broke :(", ephemeral=True)

    @app_commands.command(name="cat", description="Sends a random cat image.")
    async def cat_command(self, interaction: discord.Interaction):
        """Sends a random cat image."""

        if not await self.perms.interaction_check(interaction):
            return

        await interaction.response.defer(thinking=True)
        

        async with self.api_command_semaphore:
            # Request headers
            headers = {
                "User-Agent": "JerryBot/1.0",
            }

            # Fetch cat image
            session = await self._get_session()
            async with session.get(self.cat, headers=headers) as response:
                if response.status == 200:
                    data = await response.read()

                else:
                    await interaction.followup.send(
                        "Sorry, I couldn't get a cat image right now."
                    )
                    return

        # Convert to discord file, using BytesIO
        from io import BytesIO

        file = discord.File(BytesIO(data), filename="cat.jpg")

        # Embed
        embed = discord.Embed(color=discord.Color.blue()).set_footer(
            text=f"Images provided by {self.cat_title}"
        )

        await interaction.followup.send(embed=embed, file=file)
    
    @app_commands.command(
        name="yes-no", description="Get a random yes or no answer. Like an 8-ball but simpler."
    )
    async def yes_no_command(self, interaction: discord.Interaction):
        """Responds with a random yes or no answer."""
        if not await self.perms.interaction_check(interaction):
            return
        
        # Use true random from random.org
        await interaction.response.defer(thinking=True)
        
        params = {
            "num": 1,
            "min": 0,
            "max": 1,
            "col": 1,
            "base": 10,
            "format": "plain",
            "rnd": "new",
        }
        try:       
            async with self.api_command_semaphore:
                session = await self._get_session()
                async with session.get(self.random, params=params) as response:
                    if response.status == 200:
                        text = await response.text()
                        result = text.strip()
                        if result == "0":
                            answer = "No."
                        elif result == "1":
                            answer = "Yes."
                        else:
                            raise ValueError("Unexpected response from random.org")
                    else:
                        raise ValueError("Failed to get response from random.org")
                        
        except Exception as e:
            import random
            self.logger.error(f"Error in yes_no_command: {e}")
            answer = random.choice(["Yes.", "No."])
            await interaction.followup.send(f"*{answer}*")
            return
        
        await interaction.followup.send(f"*{answer}*")