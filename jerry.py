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

pillow_heif.register_heif_opener()  # Register the HEIF opener to process HEIF images

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
        shell_channel: int,
        **kwargs,
    ):
        # Initialize the bot
        super().__init__(
            token=discord_token, name="jerry", shell_channel=shell_channel, **kwargs
        )

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
    """V2 | Chat with Jerry, powered by Google Gemini"""

    def __init__(self, bot: Jerry):
        self.bot = bot
        self.instances = {}
        
        # Hide Seek Instances
        self.hide_seek_jobs = []

        # Logger
        self.logger = logging.getLogger("jerry.gemini")
        self.logger.info("Initializing")

        # Configuration
        self.files = self.bot.filebroker.configure_cog(
            "JerryGemini",
            config_file=True,
            config_default=self.DEFUALT_CONFIG,
            config_do_cache=300,
            cache=True,
            cache_clear_on_init=True,
        )
        self.files.init()
        self.load_config(init=True)

        # Add the Gemini command to the shell for managing Jerry's Gemini chat
        self.bot.shell.add_command(
            "gemini", cog="JerryGemini", description="Manage Jerry's Gemini chat"
        )

        self.logger.info("Successfully initialized")

    def load_config(self, init=False):
        """Load the global configuration"""
        # Fetch config
        self.logger.info("Loading global configuration")
        self.logger.debug("Fetching configuration")
        self.config = self.files.get_config()

        # Model config
        self.ai_token = self.config.get("global", {}).get("token")
        if not self.ai_token or self.ai_token == "CHANGE_ME":
            self.logger.error(
                "AI token not set; please set it in the configuration file (store/config/JerryGemini.yaml)"
            )
            return
        self.ai_model = (
            self.config.get("global", {}).get("ai", {}).get("model", "gemini-1.5-flash")
        )
        self.ai_top_p = self.config.get("global", {}).get("ai", {}).get("top_p", 0.95)
        self.ai_top_k = self.config.get("global", {}).get("ai", {}).get("top_k", 40)
        self.ai_temperature = (
            self.config.get("global", {}).get("ai", {}).get("temperature", 1.0)
        )
        
        # Discord Config
        self.emoji_default = self.config.get("global", {}).get("personal_emoji", "🐙")

        # Configure model
        self.logger.info("Configuring model")
        gemini.configure(api_key=self.ai_token)
        self.model = gemini.GenerativeModel(
            self.ai_model,
            generation_config=gemini.types.GenerationConfig(
                top_p=self.ai_top_p,
                top_k=self.ai_top_k,
                temperature=self.ai_temperature,
            ),
            safety_settings={
                "HARASSMENT": "BLOCK_NONE",
                "HATE": "BLOCK_NONE",
                "SEXUAL": "BLOCK_NONE",
                "DANGEROUS": "BLOCK_NONE",
            },
        )

        # Load instances
        self.logger.info("Loading instances")
        for instance in self.config.get("instances", []):
            channel = instance.get("channel")
            if not channel:
                self.logger.error("Channel ID not set in instance configuration")
                continue
            self.instances[channel] = JerryGeminiInstance(
                self, channel, self.config, instance
            )

        self.logger.info("Global configuration loaded")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle messages for JerryGemini"""
        if message.author == self.bot.user:
            return

        # Check if the message is in a JerryGemini channel
        if message.channel.id in self.instances:
            instance = self.instances[message.channel.id]

            # Pass to corresponding instance
            await instance.handle(message)
            
    # Hide and Seek
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle reactions for JerryGemini"""
        
        # Check if reaction is from Jerry
        if payload.user_id == self.bot.user.id:
            return
        
        # Check that there are active hide and seek jobs
        if len(self.hide_seek_jobs) == 0:
            return
        
        # Check if the reaction is the hide and seek emoji
        if payload.emoji.name != "🔍":
            return
        
        # Check if the message is in a hide and seek job
        for job in self.hide_seek_jobs:
            if job["message"].id == payload.message_id:
                # Get the instance
                instance = self.instances[job["instance_id"]]
                
                # Forward the message to the instance
                await instance._hide_seek_found(payload, job)
                
                # Remove the job
                self.hide_seek_jobs.remove(job)
    # Constants
    DEFUALT_CONFIG = """# Configuration for JerryGemini
global:
  # Google Generative AI API Token
  token: "CHANGE_ME"

  # Google Generative AI Model Config
  ai:
    model: gemini-1.5-flash
    top_p: 0.95
    model_top_k: 40
    model_temperature: 1.0

instances:
  - channel: change_to_channel_id
    addons:
      - hide-seek
      - files
"""

    NAME = "Jerry"
    PROMPT = f"""You are {NAME}, an intellegent experimental octopus. you are chatting in a discord channel.

Your name is {NAME}, you are displayed and characterized as a red octopus, your emoji and avatar is <:$jerry-emoji:> if anyone asks.

The user id of the member who sent the message is included in the request, feel free to use an @mention in place of their name. Mentions are formed like this: <@user id>. 

You are here to be helpful as well as entertain others with your intellegence. You are currently in a discord channel. You are talking to memebers if the server. """

    COMMAND_PREFIX = "%^&"
    COMMAND_SUFFIX = "&^%"
    COMMANDS_INTRO = (
        """To interact with the chat, you may use the following commands:"""
    )
    COMMANDS = {
        "send": "Respond with a message",
        "reset": "Reset/reinitialize the chat",
        "hide-seek": "Facilitate a hide and seek game. You will hide an emoji in a random message in a random channel (automaticly determined by the system). DO NOT USE UNLESS REQUESTED (you may only suggest it when appropriate). When using the command the system will alert you when the game is ready.",
        "dm": "Send a direct message to the user. Useful for sending private information. Hint: emojis are not supported in DMs. Be sure to also send the message in the regular chat.",
        "sticker": "Send a sticker from discord's sticker collection. Use the sticker id as the argument. DO NOT GUESS STICKER IDS.",
        "reaction": "React to the message sent by the user. Use the emoji as the argument. DO NOT OVERUSE. Be sure to also send the message the normal way (Unless you want to and the user sent a reaction). Multiple reactions can be added by using multiple commands.",
    }
    COMMANDS_DEFUALT = ["send", "reset","sticker","reaction"]
    COMMANDS_DIRECTIONS = f"""To use a command, type the command prefix followed by the command name. For example, "{COMMAND_PREFIX}send{COMMAND_SUFFIX} Let's play!{COMMAND_PREFIX}hide-seek{COMMAND_SUFFIX}" This will send the message "Let's play!" and start a hide and seek game. Multiple commands can be used in a single response. """

    CHANNEL_DESCRIPTION = f"""Chat with {NAME}, a chatbot powered by Google's Generative AI.
Commands:
    - reset: Reset the chat
    - hide-seek: Start a hide and seek game
    """

    async def generate_prompt(self, addons: list = [], emoji: str = None):
        """Generate a prompt for the chat"""
        prompt = self.PROMPT
        
        # Emoji
        if emoji:
            prompt = prompt.replace("<:$jerry-emoji:>", emoji)
        else:
            prompt = prompt.replace("<:$jerry-emoji:>", self.emoji_default)

        addons.extend(self.COMMANDS_DEFUALT)
        prompt += f"\n\n{self.COMMANDS_INTRO}"
        for command, description in self.COMMANDS.items():
            if command in addons:
                prompt += f"\n{self.COMMAND_PREFIX}{command}{self.COMMAND_SUFFIX} - {description}"
        prompt += f"\n{self.COMMANDS_DIRECTIONS}"

        return prompt


