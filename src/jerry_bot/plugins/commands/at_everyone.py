"""At everyone command logic"""

from enum import Enum

import discord
import regex as re
from discord import app_commands
from squid_core import PluginCog

MENTION_TOKENIZER = re.compile(r"\(|\)|[^\s()]+")
IS_DISCORD_MENTION = re.compile(r"<@(\d+)>|<@&(\d+)>")

class MentionMode(Enum):
    Interaction = "Interaction (Followup)"
    Message = "Message (Send as bot)"
    Ephemeral = "Ephemeral (Copyable)"


def tokenize(query: str) -> list[str]:
    return MENTION_TOKENIZER.findall(query)


def parse(tokens: list[str], parts: list[str]) -> bool:
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def eat():
        nonlocal pos
        t = tokens[pos]
        pos += 1
        return t

    def expr():
        v = term()
        while peek() == "or":
            eat()
            v = v or term()
        return v

    def term():
        v = factor()
        while peek() == "and":
            eat()
            v = v and factor()
        return v

    def factor():
        if peek() == "not":
            eat()
            return not factor()
        if peek() == "(":
            eat()
            v = expr()
            eat()  # consume ")"
            return v
        return eat() in parts

    return expr()


def match_query(query: str, parts: list[str]) -> bool:
    """
    Match a query against a list of parts.
    The query can contain 'and', 'or', 'not' and parentheses.
    """
    try:
        return parse(tokenize(query), parts)
    except IndexError:
        return False  # Invalid query


class StaticCommandAtEveryoneCog(PluginCog):

    @app_commands.command(
        name="at-everyone",
        description="[Commands] Mentions everyone in the server, user by user.",
    )
    @app_commands.describe(
        yes="Confirm you want to do this, which you probably don't.",
        mention="Any of: @here @bot @person @user @role @platform @online @offline @activity:name, with and/or/not/()",
        mode="How to send the mentions",
        maximum="Maximum number of users to mention. 0 for no limit.",
    )
    @app_commands.guild_install()
    @app_commands.guild_only()  # No dms
    @app_commands.default_permissions(mention_everyone=True)
    async def at_everyone_command(
        self,
        interaction: discord.Interaction,
        mention: str,
        yes: bool = False,
        maximum: int = 0,
        mode: MentionMode = MentionMode.Ephemeral,
    ):
        """
        Mention users in the server, user by user, with smart filtering.
        """


        if not await self._check_permissions(interaction, mode == MentionMode.Ephemeral or yes):
            return

        await interaction.response.defer(
            thinking=True, ephemeral=mode != MentionMode.Interaction
        )

        members = await self._scan_members(interaction.guild, mention, maximum)
        
        try:
            await self._send_mentions(interaction, members, mode)
        except discord.Forbidden:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Permission Error",
                    description="I don't have permission to send messages in this channel.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="HTTP Error",
                    description=f"An error occurred while sending messages: {e}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

    @app_commands.command(
        name="tags-for",
        description="[Commands] Get the tags for a user, which can be used in the at-everyone command.",
    )
    @app_commands.describe(
        user="The user to get the tags for.",
    )
    @app_commands.guild_install()
    @app_commands.guild_only()  # No dms
    async def tags_for_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ):
        """
        Get the tags for a user, which can be used in the at-everyone command.
        """
        
        if not await self._check_permissions(interaction, True):
            return

        tags = self._tags_for_member(interaction.guild.get_member(user.id) or user)
        
        tags = [
            f"`{tag}`" if not IS_DISCORD_MENTION.match(tag) else tag for tag in tags
        ]
        
        embed = discord.Embed(
            title=f"Tags for {user.display_name}",
            description="- " + "\n- ".join(tags),
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    async def _check_permissions(
        self, interaction: discord.Interaction, yes: bool
    ) -> bool:
        """
        Check if the user has the required permissions to use the command.
        """

        async def _error_response(title: str, description: str):
            await interaction.response.send_message(
                "",
                embed=discord.Embed(
                    title=title,
                    description=description,
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )

        if not await self.plugin.fw.perms.interaction_check(interaction):
            return False
        
        if interaction.guild is None:
            await _error_response(
                "Guild Only",
                "This command can only be used in a server.",
            )
            return False

        if not yes:
            await _error_response(
                "Confirmation Required",
                "You must confirm that you want to do this by setting `yes` to `True`. This is a safety measure to prevent accidental mass mentions.",
            )
            return False

        if not isinstance(interaction.user, discord.Member):
            await _error_response(
                "Invalid User",
                "This command can only be used by server members.",
            )
            return False

        if not interaction.user.guild_permissions.mention_everyone:
            await _error_response(
                "Permission Required",
                "You need the `Mention Everyone` permission to do this command without a role filter. Technically this is 100% still possible since Discord only cares if *I* have the permission, but I'm not going to allow that because that would not be nice.",
            )
            return False

        return True

    async def _scan_members(
        self, guild: discord.Guild, mention: str, maximum: int
    ) -> list[discord.Member]:
        """
        Scan the members of the server and return a list of members that match the mention filter.
        """

        matched_members = []

        if guild.chunked:
            members = guild.members
        else:
            members = await guild.chunk(cache=True)

        for member in members:
            tags = self._tags_for_member(member)

            if match_query(mention, tags):
                matched_members.append(member)

            if maximum > 0 and len(matched_members) >= maximum:
                break

        return matched_members

    def _tags_for_member(self, member: discord.Member) -> list[str]:
        """
        Get the tags for a member.
        """
        tags = [member.mention]

        if member.bot:
            tags.append("@bot")
        else:
            tags.append("@person")
            if member.status != discord.Status.offline:
                tags.append("@here")
            tags.append(f"@{member.status.value}")

            if member.desktop_status != discord.Status.offline:
                tags.append("@desktop")
            elif member.mobile_status != discord.Status.offline:
                tags.append("@mobile")
            elif member.web_status != discord.Status.offline:
                tags.append("@web")

            for activity in member.activities:
                if isinstance(activity, discord.CustomActivity):
                    continue
                
                if "@activity" not in tags:
                    tags.append("@activity")

                if activity.name:
                    tags.append(f"@activity:{activity.name.lower().replace(' ', '_')}")

        for role in member.roles:
            tags.append(role.mention)

        return tags
    
    async def _send_mentions(
        self, interaction: discord.Interaction, members: list[discord.Member], mode: MentionMode
    ):
        """
        Send the mentions to the channel.
        """
        
        if not members:
            await interaction.followup.send(
                "🦗",
                ephemeral=True,
            )
            return
        
        chunks = self._compress_mentions(
            [member.mention for member in members], max_length=2000
        )
        
        if mode == MentionMode.Interaction:
            for chunk in chunks:
                await interaction.followup.send(chunk)
        elif mode == MentionMode.Message and isinstance(interaction.channel, discord.TextChannel):
            for chunk in chunks:
                await interaction.channel.send(chunk)
            await interaction.followup.send(
                "👍",
                ephemeral=True,
            )
        elif mode == MentionMode.Ephemeral:
            for chunk in chunks:
                await interaction.followup.send(chunk, ephemeral=True)

    def _compress_mentions(
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


if __name__ == "__main__":
    query: str = input("test > ")
    print(
        match_query(
            query,
            [
                "<@814724669470408766>",
                "@everyone",
                "<@&1286854686074470400>",
                "<@&1286854887568572466>",
            ],
        )
    )
