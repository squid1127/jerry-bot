# Packages
import discord
from discord import app_commands
from discord.ext import commands
import logging
import aiohttp
import bs4
from enum import Enum

# squid-core
import core


class StaticCommands(commands.Cog):
    """Static commands that don't really do much, including api commands"""

    def __init__(self, bot: core.Bot):
        self.bot = bot

        # self.bot.shell.add_command( Nothing uses shell commands yet
        #     "api",
        #     cog="StaticCommands",
        #     description="Manage API keys",
        # )
        self.logger = logging.getLogger("jerry.staticcommands")

        self.dev_excuses = "http://developerexcuses.com/"

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("Static commands ready")

    async def cog_status(self):
        return "Ready"

    async def shell_callback(self, command: core.ShellCommand):
        if command.name == "api":
            await command.log(
                "This command is not yet implemented (Since no commands require API keys)"
            )
            return

    @app_commands.command(
        name="ping-jerry",
        description="Is Jerry alive?",
    )
    async def ping_command(self, interaction: discord.Interaction):
        # Get latency
        latency = self.bot.latency * 1000
        await interaction.response.send_message(f"Pong! 🏓\nLatency: {latency:.2f}ms")

    @app_commands.command(
        name="help-jerry",
        description="Get help with Jerry",
    )
    @app_commands.guild_install()
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Jerry Bot",
            description="I'm Jerry, a bot created by CubbScratchStudios. I'm designed as a server-specific bot, meaning I have features that are unique to each server I'm in. However, I also have some global features that are available in all servers.",
            color=self.bot.JERRY_RED,
        )

        embed.add_field(
            name="Global Commands",
            value="""Here are some commands that are available in all servers:
- `/ping-jerry` - Check if Jerry is alive
- `/help-jerry` - This command
- `/sticker` - Get a sticker from the CubbScratchStudios sticker pack
- `/sever` - Get server information such as message count by user. Kinda like a leveling bot but includes all time. (Highly experimental)
More to come soon!""",
            inline=False,
        )
        embed.add_field(
            name="Community Server",
            value="Check out the [CubbScratchStudios Bot Community Server](https://je.fr.to/discord-bot-community) for more information about Jerry and other bots, as well as support and discussion. (We're still setting things up, so please be patient!)",
            inline=False,
        )
        embed.add_field(
            name="Splat Bot",
            value="If you want a more general-purpose bot, check out [Splat Bot](https://je.fr.to/splat-bot), a bot that can do a lot of things, including moderation, fun commands, and more!",
        )
        embed.set_footer(
            text="Brought to you by CubbScratchStudios",
            icon_url="https://je.fr.to/static/css_logo.PNG",
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="my-code-sucks",
        description="Helps you with your stupid code",
    )
    async def my_code_sucks_command(self, interaction: discord.Interaction):
        """Gives you a random excuse for your code not working"""
        # Request headers
        headers = {
            "User-Agent": "JerryBot/1.0",
            "Accept": "text/plain",
        }
        await interaction.response.defer(thinking=True)
        async with aiohttp.ClientSession() as session:
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
        mentions = []
        if role:
            members = role.members
        else:
            members = []
            # Force fetch all members
            async for member in guild.fetch_members(limit=None):
                members.append(member)
        if mention_type == self.MentionType.EVERYONE:
            for member in members:
                if not member.bot:
                    mentions.append(member.mention)
        elif mention_type == self.MentionType.HERE:
            for member in members:
                if not member.bot and member.status != discord.Status.offline:
                    mentions.append(member.mention)
        elif mention_type == self.MentionType.USER:
            for member in members:
                if not member.bot and member.status != discord.Status.offline:
                    mentions.append(member.mention)
        return mentions

    def compress_mentions(
        self, mentions: list[str], max_length: int = 2000
    ) -> list[str]:
        chunks = []
        current_chunk = ""
        for mention in mentions:
            if len(current_chunk) + len(mention) + 1 > max_length:
                chunks.append(current_chunk)
                current_chunk = mention
            else:
                if current_chunk:
                    current_chunk += " " + mention
                else:
                    current_chunk = mention
        if current_chunk:
            chunks.append(current_chunk)
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