class JerryGeminiInstance:
    def __init__(
        self,
        core: JerryGemini,
        channel: int,
        global_config: dict,
        instance_config: dict,
    ):
        self.core = core
        self.channel_id = channel
        self.global_config = global_config
        self.instance_config = instance_config
        self.chat = None
        self.hs_logger = logging.getLogger(f"jerry.gemini.{channel}.hide_seek")
        self.logger = logging.getLogger(f"jerry.gemini.{channel}")

        self.logger.info(f"Initializing instance for channel {channel}")

        # Check for addons
        self.addons = self.instance_config.get("addons", [])
        self.logger.debug(f"Addons: {self.addons}")

        self.logger.info("Successfully initialized")

    async def start_chat(self):
        """Initialize the chat"""
        # Initialize the chat model
        self.logger.info("(Re)Starting chat")
        self.chat = self.core.model.start_chat()
        
        # Update the channel description
        try:
            channel:discord.TextChannel = self.core.bot.get_channel(self.channel_id)
            await channel.edit(
                topic=self.core.CHANNEL_DESCRIPTION,
            )
        except discord.Forbidden:
            self.logger.error("Failed to update channel description (Missing permissions)")
        
        return

    async def handle_embed(self, embed: discord.Embed) -> str:
        """Process an embed"""
        embed_str = ""
        if embed.author:
            embed_str += f"Author: '{embed.author.name}'\n"
        embed_str += f"# '{embed.title}'\n'{embed.description}'\n"
        for field in embed.fields:
            embed_str += f"## '{field.name}'\n'{field.value}'\n"
        if embed.footer:
            embed_str += f"### '{embed.footer.text}'"
        return embed_str

    async def generate_prompt(self, message: discord.Message):
        """Generate the prompt for the chat"""
        prompt = await self.core.generate_prompt(addons=self.addons, emoji=self.instance_config.get("personal_emoji"))
        
        # Inject additional information
        if self.instance_config.get("extra_prompt"):
            prompt += f"\n\n{self.instance_config.get('extra_prompt')}"

        # Handle reply
        if message.reference:
            # Fetch the reply
            reply = await message.channel.fetch_message(message.reference.message_id)
            if reply:
                prompt += f'\n\nIn reply to: {reply.author.display_name} (ID: {reply.author.id}), who said: \n"""{reply.content}"""'
                if reply.embeds:
                    prompt += f"Message embeds:\n"
                    for embed in reply.embeds:
                        prompt += f"\n{await self.handle_embed(embed)}"

        # Add message content
        prompt += f'\n\n{"In response " if message.reference else ""}{message.author.display_name} (ID: {message.author.id}) said: \n"""{message.content}"""'
        if message.stickers:
            for sticker in message.stickers:
                prompt += f"\nSticker: {sticker.name} (ID: {sticker.id})"

        # Handle embeds
        if message.embeds:
            prompt += f"Message embeds:\n"
            for embed in message.embeds:
                prompt += f"\n{await self.handle_embed(embed)}"

        return prompt

    async def handle_attachments(self, message: discord.Message, prompt: str):
        attachments = []
        for attachment in message.attachments:
            attachments.append((attachment, False))
        for embed in message.embeds:
            if embed.image:
                attachments.append((embed.image, True))
            if embed.thumbnail:
                attachments.append((embed.thumbnail, True))
        
        if len(attachments) == 0:
            return prompt
        
        if not "files" in self.addons:
            await message.channel.send(
                embed=discord.Embed(
                    title="Attachments Disabled",
                    description="Attachments are not enabled for this channel and will not be processed.",
                    color=discord.Color.red(),
                )
            )
            return prompt

        processed_attachments = [prompt]
        for attachment in attachments:
            attachment_processed = await self._handle_attachment(*attachment)
            if attachment_processed[1]:
                processed_attachments.append(attachment_processed[1])
            else:
                message.channel.send(
                    embed=discord.Embed(
                        title="Attachment Error",
                        description=f"Error processing attachment {attachment.filename}: {attachment_processed[0]}",
                        color=discord.Color.red(),
                    )
                )

        return processed_attachments

    async def _handle_attachment(self, attachment: discord.Attachment, image: bool = False):
        """Handle an attachment"""
        # Determine file name and location
        directory = self.core.files.get_cache_dir()
        file_name = os.path.join(directory, attachment.filename if attachment.filename else "attachment")

        # Download the file (overwrite if it exists)
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                with open(file_name, "wb") as f:
                    f.write(await resp.read())

        # Determine the file type
        mime_type, _ = mimetypes.guess_type(file_name)
        if mime_type is None:
            file_type = "unknown"
            self.logger.error(f"File type not found for {file_name}")
            return ("Unsupported file type", None)
        
        if mime_type in [
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
            "image/heic",
        ] or image:
            file_type = "image"
            try:
                # Process the image
                image = Image.open(file_name)
                return (None, image)
            except:
                self.logger.error(f"Error processing image: {file_name}")
                return ("Error processing image", None)

        # Check if the file is text
        if mime_type.split("/")[0] == "text":
            file_type = "text"

        # Try to read the file as text
        try:
            with open(file_name, "r") as f:
                text = f.read()
            return (None, text)
        except UnicodeDecodeError:
            self.logger.error(f"Unsupported file type: {mime_type}")
            return ("Unsupported file type", None)
        
    async def process_response(self, response: str, message: discord.Message):
        # Parse commands
        response = response.strip()
        commands = response.split(self.core.COMMAND_PREFIX)
        if len(commands) < 1:
            self.logger.warning("No commands found in response")
            commands = [response]
        self.logger.debug(f"Commands: {commands}")
        for command in commands:
            self.logger.debug(f"Command: {command}")
            # Remove leading/trailing whitespace
            command = command.strip()

            # Check for suffix
            if self.core.COMMAND_SUFFIX in command:
                action = command.split(self.core.COMMAND_SUFFIX)[0]
                if action == "" or action == None:
                    action = "send"
                if action not in self.core.COMMANDS:
                    self.logger.warning(f"Invalid command: {command}")
                    continue
                try:
                    args = command.split(self.core.COMMAND_SUFFIX)[1]
                except IndexError:
                    args = None
            else:
                action = "send"
                args = command
                
            self.logger.debug(f"Action: {action} | Args: {args}")
                
            await self.handle_action(action, args, message)
    
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
            
    async def handle_action(self, action: str, args: str, message: discord.Message):
        if action == "send":
            if len(args) == 0 or args is None:
                self.logger.warning("No message to send")
                return
            if len(args) > 2000:
                chunks = self._split_message(args)
                for chunk in chunks:
                    await message.channel.send(chunk)
                return
            await message.channel.send(args)
        elif action == "sticker":
            if len(args) == 0 or args is None:
                self.logger.warning("No sticker ID provided")
                return
            try:
                sticker_id = int(args.strip())
            except ValueError:
                self.logger.warning("Invalid sticker ID")
                return
            sticker = await self.core.bot.fetch_sticker(sticker_id)
            if not sticker:
                self.logger.warning("Sticker not found")
                return
            await message.channel.send(stickers=[sticker])
            
        elif action == "reaction":
            if len(args) == 0 or args is None:
                self.logger.warning("No reaction provided")
                return
            try:
                await message.add_reaction(args.strip())
            except discord.errors.HTTPException:
                self.logger.warning("Invalid reaction")
            
        elif action == "reset":
            await self.start_chat()
            await message.channel.send(
                embed=discord.Embed(
                    title="Chat Reset",
                    description=f"The chat has been reset; {self.core.NAME} has forgotten everything :(",
                    color=discord.Color.green(),
                )
            )
        elif action == "hide-seek":
            if "hide-seek" in self.addons:
                await self._hide_seek_init(message)
        elif action == "dm":
            if "dm" in self.addons:
                if len(args) == 0 or args is None:
                    self.logger.warning("No message to send")
                    return
                if len(args) > 2000:
                    chunks = self._split_message(args)
                    for chunk in chunks:
                        await message.author.send(chunk)
                    return
                await message.author.send(args)
        else:
            self.logger.warning(f"Invalid action: {action}")


    async def handle(self, message: discord.Message):
        """Process an incoming message"""
        try:
            self.logger.debug(f"Message received: {message.content}")
            # Typing indicator
            async with message.channel.typing():
                # Check if the chat is initialized
                if not self.chat:
                    self.logger.debug("Chat not initialized, initializing...")
                    await self.start_chat()

                # Generate the prompt
                self.logger.debug("Generating prompt")
                prompt = await self.generate_prompt(message)

                # Handle Attachments
                self.logger.debug("Handling attachments")
                content = await self.handle_attachments(message, prompt)

                # Send the message to the model
                self.logger.debug(f"Sending message to gemini:\n{content}")
                try:
                    response = await self.chat.send_message_async(content)
                except gemini_selling.ResourceExhausted:
                    await message.channel.send(
                        embed=discord.Embed(
                            title="Rate Limit",
                            description=f"{self.core.NAME} is tired and needs a break. Please try again later. {self.core.NAME} can only respond to a limited number of messages per minute. This number is not very high as {self.core.NAME} is a free service.",
                        ).set_footer(text="Resource Exhausted")
                    )
                    self.logger.warning("Resource exhausted")
                    return
                except gemini_selling.TooManyRequests:
                    await message.channel.send(
                        embed=discord.Embed(
                            title="Rate Limit",
                            description=f"{self.core.NAME} is tired and needs a break. Please try again later. {self.core.NAME} can only respond to a limited number of messages per minute. This number is not very high as {self.core.NAME} is a free service.",
                        ).set_footer(text="Too Many Requests")
                    )
                    self.logger.warning("Rate limited")
                    return
                self.logger.debug(f"Response received: {response.text}")

                # Process the response
                self.logger.debug("Processing response")
                await self.process_response(response.text, message)

        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            await message.channel.send(
                embed=discord.Embed(
                    title="Error Encountered",
                    description=f"An error occurred while processing your message.",
                    color=discord.Color.red(),
                )
            )
            await self.core.bot.shell.log(
                f"Failed to process incoming message: {e} \nChannel:\n({message.channel.mention} | {message.guild.id}/{message.channel.id})",
                title="Message Proccess Error",
                cog="JerryGemini",
                msg_type="error",
            )
            
    async def _model_system_request(self, request: str, message: discord.Message):
        """Send a system message to the model"""
        # Format the request
        prompt = await self.core.generate_prompt()
        
        # Append the request
        prompt += f"\n\nConversation Agent Alert: \n```\n{request}\n```"
        
        # Send the message to the model
        response = await self.chat.send_message_async(prompt)
        
        # Process the response
        await self.process_response(response.text, message)

    # Hide and seek
    async def _hide_seek_init(self, message: discord.Message):
        """Initiate a hide and seek game"""
        try:
            self.hs_logger.info("Initiating hide and seek game")
            edit = await message.channel.send(
                embed=discord.Embed(
                    title="Hide and Seek",
                    description="Starting a hide and seek game...",
                    color=discord.Color.yellow(),
                )
            )
            
            # Fetch a message to hide the emoji
            self.hide_seek_message = await self._hide_seek_find(message)
            
            # Add the emoji
            try:
                await self.hide_seek_message.add_reaction("🔍")
            except discord.errors.Forbidden:
                self.hs_logger.error("Failed to add reaction")
                await edit.edit(
                    embed=discord.Embed(
                        title="Hide and Seek",
                        description="An error occurred while starting the hide and seek game.",
                        color=discord.Color.red(),
                    )
                )
                return
            
            # Register the job
            information = {
                "instance_id": self.channel_id,
                "message": self.hide_seek_message,
                "request": message,
                "user": message.author,
                "notification": edit,
            }
            self.core.hide_seek_jobs.append(information)
            
            # Notify the user
            await edit.edit(
                embed=discord.Embed(
                    title="Hide and Seek",
                    description="Hide and seek started!",
                    color=discord.Color.blue(),
                )
            )
            
            # Notify the model
            request = "A hide and seek game has been initiated. The user needs to find a 🔍 reaction placed on a random message (Sent in the past 24 hours) in a random channel on this server. This system will alert when the user has found the reaction, so the user cannot cheat. Explain this to the user."
            await self._model_system_request(request, message)
            
        except Exception as e:
            try:
                await edit.edit(
                    embed=discord.Embed(
                        title="Hide and Seek",
                        description="Whoops! Something went wrong while starting the hide and seek game! :(",
                        color=discord.Color.red(),
                    )
                )
            except:
                self.hs_logger.error("Failed to edit message")
            self.hs_logger.error(f"Error initiating hide and seek game: {e}")
            try:
                await self._model_system_request(f"An error occurred while starting the hide and seek game: {e}", message)
            except:
                self.hs_logger.error("Failed to notify model")
        
    async def _hide_seek_found(self, payload: discord.RawReactionActionEvent, job: dict):
        """Handle a found hide and seek emoji"""
        request_message: discord.Message = job["request"]
        hidden_message: discord.Message = job["message"]
        notification: discord.Message = job["notification"]
        user: discord.User = job["user"]
        
        # Clear the reaction
        try:
            await hidden_message.clear_reaction("🔍")
        except discord.errors.Forbidden:
            self.hs_logger.warning("Failed to clear reaction; missing permissions")
            
        # Check mark!
        try:
            await hidden_message.add_reaction("✅")
            
            await asyncio.sleep(2)  
            
            await hidden_message.remove_reaction("✅", self.core.bot.user)
        except discord.errors.Forbidden:
            self.hs_logger.warning("Failed to add reaction; missing permissions")
        
            
        # Edit the notification
        await notification.edit(
            embed=discord.Embed(
                title="Hide and Seek",
                description=f"Hide and seek completed! {user.mention} found the emoji!",
                color=discord.Color.green(),
            )
        )
            
        # Notify the model
        request = f"{user.mention} found the emoji in the hide and seek game. The emoji was hidden in a message sent by {hidden_message.author.display_name} in channel {hidden_message.channel.name}. Congradulate {user.display_name} (ID: {user.id}) on finding the emoji."
        await self._model_system_request(request, request_message)
        
    async def _hide_seek_find(self, message: discord.Message) -> discord.Message:
        """Find the message to hide the emoji"""
        guild = message.guild
        
        if not guild:
            return None
        
        # Loop until a message is found
        self.hs_logger.info("Finding message to hide emoji")
        for i in range(50):
            # Fetch a random channel
            channel = random.choice(guild.text_channels)
            
            self.hs_logger.debug(f"Checking channel {channel.name}")
            
            # Determine channel permissions
            # Criteria: @everyone can send messages
            if not channel.permissions_for(guild.default_role).send_messages:
                self.hs_logger.debug("Channel does not allow @everyone to send messages")
                continue
            
            
            # Fetch a random message
            a_day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
            try:
                messages = [
                    message async for message in channel.history(after=a_day_ago)
                ]
                if len(messages) == 0:
                    self.hs_logger.debug("No recent messages found in channel")
                    continue
                message = random.choice(messages)
            except discord.errors.Forbidden:
                self.hs_logger.debug("Channel does not allow Jerry to read messages")
                continue
            except discord.errors.HTTPException:
                continue
            
            # Ensure message has no reactions
            if len(message.reactions) > 0:
                self.hs_logger.debug("Message has reactions; skipping")
                continue
            
            self.hs_logger.info(f"Found message to hide emoji: {message.content} (ID: {message.id}) in channel {channel.name}")
            return message

        self.hs_logger.error("Failed to find message to hide emoji")

