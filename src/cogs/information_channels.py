# Packages
import discord
from discord import app_commands
from discord.ext import commands, tasks
import logging
import datetime

# squid-core
import core

class InformationChannels(commands.Cog):
    def __init__(self, bot: core.Bot, file: str):
        self.bot = bot
        self.files = self.bot.filebroker.configure_cog(  # Filebroker
            "InformationChannels",
            config_file=True,
            config_do_cache=0,
        )
        self.files.init()

        self.bot.shell.add_command(
            "infochannels",
            cog="InformationChannels",
            description="Manage information channels",
        )
        self.bot.shell.add_command(
            "ic",
            cog="InformationChannels",
            description="Manage information channels (alias for infochannels)",
        )

        self.update_task.start()

        self.logger = logging.getLogger("jerry.information_channels")

    async def check_file(self):
        # return True

        contents = self.files.get_config()

        if contents is None or not contents.get("guilds", None):
            if contents is None:
                contents = {}

            self.logger.warning("Guilds key missing, creating...")
            contents["guilds"] = []
            self.files.set_config(contents)

            return True

        guilds = contents["guilds"]

        if not isinstance(guilds, list):
            self.logger.error("Guilds is not a list")
            await self.bot.shell.log(
                "Error: Messages is not a list", "InformationChannels", msg_type="error"
            )
            return False

        return True

    async def check_then_update(self):
        self.logger.info("Checking and updating all channels")
        success = await self.check_file()
        if not success:
            raise Exception("Error initializing")

        contents = self.files.get_config()
        guilds = contents["guilds"]
        for guild in guilds:
            guild["name"] = self.bot.get_guild(guild["id"]).name
            self.logger.debug(
                f"Checking guild {guild.get('name', guild.get('id', 'Unknown'))}"
            )
            for channel in guild["channels"]:
                self.logger.debug(
                    f"Checking channel {channel.get('name', channel.get('id', 'Unknown'))}"
                )
                dc_channel = self.bot.get_channel(channel["id"])
                if dc_channel is None:
                    self.logger.debug(f"Channel {channel} not found")
                    await self.bot.shell.log(
                        f"Channel {channel} not found",
                        "InformationChannels",
                        msg_type="error",
                    )
                    continue

                # Optimize message entry
                self.logger.debug(f"Optimizing messages for {dc_channel.name}")
                for message in channel["messages"]:
                    if message.get("content", None) == None:
                        message["content"] = ""

                channel["name"] = dc_channel.name
                self.logger.debug(
                    f"Found channel {dc_channel.name}, reading messages..."
                )
                dc_channel_as_dict = await self._channel_to_dict(dc_channel)

                self.logger.debug(f"Current messages:\n{dc_channel_as_dict}")
                self.logger.debug(f"Saved messages:\n{channel['messages']}")

                # Check if messages match
                if dc_channel_as_dict != channel["messages"]:
                    self.logger.info(
                        f"Messages do not match in {dc_channel.name}, updating..."
                    )
                    await dc_channel.purge(limit=None)
                    for message in channel["messages"]:
                        if len(message.get("embeds", [])) > 1:
                            raise Exception("Too many embeds")
                        elif len(message.get("embeds", [])) == 1:
                            embed = self._dict_to_embed(message["embeds"][0])
                            await dc_channel.send(
                                content=message.get("content", None), embed=embed
                            )
                        else:
                            await dc_channel.send(content=message.get("content", None))
                    self.logger.info("Messages updated")
                    await self.bot.shell.log(
                        f"Messages in channel {dc_channel.mention} updated",
                        "InformationChannels",
                        msg_type="success",
                    )
                else:
                    self.logger.debug("Messages match")

        self.files.set_config(contents)
        return True

    @commands.Cog.listener()
    async def on_ready(self):
        success = await self.check_file()
        if success:
            self.logger.info("Ready")
        else:
            self.logger.info("Error initializing")

    async def cog_status(self):
        success = await self.check_file()
        if success:
            return "Ready"
        else:
            return "Error initializing"

    async def shell_callback(self, command: core.ShellCommand):
        if command.name in ["infochannels", "ic"]:
            sub_command = command.query.split(" ")[0]
            if sub_command == "update":
                try:
                    await self.check_then_update()
                    await command.log(
                        "All channels updated",
                        "InformationChannels",
                        msg_type="success",
                    )
                except Exception as e:
                    self.logger.error(f"Error updating channels: {e}")
                    await command.log(
                        f"Error updating channels: {e}",
                        "InformationChannels",
                        msg_type="error",
                    )
                return

    async def _channel_to_dict(self, channel: discord.TextChannel):
        messages = []
        async for message in channel.history(limit=None):
            if message.embeds:
                embeds = []
                for embed in message.embeds:
                    embed_dict = {}
                    if embed.title:
                        embed_dict["title"] = embed.title
                    if embed.description:
                        embed_dict["description"] = embed.description
                    if embed.color:
                        embed_dict["color"] = embed.color.value
                    if embed.footer:
                        embed_dict["footer"] = embed.footer.text
                    if embed.author.name:
                        embed_dict["author"] = {"name": embed.author.name}
                        if embed.author.icon_url:
                            embed_dict["author"]["icon_url"] = embed.author.icon_url
                    if embed.fields:
                        embed_dict["fields"] = []
                        for field in embed.fields:
                            embed_dict["fields"].append(
                                {
                                    "name": field.name,
                                    "value": field.value,
                                    "inline": field.inline,
                                }
                            )
                    # Keys in alphabetical order
                    embeds.sort(key=lambda x: x["name"])
                    embeds.append(embed_dict)

                messages.append({"content": message.content, "embeds": embeds})

        # Invert order as discord returns messages in newest-first order
        messages.reverse()

        return messages

    def _dict_to_embed(self, data: dict) -> discord.Embed:
        embed = discord.Embed(
            title=data.get("title", None),
            description=data.get("description", None),
            color=data.get("color", None),
        )
        if data.get("footer", None):
            embed.set_footer(text=data["footer"])
        if data.get("author", None):
            if data["author"].get("icon_url", None):
                embed.set_author(
                    name=data["author"]["name"], icon_url=data["author"]["icon_url"]
                )
            else:
                embed.set_author(name=data["author"]["name"])
        if data.get("fields", None):
            for field in data["fields"]:
                embed.add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", True),
                )

        return embed

    @tasks.loop(time=datetime.time(hour=0, minute=0, second=0))
    async def update_task(self):
        self.logger.info("Checking for updates (Periodic)")
        try:
            await self.check_then_update()
        except Exception as e:
            self.logger.error(f"Error updating channels: {e}")
            await self.bot.shell.log(
                f"Error updating channels during periodic check: {e}",
                "InformationChannels",
                msg_type="error",
            )
        else:
            self.logger.info("Update complete")