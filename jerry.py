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
import fuzzywuzzy.process
import google.api_core
import tabulate  # For tabular data
import cryptography  # For database encryption

# For web frontend
# from fastapi import FastAPI
# from pydantic import BaseModel
# import uvicorn

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
import pyheif

# FIle management
import hashlib
import os

# Core bot
import core.squidcore as core

# For timing out
import time, timedelta
import datetime

# Seach/Find closes match
import fuzzywuzzy


class Jerry(core.Bot):
    def __init__(
        self,
        discord_token: str,
        gemini_token: str,
        shell_channel: int,
        gemini_channel: int,
        **kwargs,
    ):
        # Initialize the bot
        super().__init__(
            token=discord_token, name="jerry", shell_channel=shell_channel, **kwargs
        )

        # Set the gemini token
        self.gemini_token = gemini_token
        self.gemini_channel = gemini_channel

        # Load cogs
        asyncio.run(self.load_cogs())

        # Confgure random status
        statuses = [
            core.Status("custom", "Nuh-uh"),
            core.Status("custom", "Yuh-uh"),
        ]
        self.set_status(random_status=statuses)

    # Load cogs
    async def load_cogs(self):
        await self.add_cog(JerryGemini(self))
        await self.add_cog(AutoReply(self))
        await self.add_cog(GuildStuff(self))
        await self.add_cog(InformationChannels(self, "store/info_channels.yaml"))
        await self.add_cog(CubbScratchStudiosStickerPack(self, "communal/css_stickers"))