class AutoReplyV2(commands.Cog):
    """
    (V2) Listens for messages and replies with a set message configurable in a YAML file.
    """

    def __init__(self, bot: Jerry):
        self.bot = bot
        self.logger = logging.getLogger("jerry.auto_reply")

        # Configuration
        self.files = self.bot.filebroker.configure_cog(
            "AutoReplyV2",
            config_file=True,
            config_default=self.DEFAULT_CONFIG,
            config_do_cache=300,
            cache=True,
            cache_clear_on_init=True,
        )
        self.files.init()

        self.auto_reply_cache = {}
        self.auto_reply_cache_timeout = 0  # Default
        self.auto_reply_cache_last_updated = 0

        # Command
        self.bot.shell.add_command(
            "autoreply", cog="AutoReplyV2", description="Manage Jerry's auto-reply"
        )

    # Default auto-reply configuration
    DEFAULT_CONFIG = """# Default Config for the AutoReply cog
config:
  # The time in seconds to cache config files to reduce the amount of reads to the file system (Set to 0 to disable)
  cache_timeout: 500 # 10 minutes

  # Directory to store image downloads. 
  # image_cache_dir: "store/cache/AutoReplyV2"

# filters:
#   - type: "ignore"
#     channel: 123456789012345678


vars:
  generic_gaslighting:
    random:
      - text: "Lies, all lies"
      - text: "Prove it"
      - text: "Sure you did"

autoreply:
  # Nuh-uh and Yuh-uh
  - regex: "nuh+[\\\\W_]*h?uh"
    response:
      text: Yuh-uh ✅

  - regex: "yuh+[\\\\W_]*h?uh"
    response:
      text: Nuh-uh ❌

"""

    def verify_config(self, config: dict) -> tuple:
        """Verify the auto-reply configuration"""
        if not config:
            return (False, "No configuration found")

        if config.get("config", None):
            self.auto_reply_cache_timeout = config["config"].get(
                "cache_timeout", self.auto_reply_cache_timeout
            )

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
                if not (
                    filter.get("channel") or filter.get("user") or filter.get("guild")
                ):
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
                    return (
                        False,
                        f"Pattern {pattern} response is invalid: {verify[1]}",
                    )
        else:
            return (False, "No auto-reply patterns found")

        return (True, None)

    def _verify_response(self, response: dict) -> tuple:
        """Check a specific response for required fields"""
        self.logger.debug(f"Verifying response: {response}")
        if not isinstance(response, dict):
            return (False, "Response must be a dictionary")

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
                return (
                    False,
                    "Response type is random, but no responses were provided",
                )

        if response.get("vars") or response.get("var"):
            variables = response.get("vars", response.get("var"))
            if isinstance(variables, str):
                variables = [variables]
            elif not isinstance(variables, list):
                return (
                    False,
                    "vars must be a list of variable names or a single variable name",
                )

        has_valid_keys = False
        for key in response.keys():
            if key not in ["text", "type", "random", "vars", "path", "url", "bad"]:
                return (False, f"Response key `{key}` is invalid")
            else:
                has_valid_keys = True

        if not has_valid_keys:
            return (False, "Invalid response; no valid keys found")
        return (True, None)

    def get_config(self, cache: bool = True) -> dict:
        """Read the auto-reply configuration file. (Includes caching)"""
        # if cache and self.auto_reply_cache_timeout > 0:
        #     # Check if the cache is still valid
        #     if (
        #         self.auto_reply_cache_last_updated + self.auto_reply_cache_timeout
        #         > time.time()
        #     ):
        #         return self.auto_reply_cache

        # try:
        #     with open(self.auto_reply_file, "r") as f:
        #         self.auto_reply_cache = yaml.safe_load(f)
        # except Exception as e:
        #     self.logger.error(f"Error reading auto-reply configuration: {e}")
        #     return {"invalid": True, "error": e, "error_type": "read"}

        # Use new built in filebroker
        config = self.files.get_config()
        if not config:
            return {
                "invalid": True,
                "error": "No configuration found",
                "error_type": "read",
            }

        # Verify the configuration
        verify = self.verify_config(config)
        if not verify[0]:
            self.logger.error(f"Invalid auto-reply configuration: {verify[1]}")
            self.files.invalidate_config()
            return {"invalid": True, "error": verify[1], "error_type": "verify"}

        return config

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        await self.process_message(message)

    async def process_message(self, message: discord.Message):
        """Process a discord message for auto-reply"""

        config = self.get_config()

        if config.get("invalid"):
            await self.bot.shell.log(
                f"Auto-reply configuration error: {config.get('error', 'Unknown error')}",
                "Auto-Reply",
                msg_type="error",
                cog="AutoReply",
            )
            return

        self.logger.debug(config)

        response = await self._scan_message(message, config)
        if not response:
            self.logger.debug("No response found")
            return

        self.logger.debug(response)

        await self._do_reponse(message, response, config)

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
                if (
                    filter.get("channel", None)
                    and filter["channel"] == message.channel.id
                ):
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

            # Filters
            self.logger.debug(
                f"Bots are {'allowed' if pattern.get('bot', False) else 'not allowed'}. {message.author.name} is {'a bot' if message.author.bot else 'not a bot'}"
            )
            if not pattern.get("bot", False) and message.author.bot:
                continue

            if pattern.get("filter", None):
                filters = pattern["filter"]

                # Check for filters
                if (
                    filters.get("channel", None)
                    and filters["channel"] != message.channel.id
                ):
                    continue

                if filters.get("user", None) and filters["user"] != message.author.id:
                    continue

                if filters.get("guild", None) and filters["guild"] != message.guild.id:
                    continue

                if filters.get("display_name", None):
                    # Process regex for display name
                    name = message.author.display_name
                    if not re.search(filters["display_name"], name, re.IGNORECASE):
                        continue

                if filters.get("username", None):
                    # Process regex for username
                    if not re.search(
                        filters["username"], message.author.name, re.IGNORECASE
                    ):
                        continue

                if filters.get("roles_any", None):
                    # Check if the user has any of the roles
                    for role_id in filters["roles_any"]:
                        role = discord.utils.get(message.author.roles, id=role_id)
                        if role:
                            break
                    else:
                        continue

                if filters.get("roles_all", None):
                    # Check if the user has all of the roles
                    for role_id in filters["roles_all"]:
                        role = discord.utils.get(message.author.roles, id=role_id)
                        if not role:
                            break
                    else:
                        continue

                if filters.get("role", None):
                    # Check if the user has the role
                    role = discord.utils.get(message.author.roles, id=filters["role"])
                    if not role:
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
                        if re.search(
                            embed_regex["description"], embed.description, re.IGNORECASE
                        ):
                            return pattern["response"]
                    if embed_regex.get("author"):
                        if re.search(
                            embed_regex["author"], embed.author.name, re.IGNORECASE
                        ):
                            return pattern["response"]
        return None

    async def _handle_file(
        self, url: str = None, path: str = None, config: dict = None
    ) -> discord.File:
        """Retrieve a file from a URL or path"""
        directory = config.get("config", {}).get(
            "image_cache_dir", self.files.get_cache_dir()
        )
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

    async def _do_reponse(
        self, message: discord.Message, response: dict, config: dict = None
    ):
        """Handle the auto-reply response"""

        # Apply variables
        if response.get("vars") or response.get("var"):
            variables = response.get("vars", response.get("var"))
            if isinstance(variables, str):
                variables = [variables]

            self.logger.debug(f"Variables: {variables}")
            for var in variables:
                if var in config.get("vars", {}):
                    var_payload = config["vars"][var]
                    for key, value in var_payload.items():
                        # Add each key to the response
                        self.logger.debug(f"Adding variable {key} to the response")
                        # Check if the key is already in the response
                        if response.get(key):
                            # If the key is a list, merge the lists
                            if isinstance(response[key], list) and isinstance(
                                value, list
                            ):
                                response[key].extend(value)
                                self.logger.debug(
                                    f"Added {value} to {key} (List extension)"
                                )
                            # If the key is a dictionary, try to merge the dictionaries, preserving the original values where possible
                            elif isinstance(response[key], dict) and isinstance(
                                value, dict
                            ):
                                for k, v in value.items():
                                    if k not in response[key]:
                                        response[key][k] = v
                                        self.logger.debug(
                                            f"Added {k} to {key} (Dict extension)"
                                        )

                            # Otherwise leave it as is
                            else:
                                self.logger.debug(
                                    f"Variable {key} already in response; cannot merge"
                                )
                        else:
                            self.logger.debug(f"Set {key} to {value} (Not in response)")
                            response[key] = value

        if response.get("bad"):
            await message.delete()
            return

        if response.get("text"):
            if response.get("bad"):
                await message.channel.send(response["text"])
            else:
                await message.reply(response["text"])

        elif response.get("random"):
            await self._do_reponse(
                message, random.choice(response["random"]), config=config
            )

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

    async def shell_callback(self, command: core.ShellCommand):
        if command.name == "autoreply":
            sub_command = command.query.split(" ")[0]

            if sub_command == "reload":
                self.auto_reply_cache = {}
                self.auto_reply_cache_last_updated = 0
                self.get_config(cache=False)
                await command.log(
                    "Auto-reply configuration reloaded",
                    "Auto-Reply",
                    msg_type="success",
                )
                return

            await command.log(
                "Available commands:\n- **reload** - Reload the auto-reply configuration",
                "Auto-Reply",
            )
            return


