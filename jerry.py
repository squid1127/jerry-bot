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

# Auto-reply
import re

# Core bot
import core


class Jerry(core.Bot):
    def __init__(
        self, discord_token: str, gemini_token: str, shell_channel: int, **kwargs
    ):
        super().__init__(
            token=discord_token, name="jerry", shell_channel=shell_channel, **kwargs
        )
        self.gemini_token = gemini_token

        asyncio.run(self.load_cogs())

    # Load cogs
    async def load_cogs(self):
        await self.add_cog(JerryGemini(self))
        await self.add_cog(AutoReply(self))


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
            await self._new_chat()
            if message.content.lower() == "~reset":
                await self._new_chat()
                embed = discord.Embed(
                    title="Chat Reset",
                    description="The chat has been reset; Jerry has forgotten everything :(",
                    color=discord.Color.green(),
                )
                embed.set_footer(text="Powered by Jerry Bot")
                embed.set_author(
                    name="Conversation Agent",
                )
                await message.channel.send(embed=embed)
                return

        if message.content.lower().startswith("~prompt "):
            message.content = "~prompt ".join(message.content.split(" ")[1:])
            promptDebug = True
        else:
            promptDebug = False

        # Send the message to the model
        try:
            message_prompt = await self._create_prompt(message)
            message_embeds = await self._handle_embed(message)
            message_send = (
                f"{message_prompt}\n\nIncoming Message:\n```\n{message.content}\n```"
            )
            if message_embeds:
                message_send += (
                    f"\n\nIncoming Message has embeds:\n```\n{message_embeds}\n```"
                )

            # Check for replies
            if message.reference:
                reply = await message.channel.fetch_message(
                    message.reference.message_id
                )
                print(f"[Gemini] Reply detected: {message.reference.resolved.content}")
                message_send = f"{message_prompt}\n\nIncoming Reply Message:\n```\n{message.content}\n```\nReplying to {reply.author.display_name}:\n```\n{reply.content}\n```"

            # Read memory
            try:
                with open("store/memory.txt", "r") as f:
                    memory = f.readlines()
                    if memory:
                        message_send += f"\n\nMemory:\n```\n{memory}\n```"
            except FileNotFoundError:
                print("[Gemini] Memory file not found")
                pass
            except Exception as e:
                print(f"[Gemini] Error reading memory: {e}")
                pass

            if message.attachments:
                # Check if the attachment is an image
                image = await self._handle_attachment(message)
                if image:
                    print(f"[Gemini] Image processed: {image}")
                    print(f"[Gemini] Sending message to gemini: {message_send}")
                    response = await self.chat.send_message_async(
                        [image, message_send],
                    )
            else:
                if promptDebug:
                    await message.channel.send(f"## Prompt\n{message_send}")
                    return

                print(f"[Gemini] Sending message to gemini: {message_send}")
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

        # Process the response
        await self._process_response(response.text, message)

    async def _process_response(self, response: str, message: discord.Message):
        print(f"[Gemini] Response received: {response}")
        commands = response.split("%^%")
        print(f"[Gemini] Commands: {commands}")
        for command in commands:
            # Remove leading/trailing whitespace
            command = command.strip()

            # Check for actions
            action = command.split(" ")[0]
            if action.startswith("~send"):
                print(f"[Gemini] Sending message: {command}")
                message_text = command.split(" ", 1)[1]
                await message.channel.send(message_text)
                continue

            if action.startswith("~reset"):
                print("[Gemini] Resetting chat")
                await self._new_chat()
                embed = discord.Embed(
                    title="Chat Reset",
                    description="The chat has been reset; Jerry has forgotten everything :(",
                    color=discord.Color.green(),
                )
                embed.set_footer(text="Powered by Jerry Bot")
                embed.set_author(
                    name="Conversation Agent",
                )
                await message.channel.send(embed=embed)
                continue

            if action.startswith("~save"):
                print(f"[Gemini] Saving text: {command}")
                text = command.split(" ", 1)[1]
                await self._add_memory(text)
                continue

    async def _new_chat(self):
        self.chat = self.model.start_chat()
        return

    async def _create_prompt(self, message: discord.Message):
        message_prompt = f"""You are Jerry, a discord AI chatbot.

Your name is Jerry, your AI's character is displayed and characterized as a red octopus, your emoji and avatar is <:jerry:1284336293811327080> if anyone asks

The user id of the member who sent the message is included in the request, feel free to use an @mention in place of their name. Mentions are formed like this: <@user id>. 

You are here to be helpful as well as just an AI friend. You are currently in a discord channel. You are talking to a user. They are called {message.author.display_name} and can be mentioned as {message.author.mention}. 

To interact with the chat, use the following commands:
~send <message> - Respond with a message
~reset - Reset the chat
~save <text> - Remember a piece of text forever; use this to remember important information such as names, dates, or other details that may be relevant to the conversation in the future. You can also use it to remember names & ids of users, etc. Memory will be included in this prompt.
To execute multiple commands, separate them with %^%"""

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
                fileName = f"./store/images/{message.attachments[0].filename}"
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

    async def _handle_embed(self, message: discord.Message) -> str:
        if not message.embeds:
            return None
        print(f"[Gemini] {len(message.embeds)} embeds found")
        embeds_str = ""
        for embed in message.embeds:
            embeds_str += f"Embed Title: {embed.title}\nEmbed Description: {embed.description}\nEmbed Fields:\n"
            for field in embed.fields:
                embeds_str += f"Field Name: {field.name}\nField Value: {field.value}\n"
            embeds_str += f"Embed Footer: {embed.footer.text}\nEmbed Author: {embed.author.name}\n"
        print(f"[Gemini] Processed embeds: \n{embeds_str}")
        return embeds_str

    async def shell_callback(
        self, command: str, query: list, shell_command: core.ShellCommand
    ):
        if command == "gemini":
            await shell_command.log(
                "Now entering Gemini mode.",
                title="Entering Gemini Mode",
                msg_type="info",
            )
            self.bot.shell.interactive_mode = "gemini"

    async def _add_memory(self, text: str):
        with open("store/memory.txt", "a") as f:
            f.write(f"{text}\n\n")
            return True

    async def _load_memory(self):
        with open("store/memory.txt", "r") as f:
            return f.readlines()


class AutoReply(commands.Cog):
    """
    A Discord bot cog for automatically replying to specific messages.
    Attributes:
        bot (Jerry): The instance of the bot.
        auto_reply (dict): A dictionary containing regex patterns as keys and their corresponding responses.
    Methods:
        __init__(bot: Jerry):
            Initializes the AutoReply cog with the bot instance and predefined auto-reply patterns.
        on_ready():
            Event listener that triggers when the bot is ready. Prints the number of auto-reply patterns loaded.
        on_message(message: discord.Message):
            Event listener that triggers on every new message. Checks the message content against predefined patterns
            and replies accordingly if a match is found.
    """

    def __init__(self, bot: Jerry):
        self.bot = bot

        self.auto_reply = {
            "nuh+[\W_]*h?uh": {"response": "Yuh-uh ✅"},
            "yuh+[\W_]*h?uh": {"response": "Nuh-uh ❌"},
            "womp": {"response": "Womp womp"},
            "^shut+[\W_]*up": {"response": "No u"},
        }

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"[AutoReply] Ready with {len(self.auto_reply)} replies")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        if message.channel.id == 1293430080328171530:
            return

        for pattern, response in self.auto_reply.items():
            if re.search(pattern, message.content, re.IGNORECASE):
                if "response" in response:
                    await message.reply(response["response"])
