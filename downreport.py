import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio

import dotenv
import os


class DownReport(commands.Bot):
    def __init__(self, token: str, report_channel: int):
        super().__init__(command_prefix="dd:", intents=discord.Intents.all())
        self.channel = report_channel
        self.token = token

    def report(
        self, message: str, title: str = None, msg_type: str = "info", cog: str = None
    ):
        self.log = self.Logger(self.channel, message, title, msg_type, cog)
        print("[Down Report] Starting up warning report")
        self.run(self.token)
        print("[Down Report] Done")

    async def on_ready(self):
        
        await self.log.log_saved(self)
        print("[Down Report] Done, shutting down")
        await asyncio.sleep(1)
        await self.close()

    class Logger:
        def __init__(
            self,
            channel: int,
            message: str = None,
            title: str = None,
            msg_type: str = "info",
            cog: str = None,
        ):
            self.channel = channel
            self.message = message
            self.title = title
            self.msg_type = msg_type
            self.cog = cog

        async def create_embed(
            self,
            message: str,
            title: str = None,
            msg_type: str = "info",
            cog: str = None,
        ):

            if msg_type == "error":
                color = discord.Color.red()
            elif msg_type == "success":
                color = discord.Color.green()
            elif msg_type == "warn":
                color = discord.Color.orange()
            else:
                color = discord.Color.blurple()
            embed = discord.Embed(
                title=f"[{msg_type.upper()}] {title}",
                description=message,
                color=color,
            )
            embed.set_author(name=cog)
            embed.set_footer(text="Powered by Jerry Bot")
            return embed

        # Send a log message
        async def log(
            self,
            bot: commands.Bot,
            message: str,
            title: str = None,
            msg_type: str = "info",
            cog: str = None,
        ):
            self.message = message
            self.title = title
            self.msg_type = msg_type
            self.cog = cog
            channel = bot.get_channel(self.channel)
            embed = await self.create_embed(message, title, msg_type, cog)
            await channel.send(
                ("@everyone" if msg_type == "error" else ""), embed=embed
            )

        async def log_saved(self, bot: commands.Bot):
            await self.log(bot, self.message, self.title, self.msg_type, self.cog)