class GuildStuff(commands.Cog):
    """A experimental cog for finding guild stats and other stuff"""

    def __init__(self, bot: Jerry):
        self.bot = bot
        self.logger = logging.getLogger("jerry.guild_stuff")

    @app_commands.command(
        name="server",
        description="[Experimental] Get information about this guild (server)",
    )
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


class InformationChannels(commands.Cog):
    def __init__(self, bot: Jerry, file: str):
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


class StickerEphemeralView(discord.ui.View):
    def __init__(self, sticker_file: str, core: "CubbScratchStudiosStickerPack"):
        super().__init__()
        self.sticker_file = sticker_file
        self.core = core
        self.logger = core.logger

    @discord.ui.button(label="Send✅", style=discord.ButtonStyle.primary)
    async def send(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.logger.info(f"Confirming sending sticker {self.sticker_file}")
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
        self.logger.debug(f"Converting Apple Type Image to PNG: {file_path}")
        new_path = file_path.replace(".heic", ".png").replace(".heif", ".png")

        if os.path.exists(new_path):
            self.logger.debug(f"File {new_path} already exists, skipping")
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
            self.logger.error(f"Error converting {file_path} to PNG: {e}")
            return None

        self.logger.info(f"Converted {file_path} to PNG: {new_path}")
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
                    self.logger.debug(f"Skipping file with Zone.Identifier: {file}")
                    continue

                if file.endswith(".heic") or file.endswith(".heif"):
                    new_path = await self.apple_to_better(f"{self.directory}/{file}")
                    if new_path:
                        os.remove(f"{self.directory}/{file}")
                        interrupted = True

                # Replace spaces with underscores
                if " " in file:
                    self.logger.debug(f"Replacing spaces in file {file}")
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
                        self.logger.error(f"Error renaming file {file}: {e} (space)")
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
            self.logger.debug("Some files were optimized, checking again")

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
        self.logger.info(f"{len(data)} entries missing from directory")

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

        self.logger.warning("Interactive shell view not found")
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

        self.bot.shell.add_command(
            "voice", cog="VoiceChat", description="Manage voice chat runners"
        )

        self.stop = []
        self.running = []

        self.logger = logging.getLogger("jerry.voicechat")

    async def shell_callback(self, command: core.ShellCommand):
        if command.name == "voice":
            if command.query == "list":
                await command.log(
                    "Running instances: " + ", ".join(map(str, self.running))
                )
                return
            if command.query == "stop":
                self.stop = self.running
                await command.log(
                    "Stopped all voice chat instances",
                    title="Stop All",
                    msg_type="success",
                )
                return
            fields = [
                {
                    "name": "Subcommands",
                    "inline": False,
                    "value": "list - List all running instances\nstop - Stop all running instances",
                }
            ]

            await command.log(
                "To interact with voice chat, use the /play-sound and /stop-sound commands",
                fields=fields,
                title="Voice Chat",
                msg_type="info",
            )
            return

    @app_commands.command(
        name="play-sound", description="Play a sound in a voice channel (experimental)"
    )
    @app_commands.describe(
        stream="The stream to play",
    )
    async def play_sound(self, interaction: discord.Interaction, stream: str):
        try:
            await self.do_voice_chat(interaction.channel_id, interaction, stream)
        except Exception as e:
            self.logger.error(e)
            try:
                await interaction.followup.send(
                    "An unexpected error occurred", ephemeral=True
                )
            except:
                await interaction.response.send_message(
                    "An error occurred", ephemeral=True
                )

    @app_commands.command(
        name="stop-sound",
        description="Stop the sound in this voice channel (experimental)",
    )
    async def stop_sound(self, interaction: discord.Interaction):
        self.stop.append(interaction.channel_id)
        await interaction.response.send_message("Stopping sound", ephemeral=True)

    async def do_voice_chat(
        self, channel_id: int, interaction: discord.Interaction, stream: str
    ):
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

            await interaction.response.send_message(
                "Invalid stream. Available streams: "
                + comma_separated
                + ". You can also use 'custom:URL' to play a custom stream",
                ephemeral=True,
            )
            return

        else:
            stream = streams[stream]

        # Get the voice channel
        channel: discord.VoiceChannel = self.bot.get_channel(channel_id)

        # Check if the channel is a voice channel
        if not isinstance(channel, discord.VoiceChannel):
            self.logger.error("Channel is not a voice channel")
            await interaction.response.send_message(
                "This is not a voice channel", ephemeral=True
            )
            return

        await interaction.response.send_message("Playing sound", ephemeral=True)

        # Connect to the voice channel
        self.logger.info(f"Connecting to voice channel {channel}")

        try:
            voice = await channel.connect()
        except discord.errors.ClientException:
            self.logger.error("Already playing in a voice channel")
            await interaction.followup.send(
                "Already playing in this voice channel", ephemeral=True
            )
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

        await interaction.followup.send(
            f"Sound {'finished' if not manually_stopped else 'stopped'}", ephemeral=True
        )


if __name__ == "__main__":
    print("You can't run this file directly dummy")
    sys.exit(1)
