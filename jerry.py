"""
Jerry-Bot
~~~~~~~~~~~~~~~~~~~
The bot designed specifically for LBUSD Drone Soccer Discord and other of squid1127's personal servers.

:license: MIT, see LICENSE for more details.
"""

# Packages & Imports
# Discord Packages
import discord
from discord.ui import Select, View, Button
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, Literal  # For command params
from datetime import timedelta, datetime  # For timeouts & timestamps
from enum import Enum  # For enums (select menus)

# Async Packages
import asyncio
import aiohttp
import aiomysql
import google.api_core
import tabulate  # For tabular data
import cryptography  # For database encryption

# For web frontend
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# For random status
import random

# Downtime warning
import downreport

# Regular Expressions
import re

# Google Gemini client
import google.generativeai as gemini
import google.api_core.exceptions as gemini_selling
from PIL import Image

# Core bot
import core

class Jerry(core.Bot):
    def __init__(self, discord_token: str, gemini_token: str, shell_channel: int, **kwargs):
        super().__init__(token=discord_token, name="jerry", shell_channel=shell_channel, **kwargs)
        self.gemini_token = gemini_token
        
        asyncio.run(self.load_cogs())

    # Load cogs
    async def load_cogs(self):
        self.add_cog(JerryGemini(self))

class JerryGemini(commands.Cog):
    def __init__(self, bot: Jerry):
        self.bot = bot
        gemini.configure(api_key=self.bot.gemini_token)
        self.model = gemini.GenerativeModel(
            "gemini-1.5-flash",
            generation_config=gemini.types.GenerationConfig(
                top_p=0.95,
                top_k=40,
                temperature=1.0,
            ),
            safety_settings={
                "HARASSMENT": "BLOCK_NONE",
                "HATE": "BLOCK_NONE",
                "SEXUAL": "BLOCK_NONE",
                "DANGEROUS": "BLOCK_NONE",
            },
        )

    @commands.Cog.listener()
    async def on_ready(self):
        print("[Gemini] Ready")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        if (
            message.channel.id != 1293430080328171530
        ):  # TODO: Make this a config variable
            return

        # Typing indicator
        await message.channel.typing()

        print(f"[Gemini] Message received {message.content}")

        if not hasattr(self, "chat") or message.content.lower() == "~reset":
            print("[Gemini] Chat not initialized, initializing...")
            self.chat = self.model.start_chat()
            if message.content.lower() == "~reset":
                await message.channel.send("Chat reset.")
                return

        if message.content.lower().startswith("~prompt "):
            message.content = "~prompt ".join(message.content.split(" ")[1:])
            promptDebug = True
        else:
            promptDebug = False

        # Send the message to the model
        try:
            message_prompt = await self._create_prompt(message)
            message_send = (
                f"{message_prompt}\n\nIncoming Message:\n```\n{message.content}\n```"
            )

            # Check for replies
            if message.reference:
                reply = await message.channel.fetch_message(
                    message.reference.message_id
                )
                print(f"[Gemini] Reply detected: {message.reference.resolved.content}")
                message_send = f"{message_prompt}\n\nIncoming Reply Message:\n```\n{message.content}\n```\nReplying to {reply.author.display_name}:\n```\n{reply.content}\n```"

            if message.attachments:
                # Check if the attachment is an image
                image = await self._handle_attachment(message)
                if image:
                    print(f"[Gemini] Image processed: {image}")
                    response = await self.chat.send_message_async(
                        [image, message_send],
                    )
            else:
                if promptDebug:
                    await message.channel.send(f"## Prompt\n{message_send}")
                    return

                print(f"[Gemini] Sending message: {message.content}")
                response = await self.chat.send_message_async(
                    message_send,
                )
            # response = await self.model.generate_content_async(
            #     message.content, generation_config=self.model_config,
            # )
        except gemini_selling.ResourceExhausted:
            await message.channel.send(
                "I'm tired, let me rest for a bit. (Resource exhausted)"
            )
            print("[Gemini] Resource exhausted")
            return

        # Internal command
        if response.text.startswith("~internal"):
            print("[Gemini] Internal command detected")
            command = " ".join(response.text.split(" ")[1:])
            commandResult = await self._internal_command(command)
            # Send back to the ai
            message_send = f"{message_prompt}\n\nExecuted Internal Command: {command}\nResult:\n```\n{commandResult}\n``` You will now respond to the user."
            response = await self.chat.send_message_async(message_send)

        # Send the response
        await message.channel.send(response.text)

    async def _internal_command(self, command: str):
        if command == "reset":
            self.chat = self.model.start_chat()
            print("[Gemini] Internal command: Chat reset.")
            return "Chat reset."

    async def _create_prompt(self, message: discord.Message):
        message_prompt = f"""You are Jerry, a discord AI chatbot.

Your name is Jerry, your AI's character is displayed and characterized as a red octopus, your emoji and avatar is <:jerry:1284336293811327080> if anyone asks

The user id of the member who sent the message is included in the request, feel free to use an @mention in place of their name. Mentions are formed like this: <@user id>. 

You are here to be helpful as well as just an AI friend. You are currently in a discord channel. You are talking to a user. They are called {message.author.display_name} and can be mentioned as {message.author.mention}. To send a message/reply use ~send <message>. To reset the chat use ~internal reset. If a command is not specified, an error will be thrown."""

        return message_prompt

    async def _handle_attachment(self, message: discord.Message):
        try:
            if len(message.attachments) > 1:
                await message.channel.send(
                    "Notice: Only one attachment is supported; the first attachment will be used."
                )
            print(f"[Gemini] Attachment found: {message.attachments[0].filename}")
            if (
                message.attachments[0]
                .filename.lower()
                .endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
            ):
                # Download the image
                print(f"[Gemini] Downloading image: {message.attachments[0].filename}")
                fileName = f"./images/{message.attachments[0].filename}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(message.attachments[0].url) as resp:
                        # Save the image
                        with open(fileName, "wb") as f:
                            f.write(await resp.read())

                        # Process the image
                        image = Image.open(fileName)
                        image = image.convert("RGB")
                        image.save(fileName)
                        print(f"[Gemini] Image saved: {fileName}")

                    image = Image.open(fileName)
                    return image

        except Exception as e:
            print(f"[Gemini] Error processing attachment: {e}")
            return None

    async def shell_callback(
        self, command: str, query: list, shell_command: core.ShellCommand
    ):
        if command == "gemini":
            await shell_command.info(
                "Now entering Gemini mode.", title="Entering Gemini Mode"
            )
            self.bot.shell.interactive_mode = "gemini"