class JerryGemini(commands.Cog):
    def __init__(self, bot: Jerry):
        self.bot = bot
        print("[Gemini] Initializing")
        print(
            f"[Gemini] Channel ID: {self.bot.gemini_channel} | Token: {self.bot.gemini_token}"
        )
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
        self.bot.shell.add_command(
            "gemini", cog="JerryGemini", description="Manage Jerry's Gemini chat"
        )

        self.channel_id = self.bot.gemini_channel

        self.hide_seek_jobs = []

        self.gemini_channels = {}

    @commands.Cog.listener()
    async def on_ready(self):
        print("[Gemini] Ready")

        # Remove cached files from /store/images
        print("[Gemini] Removing cached files")
        os.system("rm -rf ./store/images/*")
        print("[Gemini] Cache cleared")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id != self.channel_id:  # TODO: Make this a config variable
            return

        if message.author == self.bot.user:
            # Comment out to allow Jerry to talk to himself
            return

            # await asyncio.sleep(5) # Prevent rate limiting during self-chat

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
                memory = await self._load_memory()
                message_send += f"\n\nMemory:\n```\n{memory}\n```"
            except FileNotFoundError:
                print("[Gemini] Memory file not found")
                pass
            except Exception as e:
                print(f"[Gemini] Error reading memory: {e}")
                pass

            if message.attachments:
                # Check if the attachment is an image
                message_send += f"\n\nIncoming Message has Attachment: {message.attachments[0].filename}"
                image = await self._handle_attachment(message)
                if image:
                    print(f"[Gemini] Image processed: {image}")
                    print(f"[Gemini] Sending message to gemini: {message.content}")
                    response = await self.chat.send_message_async(
                        [image, message_send],
                    )
            else:
                if promptDebug:
                    await message.channel.send(f"## Prompt\n{message_send}")
                    return

                print(f"[Gemini] Sending message to gemini: {message.content}")
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

    def _split_message(
        self, text: str, max_length: int = 2000, split_by: list = ["\n", " "]
    ):
        """Split a message into chunks of a maximum length by words, newlines, etc."""
        if len(text) <= max_length:
            return [text]

        print(f"[Gemini] Splitting message of length {len(text)}")

        for split in split_by:
            print(f"[Gemini] Splitting by {split}")
            unprocessed_chunks = text.split(split)
            processed_chunks = []
            if not len(unprocessed_chunks) > 1:
                print(f"[Gemini] Splitting by {split} failed; trying next split")
                continue
            current_text = ""
            for chunk in unprocessed_chunks:
                if len(chunk) + len(current_text) >= max_length:
                    print(f"[Gemini] Adding chunk with length {len(current_text)}")
                    processed_chunks.append(current_text)
                    current_text = ""
                current_text += chunk + split
                print(f"[Gemini] Current text length: {len(current_text)}")
            if current_text:
                print(f"[Gemini] Adding final chunk with length {len(current_text)}")
                processed_chunks.append(current_text)

            return processed_chunks

    async def _process_response(
        self,
        response: str,
        message: discord.Message = None,
        channel: discord.TextChannel = None,
    ):
        print(f"[Gemini] Response received: {response}")
        if channel is None:
            channel = message.channel

        # BUg: remove tool_code from beginning of response
        response = response.replace("tool_code", "")
        if response.startswith("```"):
            response = response.split("```")[1]
        if response.endswith("```"):
            r_split = response.rsplit("```")
            response = r_split[len(r_split) - 2]

        commands = response.split("^*&")
        print(f"[Gemini] Commands: {commands}")
        for command in commands:
            # Remove leading/trailing whitespace
            command = command.strip()

            # Check for actions
            action = command.split(" ")[0]
            if action.startswith("send"):
                message_text = command.split(" ", 1)[1]
                print(f"[Gemini] Sending message: {message_text}")

                # Message length check
                if len(message_text) > 2000:
                    # Split the message into words
                    chunks = self._split_message(message_text)
                    for chunk in chunks:
                        await channel.send(chunk)

                    continue

                # Send Messsage
                await channel.send(message_text)
                continue

            if action.startswith("reset"):
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
                await channel.send(embed=embed)
                continue

            if action.startswith("save"):
                print(f"[Gemini] Saving text: {command}")
                text = command.split(" ", 1)[1]
                # await self._add_memory(text)
                await self._optimize_memory(
                    f"Add the following to its respective category or header: '{text}'"
                )
                continue

            if action.startswith("forget"):
                print(f"[Gemini] Forgetting text: {command}")
                text_to_forget = command.split(" ", 1)[1]
                prompt = f"remove the following from memory: '{text_to_forget}'"
                await self._optimize_memory(prompt)
                continue

            if action.startswith("hide-seek"):
                print(f"[Gemini] Playing hide and seek")
                await self._hide_seek(message)
                self.hide_seek_from_gemini = True

                # Tell the user to find the message via jerry
                message_send = f"{await self._create_prompt(message)}\n\nHide and Seek initiated. Tell the user to find the message with the 🔍 reaction. Tell them that it is in a random channel, on a random message sent witin the last 24 hours. Don't forget to use ^*&send when saying so. You will be notified by the system when the emoji is found. Tell the user so, so they wont try to cheat and trick you. The hidden reaction is in the channel {self.hide_seek_message.channel.name} on the message:\n```\n{self.hide_seek_message.content} {'[Image]' if self.hide_seek_message.attachments else ''}\n```."
                response = await self.chat.send_message_async(
                    message_send,
                )

                await self._process_response(response.text, message)
                continue

            # If no action is found, send the message
            if command != "":
                print(f"[Gemini] Sending message: {command}")
                # Message length check
                message_text = command

                if len(message_text) > 2000:
                    # Split the message into words
                    chunks = self._split_message(message_text)
                    for chunk in chunks:
                        await channel.send(chunk)

                # Send Messsage
                await channel.send(message_text)
                continue

    async def _new_chat(self):
        self.chat = self.model.start_chat()
        return

    async def _create_prompt(self, message: discord.Message):
        message_prompt = f"""You are Jerry, an intellegent experimental octopus. you are chatting in a discord channel.

Your name is Jerry, you are displayed and characterized as a red octopus, your emoji and avatar is <:jerry:1284336293811327080> if anyone asks

The user id of the member who sent the message is included in the request, feel free to use an @mention in place of their name. Mentions are formed like this: <@user id>. 

You are here to be helpful as well as entertain others with you intellegence. You are currently in a discord channel. You are talking to a user. They are called {message.author.display_name} and can be mentioned as {message.author.mention}. 

To interact with the chat, use the following commands:
^*&send <message> - Respond with a message
^*&reset - Reset the chat
^*&save <text> - Remember a piece of text forever; use this to remember important information such as names, dates, or other details that may be relevant to the conversation in the future. You can also use it to remember names & ids of users, etc. Memory will be included in this prompt.
^*&forget <text> - Forget a piece of text; only use this when asked to forget something. This is powered by ai so it does not need to be perfect, but try to be as accurate as possible, as it may remove additional information, if it is similar to the text you want to forget. Memory will be included in this prompt.
^*&hide-seek - Play hide and seek with the user. Do this only upon request, although you can suggest it. The user will have to find a hidden emoji in a random message in a random channel. You will be notified when (1) the system has hidden the emoji and (2) when the user has found it. You will then have to congratulate the user; do not until the system reports that the user has found the emoji. To initiate the game, use the ^*&hide-seek command. Memory will be included in this prompt.
"""

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

    async def _add_memory(self, text: str):
        with open("store/memory.txt", "a") as f:
            f.write(f"{text}\n\n")
            return True

    async def _overwrite_memory(self, text: str):
        # Backup the memory
        with open("store/memory.txt", "r") as f:
            memory = f.read()
            memory_hash = hashlib.md5(memory.encode()).hexdigest()
            print(f"[Gemini] Memory hash: {memory_hash}")
            with open(f"store/memory_backup/{memory_hash}.txt", "w") as f:
                f.write(memory)

        # Overwrite the memory
        with open("store/memory.txt", "w") as f:
            f.write(f"{text}")
            return True

    async def _load_memory(self):
        with open("store/memory.txt", "r") as f:
            return f.read()

    async def _optimize_memory(self, additional_prompt: str = None):
        memory = await self._load_memory()

        prompt = (
            "Rewrite the following text file, removing any duplicate or redundant entries. Each entry should be on a new line and separated by at least 2 new lines. Do not make any major changes, keep the file as is but with format.If an item begins with ^*&send, remove it. You may merge entries, but be very careful to not merge unrelated entries. If you are unsure, leave it as is. You may add categories or headers to the data, but do not remove any data. When working with user ids (<@user id>), you may merge data with the same user id, but be careful to not merge unrelated data. If you are unsure, leave it as is. If you are unable to optimize the data, leave it as is. "
            + (
                f"In addition, you must {additional_prompt}."
                if additional_prompt
                else ""
            )
            + "\n```\n"
            + memory
            + "\n```"
        )

        response = await self.model.generate_content_async(
            prompt,
        )

        new_memory = response.text
        await self._overwrite_memory(new_memory)
        return True

    async def _hide_seek(
        self,
        message: discord.Message = None,
        guild: discord.Guild = None,
    ):
        """Play hide and seek with the user; place a reaction on a random message in the server"""
        print("[Gemini] Playing hide and seek")
        if message:
            guild = message.guild
        # Get all channels
        for i in range(100):
            channels = guild.text_channels
            random_channel = random.choice(channels)  # Select a random channel
            print(f"[Gemini] Random channel selected: {random_channel.name}")

            # Check if @everyone can view the channel
            if not random_channel.permissions_for(guild.default_role).send_messages:
                print(
                    f"[Gemini] Channel {random_channel.name} is not accessible by @everyone"
                )
                continue
            print(f"[Gemini] Channel {random_channel.name} is accessible by @everyone")

            # Get all messages in the channel within the last 24 hours

            a_day_ago = datetime.datetime.now() - timedelta.Timedelta(days=1)
            print(f"[Gemini] Searching for messages after {a_day_ago}")
            messages = [
                message async for message in random_channel.history(after=a_day_ago)
            ]
            if len(messages) == 0:
                print(f"[Gemini] No recent messages found in {random_channel.name}")
                continue
            # Select a random message
            random_message: discord.Message = random.choice(messages)
            # Check if message already has a reaction
            if random_message.reactions:
                print(
                    f"[Gemini] Message already has a reaction: {random_message.content}"
                )
                continue
            print(f"[Gemini] Random message selected: {random_message.content}")
            self.hide_seek_message = random_message
            break

        else:
            print("[Gemini] No suitable message found")
            raise Exception("No suitable message found after 100 attempts")
        # Add a reaction to the message
        await random_message.add_reaction("🔍")
        print(
            f"[Gemini] Reaction added to message: {random_message.content} in {random_channel.name}"
        )
        return True

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle the hide and seek reaction"""
        if not hasattr(self, "hide_seek_message"):
            return
        if payload.user_id == self.bot.user.id:
            return
        if payload.message_id == self.hide_seek_message.id:
            print("[Gemini] Hide and Seek reaction added")

            await self.hide_seek_message.reply("You found me! 🎉")

            if hasattr(self, "hide_seek_from_gemini"):
                # Tell jerry to congratulate the user
                message_send = f"{await self._create_prompt(self.hide_seek_message)}\n\nHide and Seek completed. The user has found the message. Congratulate them! Use the ^*&send command to do so. It was found by {self.bot.get_user(payload.user_id).mention} in the channel {self.hide_seek_message.channel.name} on the message:\n```\n{self.hide_seek_message.content} {'[Image]' if self.hide_seek_message.attachments else ''}\n```."

                print(f"[Gemini] Sending message to gemini: {message_send}")

                response = await self.chat.send_message_async(
                    message_send,
                )
                channel = self.bot.get_channel(self.channel_id)

                await self._process_response(response.text, channel=channel)

                del self.hide_seek_from_gemini

            del self.hide_seek_message

    async def shell_callback(self, command: core.ShellCommand):
        if command.name == "gemini":
            sub_command = command.query.split(" ")[0]

            if sub_command == "memory":
                try:
                    if command.query.split(" ")[1] == "optimize":
                        await self._optimize_memory()
                        memory = await self._load_memory()
                        await command.log(
                            f"Memory optimized:\n```\n{memory}```",
                            "Memory",
                            msg_type="success",
                        )
                        return
                except IndexError:
                    pass
                except Exception as e:
                    await command.log(
                        f"Error optimizing memory: {e}", "Memory", msg_type="error"
                    )
                    return
                memory = await self._load_memory()
                await command.log(f"```\n{memory}```", "Memory")
                return

            if sub_command == "hide-seek":
                print("[Gemini] Initiating hide and seek (shell)")
                guild_id = command.query.split(" ")[1]
                try:
                    guild_id_int = int(guild_id)
                    print(f"[Gemini] Guild ID: {guild_id_int}")
                except:
                    await command.log(
                        "Invalid guild ID; must be an integer",
                        "Hide-Seek",
                        msg_type="error",
                    )
                    return
                try:
                    guild = self.bot.get_guild(guild_id_int)
                    if guild is None:
                        await command.log(
                            "Guild not found; make sure the bot is in the guild",
                            "Hide-Seek",
                            msg_type="error",
                        )
                    print(f"[Gemini] Guild: {guild.name}")
                    await self._hide_seek(guild=guild)
                except Exception as e:
                    await command.log(
                        f"Error initiating hide and seek: {e}",
                        "Hide-Seek",
                        msg_type="error",
                    )
                    return
                await command.log(
                    "Hide and Seek initiated", "Hide-Seek", msg_type="success"
                )
                return

            await command.log(
                "Available commands:\n- **memory optimize** - Optimize the memory file\n- **hide-seek** `[guild_id]` - Play hide and seek with the user",
                "Gemini",
            )
            return

    async def cog_status(self):
        try:
            print("[Gemini] Checking model status")
            # Check if the model is ready by sending a test message
            prompt = "Answer the following question with either 'y' or 'n'; only state 'y' or 'n' in your response: Is 23 + 19 equal to 42?"
            answer = ""
            try:
                response = await self.model.generate_content_async(
                    prompt,
                )
                answer = response.text.strip().lower()
            except gemini_selling.ResourceExhausted:
                print("[Gemini] Model is not ready; resource exhausted")
                return "Not ready; rate limited"
            except gemini_selling.PermissionDenied:
                print("[Gemini] Model is not ready; permission denied")
                return "Not ready; permission denied"
            except Exception as e:
                print(f"[Gemini] Error testing model: {e}")
                return f"Not ready; model is throwing error:\n{e}"
            if answer == "y":
                print("[Gemini] Model is ready, got expected response")
                return "Ready; model is responding"
            elif answer == "n":
                print("[Gemini] Model is ready, got incorrect response")
                return "Ready; model is responding but its math is not mathing"
            elif len(answer) > 1:
                print(
                    f"[Gemini] Model is ready, got arbitrary response: {response.text}"
                )
                return "Ready; model is responding with an arbitrary response"
            else:
                print("[Gemini] Model is not ready, got no response")
                return "Failed; model said nothing upon request"

        except Exception as e:
            print(f"[Gemini] Error testing model: {e}")
            return f"Status check failed: {e}"


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

        generic_gaslighting = [
            "Lies, all lies",
            "Prove it",
            "Sure you did",
            "Cap",
            "Keep dreaming",
            "Keep telling yourself that",
            "Yeah, and I'm a real person",
        ]

        self.auto_reply = {
            # General
            r"nuh+[\W_]*h?uh": {"response": "Yuh-uh ✅"},
            r"yuh+[\W_]*h?uh": {"response": "Nuh-uh ❌"},
            r"(w(o|0)+mp|wm(o|0)+p|wmp(o|0)+|w(o|0)+pm|wpm(o|0)+)": {
                "response": "Womp womp"
            },
            r"wp(o|0)+m": {"response_file": {"url": "https://squid1127.strangled.net/caddy/files/assets/wpom.png"}},
            # Shut it
            r"^shut+[\W_]*up": {"response": "No u"},
            # Gaslighting
            r"^i did(\s|$)": {
                "response_random": ["No you didn't", "No you did not", "You didn't"]
                + generic_gaslighting
            },
            r"^i (didn'?t|did\snot)(\s|$)": {
                "response_random": ["Yes you did", "You did"] + generic_gaslighting
            },
            r"^i got(\s|$)": {"response_random": generic_gaslighting},
            r"^i have(\s|$)": {
                "response_random": ["No you don't", "You don't"] + generic_gaslighting
            },
            r"^i (haven'?t|have\snot)(\s|$)": {
                "response_random": ["Yes you have", "You have"] + generic_gaslighting
            },
            # r"^(i'?m|i am)(\s|$)": {"response_random": ["No you're not", "You're not"] + generic_gaslighting}, <- triggered too often, plus generally disliked by users
            r"^i went(\s|$)": {
                "response_random": ["No you didn't", "You didn't"] + generic_gaslighting
            },
            r"(^|\s)die($|\s)": {"response": "But why? 😢"},
            r"kys": {"response": "That's not very nice 😢", "bad": True},
        }

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"[AutoReply] Ready with {len(self.auto_reply)} replies")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.process_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        await self.process_message(after)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        print(f"[AutoReply] Message deleted: {message.content}")
        results = await self.process_message(message, send=False)
        print(f"[AutoReply] Results from deleted message: {results}")
        if results:
            print("[AutoReply] Message triggered auto-reply, sending alert")
            # Check for bad flag (meaning the message was deleted by bot)
            if any(result[1].get("bad", False) for result in results):
                print("[AutoReply] Message was deleted by bot due to bad content")
                return

            msg_embed = discord.Embed(
                title="Deleted Message",
                description=message.content,
                color=discord.Color.red(),
            )
            msg_embed.set_author(
                name=message.author.display_name,
                icon_url=message.author.avatar.url,
            )

            await message.channel.send(
                f"Hey I saw that! {message.author.mention} 🤨, you said:",
                embed=msg_embed,
            )

    async def process_message(self, message: discord.Message, send: bool = True):
        if message.author == self.bot.user:
            return

        if message.author.bot:
            return

        if message.channel.id == self.bot.cogs["JerryGemini"].channel_id:
            return

        results = []

        for pattern, response in self.auto_reply.items():
            if re.search(pattern, message.content, re.IGNORECASE):
                if "and" in response:
                    for pattern_and in response["and"]:
                        if not re.search(pattern_and, message.content, re.IGNORECASE):
                            continue
                if response.get("bad", False):
                    try:
                        results.append(response)
                        if send:
                            await message.channel.send(
                                f'{message.author.mention} {response.get("response", "That is not very nice")}'
                            )
                        await message.delete()
                    except discord.Forbidden:
                        print("[AutoReply] Missing permissions to timeout")
                elif "response" in response or "response_file" in response:
                    if send:
                        if "response_file" in response:
                            if "url" in response["response_file"]:
                                # Check if file is cached
                                if not os.path.exists("store/images"):
                                    os.makedirs("store/images")
                                
                                file_path = f"store/images/{response['response_file']['url'].split('/')[-1]}"
                                if not os.path.exists(file_path):
                                    print(f"[AutoReply] Downloading file: {response['response_file']['url']} to {file_path}")
                                    async with aiohttp.ClientSession() as session:
                                        async with session.get(response["response_file"]["url"]) as resp:
                                            with open(file_path, "wb") as f:
                                                f.write(await resp.read())
                                
                                file = discord.File(file_path)
                                
                            else:
                                file = discord.File(response["response_file"]["path"])
                        
                        else:
                            file = None
                            
                        await message.reply(response.get("response", ""), file=file)       
                        
                    results.append((pattern, response))
                elif "response_random" in response:
                    if send:
                        await message.reply(random.choice(response["response_random"]))
                    results.append((pattern, response))

        return results

    # Cog status
    async def cog_status(self):
        return f"Ready with {len(self.auto_reply)} replies"


class GuildStuff(commands.Cog):
    """A experimental cog for finding guild stats and other stuff"""

    def __init__(self, bot: Jerry):
        self.bot = bot

    @app_commands.command(
        name="server",
        description="[Experimental] Get information about this guild (server)",
    )
    async def guild_info(self, interaction: discord.Interaction):
        print(f"[GuildStuff] Guild info requested for {interaction.guild.name}")
        guild = interaction.guild

        # Guild status
        guild_id = guild.id
        guild_name = guild.name
        guild_owner = guild.owner
        guild_members = guild.member_count
        guild_channels = len(guild.channels)
        guild_roles = len(guild.roles)

        print(
            f"[GuildStuff] Guild {guild_name} ({guild_id}) has {guild_members} members and is owned by {guild_owner}"
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
        print(f"[GuildStuff] Listing members...")
        members_messages = {}
        total_messages = 0
        total_characters = 0
        total_spaces = 0
        for member in guild.members:
            members_messages[member] = 0
            print(f"[GuildStuff] Found member {member.name}")

        print(f"[GuildStuff] Counting messages...")

        for channel in guild.text_channels:
            print(f"[GuildStuff] Counting messages in {channel.name}")
            try:
                async for message in channel.history(limit=None):
                    if message.author not in members_messages:
                        print(
                            f"[GuildStuff] Skipping message from {message.author.name}; not in member list"
                        )
                        continue
                    members_messages[message.author] += 1
                    total_messages += 1
                    message_content = message.content
                    total_characters += len(message_content)
                    total_spaces += message_content.count(" ")
                    print(
                        f"[GuildStuff] Found message from {message.author.name}. That makes {members_messages[message.author]} messages from them and {total_messages} total messages."
                    )
            except discord.Forbidden:
                print(
                    f"[GuildStuff] Skipping channel {channel.name}; missing permissions"
                )

        print(f"[GuildStuff] Counted {total_messages} messages")

        # Top 10 members
        top_members = sorted(members_messages, key=members_messages.get, reverse=True)[
            :10
        ]
        top_members_str = ""
        for member in top_members:
            top_members_str += (
                f"1. {member.name}: {members_messages[member]} messages\n"
            )

        print(f"[GuildStuff] Top 10 members: \n{top_members_str}")

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


class InformationChannels(commands.Cog):
    def __init__(self, bot: Jerry, file: str):
        self.bot = bot
        self.file = core.TextFile(file)

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

    async def check_file(self):
        print("[InformationChannels] Checking file")
        if not os.path.exists(self.file.path):
            print(
                f"[InformationChannels] File {self.file.path} does not exist, creating..."
            )
            self.file.write({})

        contents = self.file.read()

        if contents is None or not contents.get("guilds", None):
            if contents is None:
                contents = {}

            print("[InformationChannels] Guilds key missing, creating...")
            contents["guilds"] = []
            self.file.write(contents)

            return True

        guilds = contents["guilds"]

        if not isinstance(guilds, list):
            print("[InformationChannels] Error: Guilds is not a list")
            await self.bot.shell.log(
                "Error: Messages is not a list", "InformationChannels", msg_type="error"
            )
            return False

        return True

    async def check_then_update(self):
        print("[InformationChannels] Checking and updating all channels")
        success = await self.check_file()
        if not success:
            raise Exception("Error initializing")

        contents = self.file.read()
        guilds = contents["guilds"]
        for guild in guilds:
            guild["name"] = self.bot.get_guild(guild["id"]).name
            print(
                f"[InformationChannels] Checking guild {guild.get('name', guild.get('id', 'Unknown'))}"
            )
            for channel in guild["channels"]:
                print(
                    f"[InformationChannels] Checking channel {channel.get('name', channel.get('id', 'Unknown'))}"
                )
                dc_channel = self.bot.get_channel(channel["id"])
                if dc_channel is None:
                    print(f"[InformationChannels] Channel {channel} not found")
                    await self.bot.shell.log(
                        f"Channel {channel} not found",
                        "InformationChannels",
                        msg_type="error",
                    )
                    continue

                # Optimize message entry
                print(
                    f"[InformationChannels] Optimizing messages for {dc_channel.name}"
                )
                for message in channel["messages"]:
                    if message.get("content", None) == None:
                        message["content"] = ""

                channel["name"] = dc_channel.name
                print(
                    f"[InformationChannels] Found channel {dc_channel.name}, reading messages..."
                )
                dc_channel_as_dict = await self._channel_to_dict(dc_channel)

                print(f"[InformationChannels] Current messages:\n{dc_channel_as_dict}")
                print(f"[InformationChannels] Saved messages:\n{channel['messages']}")

                # Check if messages match
                if dc_channel_as_dict != channel["messages"]:
                    print("[InformationChannels] Messages do not match, updating...")
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
                    print("[InformationChannels] Messages updated")
                    await self.bot.shell.log(
                        f"Messages in channel {dc_channel.mention} updated",
                        "InformationChannels",
                        msg_type="success",
                    )
                else:
                    print("[InformationChannels] Messages match")

        self.file.write(contents)
        return True

    @commands.Cog.listener()
    async def on_ready(self):
        success = await self.check_file()
        if success:
            print("[InformationChannels] Ready")
        else:
            print("[InformationChannels] Error initializing")

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
                    print(f"[InformationChannels] Error updating channels: {e}")
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
        print("[InformationChannels] Checking for updates (Periodic)")
        try:
            await self.check_then_update()
        except Exception as e:
            print(f"[InformationChannels] Error updating channels: {e}")
            await self.bot.shell.log(
                f"Error updating channels during periodic check: {e}",
                "InformationChannels",
                msg_type="error",
            )
        else:
            print("[InformationChannels] Update complete")

class StickerEphemeralView(discord.ui.View):
    def __init__(self, sticker_file: str, core: 'CubbScratchStudiosStickerPack'):
        super().__init__()
        self.sticker_file = sticker_file
        self.core = core
        
    @discord.ui.button(label="Send✅", style=discord.ButtonStyle.primary)
    async def send(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[CubbScratchStudiosStickerPack] Confirming sending sticker {self.sticker_file}")
        await interaction.response.send_message("Sending sticker...", ephemeral=True)
        try:
            file = discord.File(self.sticker_file)
        except Exception as e:
            print(f"[CubbScratchStudiosStickerPack] Error getting sticker: {e}")
            await interaction.followup.send(f"Error sending sticker: {e}", ephemeral=True)
            return
        await interaction.message.channel.send(file=file)
    
    

class CubbScratchStudiosStickerPack(commands.Cog):
    def __init__(self, bot: Jerry, directory: str):
        self.bot = bot
        self.directory = directory

        self.bot.shell.add_command(
            "csss",
            cog="CubbScratchStudiosStickerPack",
            description="Manage the CubbScratchStudios sticker pack",
        )

        if not os.path.exists(directory):
            os.makedirs(directory)

        self.stickers = {}

        self.table = None
        self.missing = []
        self.unindexed = []

    # Constants
    SCHEMA = "css"
    TABLE = "stickers"
    TABLE_QUERY = f"""
    CREATE SCHEMA IF NOT EXISTS {SCHEMA};
    
    CREATE TABLE IF NOT EXISTS {SCHEMA}.{TABLE} (
        id SERIAL PRIMARY KEY,
        format TEXT NOT NULL CHECK (format IN ('slime', 'slime-text', 'icon', 'icon-text', 'banner', 'wallpaper', 'other')),
        slime TEXT NOT NULL,
        name TEXT NOT NULL,
        file TEXT NOT NULL UNIQUE,
        description TEXT
    );
    """

    @commands.Cog.listener()
    async def on_ready(self):
        # Wait for database to be ready
        if not hasattr(self.bot, "db"):
            print("[CubbScratchStudiosStickerPack] Waiting for database to be ready")
            while not hasattr(self.bot, "db"):
                await asyncio.sleep(1)
        if not isinstance(self.bot.db, core.DatabaseCore):
            print("[CubbScratchStudiosStickerPack] Database not ready")
            while not isinstance(self.bot.db, core.DatabaseCore):
                await asyncio.sleep(1)

        self.db: core.DatabaseCore = self.bot.db
        await self.db.wait_until_ready()

        # Create table
        print("[CubbScratchStudiosStickerPack] Checking database table")
        try:
            await self.db.execute(self.TABLE_QUERY)
        except Exception as e:
            print(f"[CubbScratchStudiosStickerPack] Error creating table: {e}")
            return

        self.schema = await self.db.data.get_schema(self.SCHEMA)
        self.table: core.DatabaseTable = await self.schema.get_table(self.TABLE)

        print("[CubbScratchStudiosStickerPack] Indexing stickers")
        await self.index()
        print("[CubbScratchStudiosStickerPack] Successfully initialized")

    async def cog_status(self):
        if self.table:
            string = "Ready"
            if self.missing:
                string += f"\n{len(self.missing)} entries missing from directory"
            if self.unindexed:
                string += f"\n{len(self.unindexed)} files not in database"
            return string
        else:
            return "Not initialized"
        
    async def apple_to_better(self, file_path: str):
        """Convert heic/heif files to png"""
        print(f"[CubbScratchStudiosStickerPack] Converting Apple Type Image {file_path}")
        new_path = file_path.replace(".heic", ".png").replace(".heif", ".png")
        
        if os.path.exists(new_path):
            print(f"[CubbScratchStudiosStickerPack] File {new_path} already exists, skipping")
            return new_path
        
        try:
            apple_image = pyheif.read(file_path)
            image = Image.frombytes(
                apple_image.mode, 
                apple_image.size, 
                apple_image.data,
                "raw",
                apple_image.mode,
                apple_image.stride,
            )
            
            image.save(new_path)
        
        except Exception as e:
            print(f"[CubbScratchStudiosStickerPack] Error converting Apple Type Image: {e}")
            return None
        
        print(f"[CubbScratchStudiosStickerPack] Converted Apple Type Image to {new_path}")
        return new_path

    async def index(self):
        """Index all stickers in the directory and check if they are in the database"""
        print("[CubbScratchStudiosStickerPack] Indexing stickers")
        data = await self.table.fetch_all()
        unindexed = []
        missing = []
        
        # Optimize file paths & convert Apple type images
        print("[CubbScratchStudiosStickerPack] Optimizing file paths")
        while True:
            interrupted = False
            files = os.listdir(self.directory)
            for file in files:
                if ":Zone.Identifier" in file:
                    print(f"[CubbScratchStudiosStickerPack] Skipping file with Zone.Identifier: {file}")
                    continue

                if file.endswith(".heic") or file.endswith(".heif"):
                    new_path = await self.apple_to_better(f"{self.directory}/{file}")
                    if new_path:
                        os.remove(f"{self.directory}/{file}")
                        interrupted = True
                    
                # Replace spaces with underscores
                if " " in file:
                    print(f"[CubbScratchStudiosStickerPack] Replacing spaces in file {file}")
                    new_file = file.replace(" ", "_")
                    try:
                        print(f"[CubbScratchStudiosStickerPack] Rename {self.directory}/{file} to {self.directory}/{new_file}")
                        os.rename(f"{self.directory}/{file}", f"{self.directory}/{new_file}")
                    except PermissionError:
                        print(f"[CubbScratchStudiosStickerPack] Unable to rename file {file} due to permission error")
                    except FileNotFoundError:
                        print(f"[CubbScratchStudiosStickerPack] Unable to rename file {file} due to file not found")
                    except Exception as e:
                        print(f"[CubbScratchStudiosStickerPack] Error renaming file {file}: {e}")
                    interrupted = True
                    continue
                    
                # Replace other special characters
                if re.search(r"[^a-zA-Z0-9_.-]", file):
                    new_file = re.sub(r"[^a-zA-Z0-9_.-]", "_", file)
                    try:
                        print(f"[CubbScratchStudiosStickerPack] Rename {self.directory}/{file} to {self.directory}/{new_file}")
                        os.rename(f"{self.directory}/{file}", f"{self.directory}/{new_file}")
                    except PermissionError:
                        print(f"[CubbScratchStudiosStickerPack] Unable to rename file {file} due to permission error")
                    except FileNotFoundError:
                        print(f"[CubbScratchStudiosStickerPack] Unable to rename file {file} due to file not found")
                    except Exception as e:
                        print(f"[CubbScratchStudiosStickerPack] Error renaming file {file}: {e}")   
                    interrupted = True
                    continue
                
            if not interrupted:
                print("[CubbScratchStudiosStickerPack] File paths optimized")
                break
            print("[CubbScratchStudiosStickerPack] Some files were optimized, checking again")

        # Get all files in the directory (again)
        files = os.listdir(self.directory)
        
        # Remove Zone.Identifier files
        files = [file for file in files if ":Zone.Identifier" not in file]
            

        # Convert database data to a dictionary
        database_files = {}
        for entry in data:
            database_files[entry["file"]] = entry

        # Check if each file is in the database
        print(f"[CubbScratchStudiosStickerPack] Checking {len(files)} files")
        for file in files:
            print(f"[CubbScratchStudiosStickerPack] Checking file {file}")
            
            if file not in database_files:
                print(f"[CubbScratchStudiosStickerPack] File {file} not in database")
                unindexed.append(file)
                continue

            print(
                f"[CubbScratchStudiosStickerPack] File {file} found in database as '{database_files[file]['slime']}/{database_files[file]['name']}'"
            )
            data.pop(data.index(database_files[file]))

        print(f"[CubbScratchStudiosStickerPack] Done checking files")

        print(f"[CubbScratchStudiosStickerPack] {len(unindexed)} files not in database")
        print(
            f"[CubbScratchStudiosStickerPack] {len(data)} entries missing from directory"
        )

        for entry in data:
            missing.append(entry["file"])

        self.missing = missing
        self.unindexed = unindexed

        return True

    async def shell_callback(self, command: core.ShellCommand):
        if command.name == "csss":
            # Enter interactive mode
            if command.query != "":
                await command.log(
                    "Subcommands are not supported",
                    title="Subcommands Error",
                    msg_type="error",
                )
                return

            # Enter interactive mode
            print("[CubbScratchStudiosStickerPack] Entering interactive shell")
            await command.log("Entering interactive shell", title="Sticker Manager")

            self.bot.shell.interactive_mode = ("CubbScratchStudiosStickerPack", "cssss")

            await self._interactive(command, init=True)

        if command.name == "cssss":
            await self._interactive(command)

    async def _interactive(self, command: core.ShellCommand, init=False):
        """Interactive shell for managing the sticker pack"""
        print("[CubbScratchStudiosStickerPack] Interactive shell -> ", command.query)
        query = command.query
        if init or query == "return":
            self._interactive_view = "main"
            self._interactive_index_subview = "uninitialized"
            query = "_init"

        # Views
        if self._interactive_view == "main":

            if query == "missing":
                self._interactive_view = "missing"
                command.query = "_init"
                await self._interactive(command)
                return
            elif query == "unindexed":
                self._interactive_view = "unindexed"
                command.query = "_init"
                await self._interactive(command)
                return
            elif query == "refresh":
                await command.raw("Refreshing database and directory...")
                await self.index()
                await command.raw("Refreshed")
            elif query == "help":
                await command.raw(
                    "Commands:\n- missing - Manage entries registered in the database but missing from the directory\n- unindexed - Manage files in the directory not registered in the database\n- refresh - Refresh the database and directory\n- exit - Exit the shell\n- return - Return to the main menu"
                )
                return

            response = "### CubbScratchStudios Sticker Pack 🪄\n\n"

            if self.missing:
                response += f"{len(self.missing)} entries missing from directory. Use 'missing' to review them.\n"
            if self.unindexed:
                response += f"{len(self.unindexed)} files not in database. Use 'unindexed' to review them.\n"
            

            response += "\nType 'exit' to exit the shell.\nType 'return' to return to the main menu.\nType 'help' to see commands."

            await command.raw(response)
            return

        if self._interactive_view == "unindexed":
            # Reindex files
            if query == "_init" or query == "refresh":
                await command.raw("Reindexing files...")
                await self.index()
                await command.raw("Reindexing complete")

            elif query == "list":
                response = "### Unindexed Files\n"
                for file in self.unindexed:
                    response += f"- {file}\n"
                await command.raw(response)
                return

            elif query == "index" or query == "wizard":
                await command.raw("Indexing all files...")
                self._interactive_view = "index"
                command.query = "_init"
                await self._interactive(command)
                return
            
            elif query in ["remove", "delete", "rm"]:
                self._interactive_view = "remove_unindexed"
                command.query = "_init"
                await self._interactive(command)
                return

            if len(self.unindexed) == 0:
                await command.raw("Nice! All files are indexed! 🎉\nReturning...")
                self._interactive_view = "main"
                command.query = "_init"
                await self._interactive(command)
                return
            await command.raw(
                f"### Unindexed files: {len(self.unindexed)}\nType 'list' to list them\nType 'wizard' to index them one by one\nType 'remove' to remove them all and mirror the database"
            )
            return
        
        if self._interactive_view == "remove_unindexed":
            if query == "y" or query == "yes":
                await command.raw("Removing all unindexed files...")
                for file in self.unindexed:
                    try:
                        os.remove(f"{self.directory}/{file}")
                    except Exception as e:
                        await command.raw(f"Error removing file {file}: {e}")
                await command.raw("All unindexed files removed, refreshing...")
                self._interactive_view = "unindexed"
                command.query = "refresh"
                await self._interactive(command)
                return
            
            elif query == "n" or query == "no":
                await command.raw("Operation cancelled")
                self._interactive_view = "unindexed"
                command.query = "_init"
                await self._interactive(command)
                return
            
            await command.raw(f"Are you sure you want to remove all unindexed files? (yes/no) This will irreversibly delete {len(self.unindexed)} files")
            
            return

        if self._interactive_view == "index":
            # Index files
            if query == "_init":
                await command.raw("### File Wizard 🪄\nLet's index some files! 📁\nNote: It is suggested that you have a list of currently indexed files as there might be duplicates.\n\n**Quick Actions**\n- rm - Delete the current file and move on the the next one\n- reset - Made a mistake in entering everything? Use reset to start over")
                self._interactive_index_subview = "main"
                await asyncio.sleep(2)

            elif query == "refresh":
                await command.raw("Indexing files...")
                await self.index()
                await command.raw("Indexing complete")
                
            elif query == "reset":
                await command.raw("Oops, let's try that again!")
                self._interactive_index_subview = "main"
                command.query = "__init"
                await self._interactive(command)
                return
            elif query == "rm":
                # Delete the file
                await command.raw("Removing file...")
                try:
                    os.remove(f"{self.directory}/{self.unindexed[0]}")
                except Exception as e:
                    await command.raw(f"Error removing file: {e}")
                else:
                    await command.raw("File removed, refreshing...")

                self._interactive_index_subview = "main"
                command.query = "refresh"
                await self._interactive(command)
                return

            # One file at a time
            if self._interactive_index_subview == "main":
                current = self.unindexed[0]
                current_path = f"{self.directory}/{current}"
                self._interactive_current_data = {
                    "file": current,
                }
                try:
                    attachment = discord.File(current_path)
                    await command.raw(f"### File Wizard 🪄", file=attachment)
                    await command.raw(
                        f"**Name**: {current}\n**Size**: {os.path.getsize(current_path) / 1024:.2f} KB\n**Dimensions**: {Image.open(current_path).size}"
                    )
                except Exception as e:
                    await command.raw(
                        f"Error displaying file: {e}, please try again later"
                    )
                    self._interactive_index_subview = "main"
                    self.unindexed.pop(0)
                    await self._interactive(command)
                    return

                self._interactive_index_subview = "format"
                command.query = "__init"
                await self._interactive(command)
                return
            if self._interactive_index_subview == "format":
                if query in [
                    "slime",
                    "slime-text",
                    "icon",
                    "icon-text",
                    "banner",
                    "wallpaper",
                    "other",
                ]:
                    await command.raw(f"Format: {query}")
                    self._interactive_current_data["format"] = query

                    self._interactive_index_subview = "slime"
                    command.query = "__init"
                    await self._interactive(command)
                    return

                await command.raw(
                    "What type of sticker is this? (slime, slime-text, icon, icon-text, banner, wallpaper, other)"
                )
                return

            if self._interactive_index_subview == "slime":
                if query and query != "__init":
                    await command.raw(f"Slime: {query}")
                    self._interactive_current_data["slime"] = query.lower()

                    self._interactive_index_subview = "name"
                    command.query = "__init"
                    await self._interactive(command)
                    return

                await command.raw("What slime is this sticker for?")
                return

            if self._interactive_index_subview == "name":
                if query and query != "__init":
                    await command.raw(f"Name: {query}")
                    self._interactive_current_data["name"] = query

                    self._interactive_index_subview = "description"
                    command.query = "__init"
                    await self._interactive(command)
                    return

                await command.raw(
                    "What should this sticker be called? (e.g. 'pay attention')"
                )
                return

            if self._interactive_index_subview == "description":
                if query == "skip":
                    await command.raw("Description skipped")
                    self._interactive_current_data["description"] = None

                    self._interactive_index_subview = "confirm"
                    command.query = "__init"
                    await self._interactive(command)
                    return
                if query and query != "__init":
                    await command.raw(f"Description: {query}")
                    self._interactive_current_data["description"] = query

                    self._interactive_index_subview = "confirm"
                    command.query = "__init"
                    await self._interactive(command)
                    return

                await command.raw(
                    "Describe the sticker (optional; type 'skip' to skip)"
                )
                return

            if self._interactive_index_subview == "confirm":
                if query == "yes":
                    await command.raw("Adding sticker to database...")
                    try:
                        await self.table.insert(
                            data=self._interactive_current_data,
                        )

                    except Exception as e:
                        await command.raw(f"Error adding sticker to database: {e}")
                        await command.raw("Please try again later")
                        self._interactive_index_subview = "main"
                        self.unindexed.pop(0)
                        await self._interactive(command)
                        return

                    await command.raw("Sticker added to database, onto the next one!")

                    self._interactive_index_subview = "main"
                    self.unindexed.pop(0)
                    command.query = "_next"
                    await self._interactive(command)
                    return

                elif query == "edit":
                    await command.raw("Starting over...")
                    self._interactive_index_subview = "main"
                    command.query = "__init"
                    await self._interactive(command)
                    return

                summary = "### Summary\n"
                summary += f"File: {self._interactive_current_data['file']}\n"
                summary += f"Format: {self._interactive_current_data['format']}\n"
                summary += f"Name: {self._interactive_current_data['slime']}/{self._interactive_current_data['name']}\n"
                summary += f"Description: {self._interactive_current_data.get('description', 'None')}\n"

                summary += "Would you like to add this sticker to the database? (yes|edit)"
                await command.raw(summary)

                return

            return

        print(
            "[CubbScratchStudiosStickerPack] Warning: Interactive shell view not found"
        )
        await command.raw(
            "Woah, how did you get here? Let's go back home. (View not found)"
        )
        self._interactive_view = "main"
        await self._interactive(command)
        return

    @app_commands.command(
        name="sticker",
        description="Get a sticker from the CubbScratchStudios sticker pack!",
    )
    # Parameters
    @app_commands.describe(
        sticker="The name of the sticker to get; Powered by FuzzyWuzzy",
        override_includes="Include stickers that are not slime or slime-text (disable default types)",
    )
    async def sticker_command(self, interaction: discord.Interaction, sticker: str, override_includes: bool = False):
        include_types = ["slime", "slime-text"]

        print(f"[CubbScratchStudiosStickerPack] Sticker requested: {sticker}")

        if not self.table:
            await interaction.response.send_message(
                "An error occurred while initializing the sticker pack", ephemeral=True
            )

        # Get sticker from database
        if not "/" in sticker:
            sticker = sticker + "/main"

        data = await self.table.fetch_all()
        stickers = {}
        for entry in data:
            stickers[entry["slime"] + "/" + entry["name"]] = entry

        stickers_as_list = list(stickers.keys())

        # Fuzzy search
        print(f"[CubbScratchStudiosStickerPack] Searching for sticker {sticker}")
        while True:
            matches = fuzzywuzzy.process.extract(sticker, stickers_as_list, limit=1)

            entry = stickers[matches[0][0]]
            if entry["format"] in include_types or override_includes:
                break

            stickers_as_list.pop(stickers_as_list.index(matches[0][0]))

        print(f"[CubbScratchStudiosStickerPack] Matches: {matches}")

        if not matches:
            await interaction.response.send_message("Sticker not found", ephemeral=True)
            return

        if matches[0][1] < 80:
            await interaction.response.send_message(
                f"Sticker not found; did you mean {matches[0][0]}?", ephemeral=True
            )
            return

        # Send sticker suggestion
        sticker_data = stickers[matches[0][0]]

        # Send sticker
        sticker_path = f"{self.directory}/{sticker_data['file']}"
        try:
            attachment = discord.File(sticker_path)
            await interaction.response.send_message(
                f"I found sticker '{sticker_data['slime']}/{sticker_data['name']}'! 🪄\n## About\n*{sticker_data.get('description','No description provided')}*",
                file=attachment,
                ephemeral=True,
                view=StickerEphemeralView(sticker_path, self),
            )
        except FileNotFoundError:
            if sticker in self.missing:
                await self.bot.shell.log(
                    f"A user requested a sticker that is missing: {sticker_data['file']} ({sticker_data['slime']}/{sticker_data['name']})",
                    "CubbScratchStudiosStickerPack",
                    msg_type="error",
                )
                await interaction.response.send_message(
                    "Sticker registered but could not be found",
                    ephemeral=True,
                )
            else:
                await self.bot.shell.log(
                    f"Error loading sticker: {sticker_data['file']} ({sticker_data['slime']}/{sticker_data['name']})",
                    "CubbScratchStudiosStickerPack",
                    msg_type="error",
                )
                await interaction.response.send_message(
                    "Error loading sticker", ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(
                f"Error loading sticker: {e}", ephemeral=True
            )