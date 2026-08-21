"""At everyone command logic"""

from enum import Enum
import discord
from discord import app_commands
from squid_core import PluginCog, Plugin
import regex as re

ROLE_GROUP = re.compile(r"^\(\s*(.*?)\s*\)$")
ROLE_SPLIT_OR = re.compile(r"\s*or\s*")
ROLE_SPLIT_AND = re.compile(r"\s*and\s*")

class MentionMode(Enum):
    Interaction = "Interaction (Followup)"
    Message = "Message (Send as bot)"
    Ephemeral = "Ephemeral (Copyable)"


class StaticCommandAtEveryoneCog(PluginCog):
    @app_commands.command(
        name="at-everyone",
        description="[Commands] Mentions everyone in the server, user by user.",
    )
    @app_commands.describe(
        yes="Confirm you want to do this, which you probably don't.",
        mention="Who to mention, can be '@everyone', '@here', '@formatted role', an auto-condition",
        bots="Include bots",
        mode="How to send the mentions",
    )
    @app_commands.guild_install()
    @app_commands.guild_only()  # No dms
    @app_commands.default_permissions(mention_everyone=True)
    async def at_everyone_command(
        self,
        interaction: discord.Interaction,
        mention: str,
        yes: bool = False,
        bots: bool = False,
        mode: MentionMode = MentionMode.Ephemeral,
    ):
        """
        Mention users indivisually
        """
        
        
    def parse_query(self, query: str) -> list:
        """Determine the mention parts from a query"""
        
        if not ROLE_GROUP.match(query):
            return [query]
        
        results = []
        current_list = results
        while True:
            # Split to group
            match = ROLE_GROUP.search(query) 
            if match:
                query=match.group(1)
            else:
                break
            
            for item in ROLE_SPLIT_OR.split(query):
                current_list.append(item)
                        
        return results
        
if __name__== "__main__":
    query:str = input("test > ")
    print(StaticCommandAtEveryoneCog.parse_query(None, query))  # pyright: ignore[reportArgumentType]
