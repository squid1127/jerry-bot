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
import fuzzywuzzy.process
import google.api_core

# For random status
import random

# Auto-reply
import re
import yaml

# Google Gemini client
import google.generativeai as gemini
import google.api_core.exceptions as gemini_selling
from PIL import Image
import mimetypes
import pyheif, pillow_heif
pillow_heif.register_heif_opener() # Register the HEIF opener to process HEIF images

# File management
import hashlib

# System
import os
import sys

# Core bot
import core.squidcore as core  # Core bot (https://github.com/squid1127/squid-core)

# For timing out
import time, timedelta
import datetime

# Seach/Find closes match
import fuzzywuzzy

# Logging
import logging
logger = logging.getLogger("jerry")


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
            discord.CustomActivity("Nuh-uh ❌", emoji="❌"),
            discord.CustomActivity("Yuh-uh ✅", emoji="✅"),
        ]
        self.set_status(random_status=statuses)
        

    # Load cogs
    async def load_cogs(self):
        await self.add_cog(JerryGemini(self))
        await self.add_cog(AutoReplyV2(self))
        await self.add_cog(GuildStuff(self))
        await self.add_cog(InformationChannels(self, "store/info_channels.yaml"))
        await self.add_cog(CubbScratchStudiosStickerPack(self, "communal/css_stickers"))
        await self.add_cog(StaticCommands(self))
        await self.add_cog(VoiceChat(self))


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
        self.bot.shell.add_command(
            "gemini", cog="JerryGemini", description="Manage Jerry's Gemini chat"
        )

        self.channel_id = self.bot.gemini_channel

        self.hide_seek_jobs = []

        self.gemini_channels = {}
        
        self.logger = logging.getLogger("jerry.gemini")

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("Ready")

        # Remove cached files from /store/images
        self.logger.info("Clearing cache")
        os.system("rm -rf ./store/cache/gemini/*")
        self.logger.info("Cache cleared")

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

        self.logger.debug(f"Message received: {message.content}")

        if not hasattr(self, "chat") or message.content.lower() == "~reset":
            self.logger.debug("Chat not initialized, initializing...")
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
            
            message_send = message_prompt
            
        # Check for replies
            if message.reference:
                reply = await message.channel.fetch_message(
                    message.reference.message_id
                )
                self.logger.debug(f"Reply detected: {message.reference.resolved.content}")
                message_send = f'\n\nIn reply to: {reply.author.display_name}, who said: \n"""{reply.content}"""'
                if reply.embeds and len(reply.embeds) > 0:
                    message_send += (
                        f"\nReply has Embeded Content:\n```\n{reply.embeds}\n```"
                    )
            
            message_send += (
                f'\n\n{"In response " if message.reference else ""} {message.author.display_name} said: \n"""{message.content}"""'
            )
            if message_embeds:
                message_send += (
                    f"\nEmbeded Content:\n```\n{message_embeds}\n```"
                )

            

            # Read memory
            try:
                memory = await self._load_memory()
                message_send += f"\n\nMemory:\n```\n{memory}\n```"
            except FileNotFoundError:
                self.logger.error("Memory file not found")
                pass
            except Exception as e:
                self.logger.error(f"Error reading memory: {e}")
                pass

            processed_attachments = []
            if message.attachments:
                # Check if there is an attachment
                message_send += f"\n\nAttachment: {message.attachments[0].filename}"
                processed_attachments = await self._handle_attachment(message)
                if processed_attachments and len(processed_attachments) > 0:
                    self.logger.debug(f"Processed attachments: {processed_attachments}")
                    
                    # Insert the message into the list
                    processed_attachments.insert(0, message_send)
                    
                    response = await self.model.generate_content_async(
                        processed_attachments,
                    )
            if (not message.attachments) or (not (processed_attachments and len(processed_attachments) > 0)):
                if promptDebug:
                    await message.channel.send(f"## Prompt\n{message_send}")
                    return

                self.logger.debug(f"Sending message to gemini: {message.content}")
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
            self.logger.warning("Resource exhausted")
            return

        # Process the response
        await self._process_response(response.text, message)

    def _split_message(
        self, text: str, max_length: int = 2000, split_by: list = ["\n", " "]
    ):
        """Split a message into chunks of a maximum length by words, newlines, etc."""
        if len(text) <= max_length:
            return [text]

        self.logger.debug(f"Splitting message of length {len(text)}")

        for split in split_by:
            self.logger.debug(f"Splitting by {split}")
            unprocessed_chunks = text.split(split)
            processed_chunks = []
            if not len(unprocessed_chunks) > 1:
                self.logger.debug(f"Splitting by {split} failed; trying next split")
                continue
            current_text = ""
            for chunk in unprocessed_chunks:
                if len(chunk) + len(current_text) >= max_length:
                    self.logger.debug(f"Adding chunk with length {len(current_text)}")
                    processed_chunks.append(current_text)
                    current_text = ""
                current_text += chunk + split
                self.logger.debug(f"Current text length: {len(current_text)}")
            if current_text:
                self.logger.debug(f"Adding final chunk with length {len(current_text)}")
                processed_chunks.append(current_text)

            return processed_chunks

    async def _process_response(
        self,
        response: str,
        message: discord.Message = None,
        channel: discord.TextChannel = None,
    ):
        self.logger.debug(f"Response received: {response}")
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
        self.logger.debug(f"Commands: {commands}")
        for command in commands:
            # Remove leading/trailing whitespace
            command = command.strip()

            # Check for actions
            action = command.split(" ")[0]
            if action.startswith("send"):
                message_text = command.split(" ", 1)[1]
                self.logger.debug(f"Sending message: {message_text}")

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
                self.logger.info("Resetting chat")
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
                self.logger.debug(f"Saving text: {command}")
                text = command.split(" ", 1)[1]
                # await self._add_memory(text)
                await self._optimize_memory(
                    f"Add the following to its respective category or header: '{text}'"
                )
                continue

            if action.startswith("forget"):
                self.logger.debug(f"Forgetting text: {command}")
                text_to_forget = command.split(" ", 1)[1]
                prompt = f"remove the following from memory: '{text_to_forget}'"
                await self._optimize_memory(prompt)
                continue

            if action.startswith("hide-seek"):
                self.logger.debug(f"Playing hide and seek")
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
                self.logger.debug(f"Sending message: {command}")
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
        processed_attachments = []
        for attachment in message.attachments:
            try:
                # Download the image
                self.logger.debug(f"Attachment found: {attachment.filename}. Downloading...")
                fileName = f"./store/cache/gemini/{attachment.filename}"
                
                os.makedirs(os.path.dirname(fileName), exist_ok=True)            # Create the directory if it doesn't exist

                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        # Save the image
                        with open(fileName, "wb") as f:
                            f.write(await resp.read())
                self.logger.debug(f"File downloaded: {fileName}")
                
            except Exception as e:
                self.logger.error(f"Error downloading attachment {attachment.filename}: {e}")
                message.reply(f"Error downloading attachment {attachment.filename}: {e}")
                continue
                            
            # Determine the file type
            try:
                mime_type, _ = mimetypes.guess_type(fileName)
                if mime_type is None:
                    raise Exception("File is missing a file extension or has an unsupported file type")
                self.logger.debug(f"File type: {mime_type}")
            except Exception as e:
                self.logger.error(f"Error determining file type of {fileName}: {e}")
                message.reply(f"Error determining file type of {fileName}: {e}")
                continue
            
            try:
                # Process the image/attachment
                if mime_type in ["image/png", "image/jpeg", "image/gif", "image/webp", "image/heic"]:
                    # Process the image
                    image = Image.open(fileName)
                    image = image.convert("RGB")
                    self.logger.debug(f"Image processed: {fileName} ({mime_type})")
                    
                    processed_attachments.append(image)
                    
                elif mime_type.split("/")[0] == "text":
                    # Process the text file
                    with open(fileName, "r") as f:
                        text = f.read()
                        self.logger.debug(f"Text file processed: {fileName}")
                        processed_attachments.append(text)
                    
                else:
                    # See if the file is in plain text
                    try:
                        with open(fileName, "r") as f:
                            text = f.read()
                            self.logger.debug(f"Text file processed (unsupported type): {fileName}")
                            processed_attachments.append(text)
                    except UnicodeDecodeError:       
                        self.logger.debug(f"Unsupported file type: {mime_type}")
                        await message.reply(f"You sent an unsupported file type! ({mime_type})")
                        continue
                
            except Exception as e:
                self.logger.error(f"Error processing attachment {attachment.filename}: {e}")
                message.reply(f"Error processing attachment {attachment.filename}: {e}")
                continue
            
        return processed_attachments

    async def _handle_embed(self, message: discord.Message) -> str:
        # if not message.embeds:
        #     return None
        # self.logger.debug(f"{len(message.embeds)} embeds found")
        # embeds_str = ""
        # for embed in message.embeds:
        #     embeds_str += f"Embed Title: {embed.title}\nEmbed Description: {embed.description}\nEmbed Fields:\n"
        #     for field in embed.fields:
        #         embeds_str += f"Field Name: {field.name}\nField Value: {field.value}\n"
        #     embeds_str += f"Embed Footer: {embed.footer.text}\nEmbed Author: {embed.author.name}\n"
        # self.logger.debug(f"Processed embeds: \n{embeds_str}")
        # return embeds_str
        if not message.embeds:
            return None
        
        self.logger.debug(f"{len(message.embeds)} embeds found")
        embeds_str = ""
        for embed in message.embeds:
            embeds_str += f"Author: {embed.author.name}\n"
            embeds_str += f"# {embed.title}\n{embed.description}\n"
            for field in embed.fields:
                embeds_str += f"## {field.name}\n{field.value}\n"
            embeds_str += f"# {embed.footer.text}\n{embed.author.name}\n"   
            
        self.logger.debug(f"Processed embeds: \n{embeds_str}")
        return embeds_str

    async def _add_memory(self, text: str):
        with open("store/gemini/memory.txt", "a") as f:
            f.write(f"{text}\n\n")
            return True

    async def _overwrite_memory(self, text: str):
        # Backup the memory
        with open("store/gemini/memory.txt", "r") as f:
            memory = f.read()
            memory_hash = hashlib.md5(memory.encode()).hexdigest()
            self.logger.debug(f"Memory hash: {memory_hash}")
            with open(f"store/memory_backup/{memory_hash}.txt", "w") as f:
                f.write(memory)

        # Overwrite the memory
        with open("store/gemini/memory.txt", "w") as f:
            f.write(f"{text}")
            return True

    async def _load_memory(self):
        # Check if the memory file and corresponding directory exists
        if not os.path.exists("store/gemini"):
            os.makedirs("store/gemini")
        if not os.path.exists("store/gemini/memory.txt"):
            with open("store/gemini/memory.txt", "w") as f:
                f.write("")
            return ""
        
        
        with open("store/gemini/memory.txt", "r") as f:
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
        self.logger.debug("Playing hide and seek")
        if message:
            guild = message.guild
        # Get all channels
        for i in range(100):
            channels = guild.text_channels
            random_channel = random.choice(channels)  # Select a random channel
            self.logger.debug(f"Random channel selected: {random_channel.name}")

            # Check if @everyone can view the channel
            if not random_channel.permissions_for(guild.default_role).send_messages:
                self.logger.debug(
                    f"Channel {random_channel.name} is not accessible by @everyone"
                )
                continue
            self.logger.debug(f"Channel {random_channel.name} is accessible by @everyone")

            # Get all messages in the channel within the last 24 hours

            a_day_ago = datetime.datetime.now() - timedelta.Timedelta(days=1)
            self.logger.debug(f"Searching for messages after {a_day_ago}")
            messages = [
                message async for message in random_channel.history(after=a_day_ago)
            ]
            if len(messages) == 0:
                self.logger.debug(f"No recent messages found in {random_channel.name}")
                continue
            # Select a random message
            random_message: discord.Message = random.choice(messages)
            # Check if message already has a reaction
            if random_message.reactions:
                self.logger.debug(
                    f"Message already has a reaction: {random_message.content}"
                )
                continue
            self.logger.debug(f"Random message selected: {random_message.content}")
            self.hide_seek_message = random_message
            break

        else:
            self.logger.debug("No suitable message found")
            raise Exception("No suitable message found after 100 attempts")
        # Add a reaction to the message
        await random_message.add_reaction("🔍")
        self.logger.debug(
            f"Reaction added to message: {random_message.content} in {random_channel.name}"
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
            self.logger.debug("Hide and Seek reaction added")

            await self.hide_seek_message.reply("You found me! 🎉")

            if hasattr(self, "hide_seek_from_gemini"):
                # Tell jerry to congratulate the user
                message_send = f"{await self._create_prompt(self.hide_seek_message)}\n\nHide and Seek completed. The user has found the message. Congratulate them! Use the ^*&send command to do so. It was found by {self.bot.get_user(payload.user_id).mention} in the channel {self.hide_seek_message.channel.name} on the message:\n```\n{self.hide_seek_message.content} {'[Image]' if self.hide_seek_message.attachments else ''}\n```."

                self.logger.debug(f"Sending message to gemini: {message_send}")

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
                self.logger.debug("Initiating hide and seek (shell)")
                guild_id = command.query.split(" ")[1]
                try:
                    guild_id_int = int(guild_id)
                    self.logger.debug(f"Guild ID: {guild_id_int}")
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
                    self.logger.debug(f"Guild: {guild.name}")
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
            self.logger.info("Checking model status")
            # Check if the model is ready by sending a test message
            prompt = "Answer the following question with either 'y' or 'n'; only state 'y' or 'n' in your response: Is 23 + 19 equal to 42?"
            answer = ""
            try:
                response = await self.model.generate_content_async(
                    prompt,
                )
                answer = response.text.strip().lower()
            except gemini_selling.ResourceExhausted:
                self.logger.error("Model is not ready; resource exhausted")
                return "Not ready; rate limited"
            except gemini_selling.PermissionDenied:
                self.logger.error("Model is not ready; permission denied")
                return "Not ready; permission denied"
            except Exception as e:
                self.logger.error(f"Error testing model: {e}")
                return f"Not ready; model is throwing error:\n{e}"
            if answer == "y":
                self.logger.error("Model is ready, got expected response")
                return "Ready; model is responding"
            elif answer == "n":
                self.logger.error("Model is ready, got incorrect response")
                return "Ready; model is responding but its math is not mathing"
            elif len(answer) > 1:
                self.logger.error(
                    f"Model is ready, got arbitrary response: {response.text}"
                )
                return "Ready; model is responding with an arbitrary response"
            else:
                self.logger.error("Model is not ready, got no response")
                return "Failed; model said nothing upon request"

        except Exception as e:
            self.logger.error(f"Error testing model: {e}")
            return f"Status check failed: {e}"


class AutoReplyV2(commands.Cog):
    """
    (V2) Listens for messages and replies with a set message configurable in a YAML file.
    """
    
    def __init__(self, bot: Jerry):
        self.bot = bot        
        self.logger = logging.getLogger("jerry.auto_reply")
        
        # Auto reply configuration
        self.auto_reply_file = "store/autoreply.yaml"
        
        self.auto_reply_cache = {}
        self.auto_reply_cache_timeout = 0 # Default
        self.auto_reply_cache_last_updated = 0
        
        # Default auto-reply configuration
        self.auto_reply = """
config:
  # The time in seconds to cache config files to reduce the amount of reads to the file system (Set to 0 to disable)
  cache_timeout: 500 # 10 minutes

vars:
    - generic_gaslighting:
          random:
              - { text: "Lies, all lies" }
              - { text: "Prove it" }
              - { text: "Sure you did" }
              - { text: "Cap" }
              - { text: "Keep dreaming" }
              - { text: "Keep telling yourself that" }
              - { text: "Yeah, and I'm a real person" }

autoreply:
    - regex: "^I really wanna trigger auto-reply by sending this message$"
      response:
            text: "Guess what? You just triggered an auto-reply!"
"""
        
    def _create_config(self):
        """Create the auto-reply configuration file if it doesn't exist"""
        if os.path.exists(self.auto_reply_file):
            self.logger.debug("Got create config request, but file already exists")
            return
        
        self.logger.info("Creating auto-reply configuration file")
        with open(self.auto_reply_file, "w") as f:
            f.write(self.auto_reply)
            
    def verify_config(self, config: dict) -> tuple:
        """Verify the auto-reply configuration"""
        if not config:
            return (False, "No configuration found")
        
        if config.get("config", None):
            self.auto_reply_cache_timeout = config["config"].get("cache_timeout", self.auto_reply_cache_timeout)
            
        if config.get("vars", None):
            if not isinstance(config["vars"], dict):
                return (False, "Variables config must be a dictionary")
            for name, response in config["vars"].items():
                verify = self._verify_response(response)
                if not verify[0]:
                    return verify
                
        if config.get("filters", None):
            if not isinstance(config["filters"], list):
                return (False, "Filters must be a list")
            for filter in config["filters"]:
                if not isinstance(filter, dict):
                    return (False, "Filter must be a dictionary")
                if not (filter.get("channel") or filter.get("user") or filter.get("guild")):
                    return (False, "Filter needs one of channel, user, or guild")
                
        if config.get("autoreply", None):
            for pattern in config["autoreply"]:
                if not isinstance(pattern, dict):
                    return (False, f"Pattern {pattern} is not a dictionary")
                
                if not (pattern.get("regex") or pattern.get("embed")):
                    return (False, f"Pattern {pattern} is missing its detection regex")
                
                if not pattern.get("response"):
                    return (False, f"Pattern {pattern} is missing its response")
                verify = self._verify_response(pattern["response"])
                
                if not verify[0]:
                    return (False, f"Pattern {pattern} response is invalid: {verify[1]}")
        else:
            return (False, "No auto-reply patterns found")
        
        return (True, None)
    
    def _verify_response(self, response: dict) -> tuple:
        """Check a specific response for required fields"""
        self.logger.debug(f"Verifying response: {response}")
        if response.get("text") and response.get("type", "text") == "text":
            try:
                str(response["text"])
            except:
                return (False, "Response text must be a string")
        if response.get("type") == "file":
            if not (response.get("path") or response.get("url")):
                return (False, "Response type is file, but no path or URL was provided")
        
        if response.get("type") == "random" or response.get("random"):
            if response.get("random"):
                for r in response["random"]:
                    verify = self._verify_response(r)
                    if not verify[0]:
                        return verify
            else:
                return (False, "Response type is random, but no responses were provided")
        
        if response.get("type") == "vars":
            if not isinstance(response.get("vars"), list):
                return (False, "Response type is vars, but no variables were provided")
            
            for var in response["vars"]:
                # Verify the variable (as a response)
                verify = self._verify_response(var)
                
                if not verify[0]:
                    return verify
        
        has_valid_keys = False
        for key in response.keys():
            if key not in ["text", "type", "random", "vars", "path", "url","bad"]:
                return (False, f"Response key `{key}` is invalid")
            else:
                has_valid_keys = True
            
        if not has_valid_keys:
            return (False, "Invalid response; no valid keys found")
        return (True, None)
        
            
    def get_config(self, cache: bool = True) -> dict:
        """Read the auto-reply configuration file. (Includes caching)"""
        if cache and self.auto_reply_cache_timeout > 0:
            # Check if the cache is still valid
            if self.auto_reply_cache_last_updated + self.auto_reply_cache_timeout > time.time():
                return self.auto_reply_cache
        
        self._create_config()
        
        try:
            with open(self.auto_reply_file, "r") as f:
                self.auto_reply_cache = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"Error reading auto-reply configuration: {e}")
            return {"invalid": True, "error": e, "error_type": "read"}
        
        # Verify the configuration
        verify = self.verify_config(self.auto_reply_cache)
        if not verify[0]:
            self.logger.error(f"Invalid auto-reply configuration: {verify[1]}")
            return {"invalid": True, "error": verify[1], "error_type": "verify"}
            
        self.auto_reply_cache_last_updated = time.time()
        
        return self.auto_reply_cache
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        
        await self.process_message(message)
        
    async def process_message(self, message: discord.Message):
        """Process a discord message for auto-reply"""
        
        config = self.get_config()
        
        if config.get("invalid"):
            await self.bot.shell.log(f"Auto-reply configuration error: {config.get('error', 'Unknown error')}", "Auto-Reply", msg_type="error", cog="AutoReply")
            return
        
        response = await self._scan_message(message, config)
        if not response:
            return
        
        await self._do_reponse(message, response)
        
    def _recursive_replace(self, input: any, replacements: dict):
        """Recursively replace values in a dictionary"""
        if isinstance(input, dict):
            for key, value in input.items():
                if isinstance(value, dict) or isinstance(value, list):
                    input[key] = self._recursive_replace(value, replacements)
                elif isinstance(value, str):
                    for k, v in replacements.items():
                        value = value.replace(k, v)
                    input[key] = value
                    
        elif isinstance(input, list):
            for i, value in enumerate(input):
                if isinstance(value, dict) or isinstance(value, list):
                    input[i] = self._recursive_replace(value, replacements)
                elif isinstance(value, str):
                    for k, v in replacements.items():
                        value = value.replace(k, v)
                    input[i] = value

        elif isinstance(input, str):
            for k, v in replacements.items():
                input = input.replace
        return input
        
    async def _scan_message(self, message: discord.Message, config: dict):
        """Scan a message for auto-reply patterns"""
        # Check for filters
        
        for filter in config.get("filters", []):
            if filter.get("type", "ignore"):
                if filter.get("channel", None) and filter["channel"] == message.channel.id:
                    return None

                if filter.get("user", None) and filter["user"] == message.author.id:
                    return None

                if filter.get("guild", None) and filter["guild"] == message.guild.id:
                    return None
        
        for pattern in config["autoreply"]:
            # Mentions
            # Recursively replace <@@me> and <@@author> with corresponding user mentions
            replacements = {
                "<@@me>": self.bot.user.mention,
                "<@@author>": message.author.mention,
            }
            
            pattern = self._recursive_replace(pattern, replacements)
            
            # Apply variables
            if pattern.get("vars"):
                for var in pattern["vars"]:
                    var = config.get("vars", {}).get(var, None)
                    if not var:
                        continue
                    if not isinstance(var, dict):
                        continue
                    
                    for key, value in var.items():
                        if isinstance(value, dict):
                            for key_of_key, value_of_key in value.items():
                                pattern[key][key_of_key] = value_of_key
                                
                        elif isinstance(value, list):
                            for i in value:
                                pattern[key].append(i)
                                
                        elif not pattern.get(key):
                            pattern[key] = value
            
            # Filters
            self.logger.debug(f"Bots are {'allowed' if pattern.get('bot', False) else 'not allowed'}. {message.author.name} is {'a bot' if message.author.bot else 'not a bot'}")
            if not pattern.get("bot", False) and message.author.bot:
                continue
            
            if pattern.get("filter", None):
                filters = pattern["filter"]
                
                # Check for filters
                if filters.get("channel", None) and filters["channel"] != message.channel.id:
                    continue
                
                if filters.get("user", None) and filters["user"] != message.author.id:
                    continue
                
                if filters.get("guild", None) and filters["guild"] != message.guild.id:
                    continue
                
            # Detection
            if pattern.get("regex"):
                if re.search(pattern["regex"], message.content, re.IGNORECASE):
                    return pattern["response"]
            
            if pattern.get("contains"):
                if pattern["contains"] in message.content:
                    return pattern["response"]
                
            if pattern.get("embed"):
                embed_regex = pattern["embed"]
                
                if not message.embeds:
                    continue
                
                for embed in message.embeds:
                    if embed_regex.get("title"):
                        if re.search(embed_regex["title"], embed.title, re.IGNORECASE):
                            return pattern["response"]
                    if embed_regex.get("description"):
                        if re.search(embed_regex["description"], embed.description, re.IGNORECASE):
                            return pattern["response"]
                    if embed_regex.get("author"):
                        if re.search(embed_regex["author"], embed.author.name, re.IGNORECASE):
                            return pattern["response"]
        return None
    
    async def _handle_file(self, url: str = None, path: str = None, config: dict = None) -> discord.File:
        """Retrieve a file from a URL or path"""
        directory = config.get("config", {}).get("image_cache_dir", "store/cache/autoreply")
        self.logger.debug(f"Hanlding file: {url} {path} | Directory: {directory}")
        
        if url:
            # Ensure the directory exists
            os.makedirs(directory, exist_ok=True)   
            path = os.path.join(directory, url.split("/")[-1])
            
            if not os.path.exists(path):
                self.logger.info(f"Downloading file from {url}")
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        with open(path, "wb") as f:
                            f.write(await resp.read())
                self.logger.info(f"File downloaded to {path}")
                
        if not os.path.exists(path):
            self.logger.error(f"File {path} not found")
            return None
        
        return discord.File(path)
        
    
    async def _do_reponse(self, message: discord.Message, response: dict):
        """Handle the auto-reply response"""
        
        if response.get("bad"):
            await message.delete()
            return
        
        if response.get("text"):
            if response.get("bad"):
                await message.channel.send(response["text"])
            else:
                await message.reply(response["text"])
            
        elif response.get("random"):
            await self._do_reponse(message, random.choice(response["random"]))
            
        elif response.get("type") == "file":
            if response.get("url"):
                file = await self._handle_file(url=response["url"], config=response)
            elif response.get("path"):
                file = await self._handle_file(path=response["path"], config=response)
            else:
                self.logger.error("File response is missing URL or path")
                return
            
            if file:
                if response.get("bad"):
                    await message.channel.send(file=file)
                else:
                    await message.reply(file=file)
            
        return


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
    def __init__(self, sticker_file: str, core: "CubbScratchStudiosStickerPack"):
        super().__init__()
        self.sticker_file = sticker_file
        self.core = core
        self.logger = core.logger

    @discord.ui.button(label="Send✅", style=discord.ButtonStyle.primary)
    async def send(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.logger.info(
            f"Confirming sending sticker {self.sticker_file}"
        )
        await interaction.response.send_message("Sending sticker...", ephemeral=True)
        try:
            file = discord.File(self.sticker_file)
        except Exception as e:
            self.logger.info(f"Error getting sticker: {e}")
            await interaction.followup.send(
                f"Error sending sticker: {e}", ephemeral=True
            )
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
        
        self.logger = logging.getLogger("jerry.css_sticker_pack")

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
            self.logger.info("Waiting for database to be ready")
            while not hasattr(self.bot, "db"):
                await asyncio.sleep(1)
        if not isinstance(self.bot.db, core.DatabaseCore):
            self.logger.info("Database not ready")
            while not isinstance(self.bot.db, core.DatabaseCore):
                await asyncio.sleep(1)

        self.db: core.DatabaseCore = self.bot.db
        await self.db.wait_until_ready()

        # Create table
        self.logger.info("Checking database table")
        try:
            await self.db.execute(self.TABLE_QUERY)
        except Exception as e:
            self.logger.error(f"Error creating table: {e}")
            return

        self.schema = self.db.data.get_schema(self.SCHEMA)
        self.table: core.DatabaseTable = self.schema.get_table(self.TABLE)

        self.logger.info("Indexing stickers")
        await self.index()
        self.logger.info("Successfully initialized")

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
        self.logger.debug(
            f"Converting Apple Type Image to PNG: {file_path}"
        )
        new_path = file_path.replace(".heic", ".png").replace(".heif", ".png")

        if os.path.exists(new_path):
            self.logger.debug(
                f"File {new_path} already exists, skipping"
            )
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
            self.logger.error(
                f"Error converting {file_path} to PNG: {e}"
            )
            return None

        self.logger.info(
            f"Converted {file_path} to PNG: {new_path}"
        )
        return new_path

    async def index(self):
        """Index all stickers in the directory and check if they are in the database"""
        self.logger.info("Indexing stickers")
        data = await self.table.fetch()
        unindexed = []
        missing = []

        # Optimize file paths & convert Apple type images
        self.logger.info("Optimizing file paths")
        while True:
            interrupted = False
            files = os.listdir(self.directory)
            for file in files:
                if ":Zone.Identifier" in file:
                    self.logger.debug(
                        f"Skipping file with Zone.Identifier: {file}"
                    )
                    continue

                if file.endswith(".heic") or file.endswith(".heif"):
                    new_path = await self.apple_to_better(f"{self.directory}/{file}")
                    if new_path:
                        os.remove(f"{self.directory}/{file}")
                        interrupted = True

                # Replace spaces with underscores
                if " " in file:
                    self.logger.debug(
                        f"Replacing spaces in file {file}"
                    )
                    new_file = file.replace(" ", "_")
                    try:
                        self.logger.debug(
                            f"Rename {self.directory}/{file} to {self.directory}/{new_file}"
                        )
                        os.rename(
                            f"{self.directory}/{file}", f"{self.directory}/{new_file}"
                        )
                    except PermissionError:
                        self.logger.error(
                            f"Unable to rename file {file} due to permission error (space)"
                        )
                    except FileNotFoundError:
                        self.logger.error(
                            f"Unable to rename file {file} due to file not found (space)"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Error renaming file {file}: {e} (space)"
                        )
                    interrupted = True
                    continue

                # Replace other special characters
                if re.search(r"[^a-zA-Z0-9_.-]", file):
                    new_file = re.sub(r"[^a-zA-Z0-9_.-]", "_", file)
                    try:
                        self.logger.debug(
                            f"Rename {self.directory}/{file} to {self.directory}/{new_file}"
                        )
                        os.rename(
                            f"{self.directory}/{file}", f"{self.directory}/{new_file}"
                        )
                    except PermissionError:
                        self.logger.error(
                            f"Unable to rename file {file} due to permission error (special characters)"
                        )
                    except FileNotFoundError:
                        self.logger.error(
                            f"Unable to rename file {file} due to file not found (special characters)"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Error renaming file {file}: {e} (special characters)"
                        )
                    interrupted = True
                    continue

            if not interrupted:
                self.logger.info("File paths optimized")
                break
            self.logger.debug(
                "Some files were optimized, checking again"
            )

        # Get all files in the directory (again)
        files = os.listdir(self.directory)

        # Remove Zone.Identifier files
        files = [file for file in files if ":Zone.Identifier" not in file]

        # Convert database data to a dictionary
        database_files = {}
        for entry in data:
            database_files[entry["file"]] = entry

        # Check if each file is in the database
        self.logger.info(f"Checking {len(files)} files")
        for file in files:
            self.logger.debug(f"Checking file {file}")

            if file not in database_files:
                self.logger.debug(f"File {file} not in database")
                unindexed.append(file)
                continue

            self.logger.debug(
                f"File {file} found in database as '{database_files[file]['slime']}/{database_files[file]['name']}'"
            )
            data.pop(data.index(database_files[file]))

        self.logger.info(f"Done checking files")

        self.logger.info(f"{len(unindexed)} files not in database")
        self.logger.info(
            f"{len(data)} entries missing from directory"
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
            self.logger.info("Entering interactive shell")
            await command.log("Entering interactive shell", title="Sticker Manager")

            self.bot.shell.interactive_mode = ("CubbScratchStudiosStickerPack", "cssss")

            await self._interactive(command, init=True)

        if command.name == "cssss":
            await self._interactive(command)

    async def _interactive(self, command: core.ShellCommand, init=False):
        """Interactive shell for managing the sticker pack"""
        self.logger.info("Interactive shell -> " + command.query)
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

            await command.raw(
                f"Are you sure you want to remove all unindexed files? (yes/no) This will irreversibly delete {len(self.unindexed)} files"
            )

            return

        if self._interactive_view == "index":
            # Index files
            if query == "_init":
                await command.raw(
                    "### File Wizard 🪄\nLet's index some files! 📁\nNote: It is suggested that you have a list of currently indexed files as there might be duplicates.\n\n**Quick Actions**\n- rm - Delete the current file and move on the the next one\n- reset - Made a mistake in entering everything? Use reset to start over"
                )
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

                summary += (
                    "Would you like to add this sticker to the database? (yes|edit)"
                )
                await command.raw(summary)

                return

            return

        self.logger.warning(
            "Interactive shell view not found"
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
    async def sticker_command(
        self,
        interaction: discord.Interaction,
        sticker: str,
        override_includes: bool = False,
    ):
        include_types = ["slime", "slime-text"]

        self.logger.info(f"Sticker requested: {sticker}")

        if not self.table:
            await interaction.response.send_message(
                "An error occurred while initializing the sticker pack", ephemeral=True
            )

        # Get sticker from database
        if not "/" in sticker:
            sticker = sticker + "/main"

        data = await self.table.fetch()
        stickers = {}
        for entry in data:
            stickers[entry["slime"] + "/" + entry["name"]] = entry

        stickers_as_list = list(stickers.keys())

        # Fuzzy search
        self.logger.info(f"Searching for sticker {sticker}")
        while True:
            matches = fuzzywuzzy.process.extract(sticker, stickers_as_list, limit=1)

            entry = stickers[matches[0][0]]
            if entry["format"] in include_types or override_includes:
                break

            stickers_as_list.pop(stickers_as_list.index(matches[0][0]))

        self.logger.info(f"Matches: {matches}")

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


class StaticCommands(commands.Cog):
    """Static commands that don't really do much, including api commands"""

    def __init__(self, bot: Jerry):
        self.bot = bot

        self.bot.shell.add_command(
            "api",
            cog="StaticCommands",
            description="Manage API keys",
        )

    @commands.Cog.listener()
    async def on_ready(self):
        print("[StaticCommands] Ready")

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
        name="purge",
        description="Purge messages from a channel",
    )
    @app_commands.describe(
        limit="The number of messages to delete",
    )
    async def purge_command(self, interaction: discord.Interaction, limit: int = None):
        # Check if user has permission
        if not interaction.channel.permissions_for(interaction.user).manage_messages:
            await interaction.response.send_message(
                "You don't have permission to delete messages", ephemeral=True
            )
            return

        if limit is not None and (limit > 100 or limit < 1):
            await interaction.response.send_message(
                "The limit cannot exceed 100", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Purging {limit if limit is not None else 'all'} messages... Beware of rate limits!",
            ephemeral=True,
        )

        # Purge messages
        try:
            if limit is None:
                await interaction.channel.purge()
            else:
                await interaction.channel.purge(limit=limit)
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to delete messages", ephemeral=True
            )
            return
        except Exception as e:
            await self.bot.shell.log(
                f"A purge command failed: {e}", "StaticCommands", msg_type="error"
            )
            await interaction.followup.send(
                "An error occurred while purging messages", ephemeral=True
            )

        await interaction.followup.send("Messages purged", ephemeral=True)

    @app_commands.command(
        name="help-jerry",
        description="Get help with Jerry",
    )
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Jerry Bot",
            description="I'm Jerry, a bot created by CubbScratchStudios. I'm designed as a server-specific bot, meaning I have features that are unique to each server I'm in. However, I also have some global features that are available in all servers.",
            color=0xFF5C5C,
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
        


class VoiceChat(commands.Cog):
    """Experimental cog for interacting with voice channels"""
    def __init__(self, bot: Jerry):
        self.bot = bot
        
        self.bot.shell.add_command("voice", cog="VoiceChat", description="Manage voice chat runners")
        
        self.stop = []
        self.running = []
        
        self.logger = logging.getLogger("jerry.voicechat")
        
    async def shell_callback(self, command: core.ShellCommand):
        if command.name == "voice":
            if command.query == "list":
                await command.log("Running instances: " + ", ".join(map(str, self.running)))
                return
            if command.query == "stop":
                self.stop = self.running
                await command.log("Stopped all voice chat instances", title="Stop All", msg_type="success")
                return
            fields = [
                {
                    "name": "Subcommands",
                    "inline": False,
                    "value": "list - List all running instances\nstop - Stop all running instances"
                }
            ]
            
            await command.log("To interact with voice chat, use the /play-sound and /stop-sound commands", fields=fields, title="Voice Chat", msg_type="info")
            return
            
    @app_commands.command(name="play-sound", description="Play a sound in a voice channel (experimental)")
    @app_commands.describe(
        stream="The stream to play",
    )
    async def play_sound(self, interaction: discord.Interaction, stream: str):
        try:
            await self.do_voice_chat(interaction.channel_id, interaction, stream)
        except Exception as e:
            self.logger.error(e)
            try:
                await interaction.followup.send("An unexpected error occurred", ephemeral=True)
            except:
                await interaction.response.send_message("An error occurred", ephemeral=True)
        
    @app_commands.command(name="stop-sound", description="Stop the sound in this voice channel (experimental)")
    async def stop_sound(self, interaction: discord.Interaction):
        self.stop.append(interaction.channel_id)
        await interaction.response.send_message("Stopping sound", ephemeral=True)
            
    async def do_voice_chat(self, channel_id: int, interaction: discord.Interaction, stream: str):
        """Test function to initiate voice chat"""
        self.logger.info("Initiating voice chat")
        
        streams = {
            "klove": "https://maestro.emfcdn.com/stream_for/k-love/web/aac",
            "rick": "https://squid1127.strangled.net/caddy/files/bait.MP3",
        }
        
        if stream.startswith("custom:"):
            stream = stream.split("custom:")[1]
            
        
        elif stream not in streams:
            comma_separated = ", ".join(streams.keys())
            
            await interaction.response.send_message("Invalid stream. Available streams: " + comma_separated + ". You can also use 'custom:URL' to play a custom stream", ephemeral=True)
            return
        
        else:
            stream = streams[stream]
        
        # Get the voice channel
        channel:discord.VoiceChannel = self.bot.get_channel(channel_id)
        
        # Check if the channel is a voice channel
        if not isinstance(channel, discord.VoiceChannel):
            self.logger.error("Channel is not a voice channel")
            await interaction.response.send_message("This is not a voice channel", ephemeral=True)
            return
        
        await interaction.response.send_message("Playing sound", ephemeral=True)
        
        # Connect to the voice channel
        self.logger.info(f"Connecting to voice channel {channel}")
        
        try:
            voice = await channel.connect()
        except discord.errors.ClientException:
            self.logger.error("Already playing in a voice channel")
            await interaction.followup.send("Already playing in this voice channel", ephemeral=True)
            return
        
        # Play a sound
        self.logger.info("Playing sound")
        try:
            source = discord.FFmpegPCMAudio(stream)
        except Exception as e:
            self.logger.error(f"Error loading sound: {e}")
            await interaction.followup.send(f"Error loading sound: {e}", ephemeral=True)
            # Disconnect
            await voice.disconnect()
            
            return
        
        try:
            voice.play(source, signal_type="music", bitrate=256, application="audio")
        except Exception as e:
            self.logger.error(f"Error playing sound: {e}")
            await interaction.followup.send(f"Error playing sound: {e}", ephemeral=True)
            # Disconnect
            await voice.disconnect()
            
            return
        self.running.append(channel_id)
        
        # Wait for the sound to finish
        manually_stopped = False
        self.logger.info("Waiting for sound to finish")
        while voice.is_playing():
            await asyncio.sleep(1)
            if channel_id in self.stop:
                manually_stopped = True
                self.stop.remove(channel_id)
                voice.stop()
                break
            
        try:
            self.running.remove(channel_id)
        except ValueError:
            pass
        
        # Disconnect
        self.logger.info("Disconnecting")
        await voice.disconnect()
        
        await interaction.followup.send(f"Sound {'finished' if not manually_stopped else 'stopped'}", ephemeral=True)
        


if __name__ == "__main__":
    print("You can't run this file directly dummy")
    sys.exit(1)

