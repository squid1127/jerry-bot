# Packages
import discord
from discord import app_commands
from discord.ext import commands
import logging

# squid-core
import core

class GuildStuff(commands.Cog):
    """A experimental cog for finding guild stats and other stuff"""

    def __init__(self, bot: core.Bot):
        self.bot = bot
        self.logger = logging.getLogger("jerry.guild_stuff")

    @app_commands.command(
        name="server",
        description="[Experimental] Get information about this guild (server)",
    )
    @app_commands.guild_only()
    @app_commands.guild_install()
    async def guild_info(self, interaction: discord.Interaction):
        self.logger.info(f"Guild info requested for {interaction.guild.name}")
        guild = interaction.guild

        # Guild status
        guild_id = guild.id
        guild_name = guild.name
        guild_owner = guild.owner
        guild_members = guild.member_count
        guild_channels = len(guild.channels)
        guild_roles = len(guild.roles)

        self.logger.info(
            f"Guild {guild_name} ({guild_id}) has {guild_members} members and is owned by {guild_owner}"
        )

        embed = discord.Embed(
            title="Server Information",
            description=f"Here is some information about the server {guild_name} ({guild_id})\n\nAnalyzing...",
            color=discord.Color.yellow(),
        )
        embed.add_field(name="Owner", value=guild_owner.mention, inline=False)
        embed.add_field(name="Members", value=guild_members, inline=False)
        embed.add_field(name="Channels", value=guild_channels, inline=False)
        embed.add_field(name="Roles", value=guild_roles, inline=False)
        embed.set_footer(text="Powered by Jerry Bot")
        try:
            if guild.icon.url is None:
                raise AttributeError
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
        except AttributeError:
            embed.set_author(name=guild.name)
        await interaction.response.send_message(embed=embed)

        # Advanced status
        # Count messages :)
        self.logger.info(f"Listing members...")
        members_messages = {}
        total_messages = 0
        total_characters = 0
        total_spaces = 0
        for member in guild.members:
            members_messages[member] = 0
            self.logger.debug(f"Found member {member.name}")

        self.logger.info(f"Counting messages...")

        for channel in guild.text_channels:
            self.logger.info(f"Counting messages in {channel.name}")
            try:
                async for message in channel.history(limit=None):
                    if message.author not in members_messages:
                        self.logger.debug(
                            f"Skipping message from {message.author.name}; not in member list"
                        )
                        continue
                    members_messages[message.author] += 1
                    total_messages += 1
                    message_content = message.content
                    total_characters += len(message_content)
                    total_spaces += message_content.count(" ")
                    self.logger.debug(
                        f"Found message from {message.author.name}. That makes {members_messages[message.author]} messages from them and {total_messages} total messages."
                    )
            except discord.Forbidden:
                self.logger.info(
                    f"Skipping channel {channel.name}; missing permissions"
                )

        self.logger.info(f"Counted {total_messages} messages")

        # Top 10 members
        top_members = sorted(members_messages, key=members_messages.get, reverse=True)[
            :10
        ]
        top_members_str = ""
        for member in top_members:
            top_members_str += (
                f"1. {member.name}: {members_messages[member]} messages\n"
            )

        self.logger.info(f"Top 10 members: \n{top_members_str}")

        # Send the message
        embed.description = (
            f"Here is some information about the guild {guild_name} ({guild_id})"
        )
        embed.add_field(name="Top 10 Members", value=top_members_str, inline=False)
        embed.add_field(name="Total Messages", value=total_messages, inline=False)
        embed.add_field(
            name="Total Characters In Messages", value=total_characters, inline=False
        )
        embed.add_field(
            name="Approximate Number of Times People Pushed Spacebar",
            value=f"{total_spaces}! Why did I count this? Idek",
            inline=False,
        )

        embed.color = discord.Color.green()

        await interaction.edit_original_response(embed=embed)

    async def cog_status(self) -> str:
        return "Ready"