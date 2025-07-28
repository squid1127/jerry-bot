# Packages
import logging
import json
import asyncio
from typing import Any, Dict, Optional
import abc
from enum import Enum

# System
import os

# Discord
import discord
from discord import app_commands
from discord.ext import commands

import json

# Time
from pytz import timezone  # For timezones
import time
from datetime import timedelta, datetime

# squid-core
import core
import logging

# Gemini
from .constants import ConfigDefaults, ConfigFileDefaults
from .config import JerryGeminiConfig, ConfigStatus
from .ai import ChatInstance
from .providers import AIProvider
from .ai_types import (
    AIQueryDiscordRefrences,
    AIQueryUserAuthor,
    AIResponse,
    AIQuery,
    AIMethodCall,
    AIQuerySource,
    AIQueryDiscordRefrences,
)
from .files import FileProcessor
from .prompts import ResponseTools


class JerryGemini(commands.Cog):
    """
    JerryGemini is a class that represents the Gemini AI integration for the Jerry Bot.
    It handles discord actions, configuration management, and AI provider initialization.
    """

    def __init__(self, bot: core.Bot):
        """
        Initializes the JerryGemini instance with the provided bot instance.

        Args:
            core.Bot: The bot instance to be used for interactions.
        """
        self.bot = bot
        self.instances = {}
        self.name = ConfigDefaults.AI_NAME
        self.logger = logging.getLogger("jerry.JerryGemini.core")

        self.logger.info("Initializing")

        # Configuration
        self.config = JerryGeminiConfig(bot)

        # Add the Gemini command to the shell for managing Jerry's Gemini chat
        self.bot.shell.add_command(
            "gemini", cog="JerryGemini", description="Manage Jerry's Gemini chat"
        )

        self.logger.info("Successfully initialized")

        self.channel_list = self.config.get_channel_list()
        self.logger.info(
            f"Loaded {len(self.channel_list)} channels from config: {', '.join(map(str, self.channel_list))}"
        )

    async def chat_input(
        self,
        channel: discord.TextChannel,
        user: discord.User,
        query: AIQuery,
        command_mode: bool = False,
    ):
        """
        Sends a chat message to the AI model and receives a response.

        Args:
            channel (discord.TextChannel): The channel where the message is sent.
            user (discord.User): The user who sent the message.
            query (AIQuery): The query to send to the AI model.
            command_mode (bool): Whether the chat is in command mode.
        """
        if self.config.status != ConfigStatus.LOADED:
            return
        # Validate the channel type
        if not isinstance(channel, discord.TextChannel):
            return  # Invalid channel type, expected discord.TextChannel

        # Ensure the channel is in the list of channels to handle
        if (channel.id not in self.channel_list) and not command_mode:
            self.logger.debug(f"Channel {channel.id} not in channel list, ignoring")
            return

        # Ensure the channel has an instance
        if channel.id not in self.instances:
            self.logger.info(
                f"Initializing new chat instance for channel {channel.id} (#{channel.name} / {channel.guild.name})"
            )
            if command_mode:
                # If in command mode, reset the instance to start a new chat
                self.logger.info(
                    f"Resetting chat instance for channel {channel.id} (#{channel.name} / {channel.guild.name})"
                )
                command_id = self.config.config["global"].get(
                    "jerry_command_instance_id"
                )
                command_config = self.config.config["instances"].get(command_id)
                if not (command_config and command_id):
                    raise ValueError(
                        "Jerry command instance ID not set in config. Please set 'jerry_command_instance_id' in the global config."
                    )
                self.logger.info(f"Creating command-based chat instance")
                self.instances[channel.id] = ChatInstance(
                    config=command_config,
                    id=channel.id,
                )
            else:
                self.logger.info(
                    f"Creating new chat instance for channel {channel.id} (#{channel.name} / {channel.guild.name})"
                )
                self.instances[channel.id] = ChatInstance(
                    config=self.config.config["instances"][channel.id],
                    id=channel.id,
                )

        # Pass the query to instance
        self.logger.debug(
            f"Processing query in channel {channel.id} (#{channel.name} / {channel.guild.name})"
        )
        instance: ChatInstance = self.instances[channel.id]

        # Pass response_method to the instance
        query.response_method = self.do_response

        # TODO: Add try except for handling AIProvider errors
        if not command_mode:
            await channel.typing()  # Indicate that the bot is typing
        self.logger.debug(f"Sending query to ChatInstance {instance.channel_id}")
        responses: AIResponse = await instance.chat_input(
            query=query,
        )

        # * Now handled by the instance
        # self.logger.debug(f"Received response from ChatInstance {instance.channel_id}")
        # for response in responses:
        #     if not isinstance(response, AIResponse):
        #         self.logger.error(
        #             f"Received non-AIResponse object: {response} in channel {channel.id}"
        #         )
        #         continue
        #     await self.do_response(discord_objects=AIQueryDiscordRefrences(channel=channel, member=user), response=response)

    async def do_response(
        self, response: AIResponse, discord_objects: AIQueryDiscordRefrences
    ):
        if discord_objects.interaction is not None:
            self.logger.info(f"Using interaction mode")
            await self.do_response_interaction(
                response=response, discord_objects=discord_objects
            )
            return

        channel = discord_objects.channel
        user = discord_objects.member

        # Debug logging
        self.logger.debug(
            f"Sending response to channel {channel.id}/#{channel.name} ({channel.guild.name})"
        )
        self.logger.debug(
            f"Response has {'text' if response.text else 'no text'} {'embeds' if response.embeds else 'no embeds'} {'files' if response.files else 'no files'}"
        )
        self.logger.debug(f"Source: {response.source.value}")

        # Send the response back to the channel
        if response.text:
            self.logger.debug(f"Sending response to channel {channel.id}")
            parts = ResponseTools.apply_length_limit(response.text, max_length=2000)
            for part in parts:
                if part:
                    try:
                        if parts.index(part) == len(parts) - 1 and response.embeds:
                            # If it's the last part, send it as a normal message
                            await channel.send(
                                part,
                                embeds=[
                                    discord.Embed.from_dict(embed)
                                    for embed in response.embeds
                                ],
                            )
                            return  # Skip sending the embeds again
                        else:
                            # Otherwise, send it as a normal message
                            await channel.send(part)
                    except discord.HTTPException as e:
                        self.logger.error(
                            f"Failed to send message in channel {channel.id}: {e}"
                        )
                        # Optionally, handle the error (e.g., log it, notify the user, etc.)

        if response.embeds:
            # If there are embeds, send them as a separate message
            try:
                await channel.send(
                    embeds=[discord.Embed.from_dict(embed) for embed in response.embeds]
                )
            except discord.HTTPException as e:
                self.logger.error(f"Failed to send embeds in channel {channel.id}: {e}")
                # Optionally, handle the error (e.g., log it, notify the user, etc.)

        if response.files:
            # If there are files, send them as attachments
            for file in response.files:
                try:
                    self.logger.info(
                        f"Sending file {file.filename} in channel {channel.id} ({file.content_type}) "
                    )
                    # Ensure the file has
                    fp = (
                        file.buffered_data
                        if file.discord_use_buffered_data
                        else file.raw_data
                    )
                    await channel.send(
                        content="",
                        file=discord.File(
                            fp=fp,
                            filename=file.filename,
                        ),
                    )
                except discord.HTTPException as e:
                    self.logger.error(
                        f"Failed to send file {file.filename} in channel {channel.id}: {e}"
                    )
                    # Optionally, handle the error (e.g., log it, notify the user, etc.)

    # Message Event Listener
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Listens for messages in the Discord server and processes them.

        Args:
            message (discord.Message): The message to process.
        """
        if message.author == self.bot.user:
            return
        if (
            (message.content == "" or message.content.isspace() or not message.content)
            and (not message.attachments)
            and (not message.embeds)
        ):
            self.logger.debug("Ignoring empty message")
            return

        if message.embeds and len(message.embeds) > 0:
            embeds = [embed.to_dict() for embed in message.embeds]
        else:
            embeds = []

        query = AIQuery(
            message=message.content,
            source=AIQuerySource.USER,
            author=AIQueryUserAuthor(
                id=message.author.id,
                username=message.author.name,
                display_name=message.author.display_name,
                mention=message.author.mention,
            ),
            discord=AIQueryDiscordRefrences(
                message=message,
                channel=message.channel,
                guild=message.guild,
                member=message.author,
            ),
            embeds=embeds,
        )

        if message.reference and message.reference.resolved:
            # If the message is a reply, set the is_reply flag and reference the original message
            query.is_reply = True
            original_message = message.reference.resolved
            query.reply = AIQuery(
                message=original_message.content,
                source=AIQuerySource.USER,
                author=AIQueryUserAuthor(
                    id=original_message.author.id,
                    username=original_message.author.name,
                    display_name=original_message.author.display_name,
                    mention=original_message.author.mention,
                ),
                discord=AIQueryDiscordRefrences(
                    message=original_message,
                    channel=original_message.channel,
                    member=original_message.author,
                    guild=original_message.guild,
                ),
                embeds=[embed.to_dict() for embed in original_message.embeds],
            )

        if message.attachments and len(message.attachments) > 0:
            await FileProcessor.process_files(
                query=query, attachments=message.attachments
            )

        await self.chat_input(channel=message.channel, user=message.author, query=query)

    # Reaction Event Listener
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """
        Listens for reactions added to messages in the Discord server and processes them.

        Args:
            reaction (discord.Reaction): The reaction that was added.
            user (discord.User): The user who added the reaction.
        """
        if user == self.bot.user:
            return
        if not reaction.message or not reaction.message.content:
            self.logger.debug("Ignoring reaction on a message without content")
            return

        query = AIQuery(
            reaction=reaction.emoji,
            message=reaction.message.content,
            source=AIQuerySource.USER,
            author=AIQueryUserAuthor(
                id=user.id,
                username=user.name,
                display_name=user.display_name,
                mention=user.mention,
            ),
            discord=AIQueryDiscordRefrences(
                message=reaction.message,
                channel=reaction.message.channel,
                guild=reaction.message.guild,
                member=reaction.message.author,
            ),
        )

        await self.chat_input(channel=reaction.message.channel, user=user, query=query)

    @app_commands.command(
        name="gemini-reset",
        description="[Jerry Gemini] Start a new conversation with Jerry by giving him dementia.",
    )
    @app_commands.guild_only()  # Only can be used in guilds its installed in
    @app_commands.guild_install()
    async def gemini_reset(self, interaction: discord.Interaction):
        """
        Resets the conversation with Jerry by giving him dementia.
        """
        if interaction.channel_id not in self.instances:
            await interaction.response.send_message(
                "No active conversation found. Please start a new conversation first.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=False)
        instance: ChatInstance = self.instances[interaction.channel_id]
        instance.provider.start_chat()
        self.logger.info(f"Resetting conversation in channel {interaction.channel_id}")
        await interaction.followup.send(
            embed=discord.Embed(
                title="Conversation Reset",
                description="New chat session started. Jerry has forgotten everything D:",
                color=discord.Color.red(),
            ),
            ephemeral=True,
        )

    async def shell_callback(self, command: core.ShellCommand):
        if command.name == "gemini":
            sub_command = command.query.split(" ")[0]

            if sub_command == "reload":
                # Reload the Gemini configuration
                self.logger.info("Reloading Gemini configuration")
                self.instances.clear()  # Clear existing instances
                self.config.load_config()
                if self.config.status != ConfigStatus.LOADED:
                    await command.log(
                        f"Failed to reload Gemini configuration: {self.config.error}",
                        "Jerry Gemini Reload Failed",
                        msg_type="error",
                    )
                    return
                await command.log(
                    "Gemini configuration reloaded",
                    "Jerry Gemini Reloaded",
                    msg_type="success",
                )
                return

            if sub_command == "status":
                # Get the status of the JerryGemini cog
                status = await self._detailed_status()
                await command.log(
                    status,
                    "Jerry Gemini Status",
                    msg_type="info",
                )
                return

            if sub_command == "query":
                # Usage: gemini query <channel_id> <source> <query>
                parts = command.query.split(" ", 3)
                if len(parts) < 4:
                    await command.log(
                        "Usage: gemini query <channel_id> <source> <query>",
                        "Jerry Gemini Query Error",
                        msg_type="error",
                    )
                    return
                channel_id = int(parts[1])
                source = parts[2].lower()
                query_text = parts[3]

                if not channel_id in self.instances:
                    await command.log(
                        f"Channel {channel_id} not found in active instances.",
                        "Jerry Gemini Query Error",
                        msg_type="error",
                    )
                    return

                await self._manual_query(
                    channel_id=channel_id,
                    source=source,
                    query_text=query_text,
                    command=command,
                )

    async def cog_status(self) -> str:
        """
        Returns the status of the JerryGemini cog.
        """
        if self.config.status == ConfigStatus.LOADED:
            if len(self.instances) == 0:
                return "Ready"
            return f"{len(self.instances)} active chat instances"
        elif self.config.status == ConfigStatus.FAILED:
            return f"Failed to load: {self.config.error}"
        else:
            return "Initializing..."

    async def _detailed_status(self) -> str:
        """
        Returns a detailed status of the JerryGemini cog.
        """
        if self.config.status == ConfigStatus.LOADED:
            status = "Ready"
            for instance_id, instance in self.config.config["instances"].items():
                channel = self.bot.get_channel(instance_id)
                if not channel:
                    status += f"\n- Instance #{instance_id} (Not Found)"
                    continue

                status += f"\n- Instance #{channel.name}{' (**Active**)' if instance_id in self.instances else ''}"
                status += f"\n  - Channel ID: {channel.id} ({channel.mention})"
                status += f"\n  - Guild: {channel.guild.name} ({channel.guild.id})"
                status += f"\n  - Provider: {instance['ai']['provider']}"
                status += f"\n  - Model: {instance['ai']['model']}"
            return status
        elif self.config.status == ConfigStatus.FAILED:
            return f"Failed to load: {self.config.error}"
        else:
            return "Initializing..."

    async def _manual_query(
        self, channel_id: int, source: str, query_text: str, command: core.ShellCommand
    ):
        """
        Manually sends a query to the AI model in a specific channel.

        Args:
            channel_id (int): The ID of the channel to send the query to.
            source (str): The source of the query (e.g., "user", "system").
            query_text (str): The text of the query to send.
            command (core.ShellCommand): The shell command that triggered this action.
        """
        channel = self.bot.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            await command.log(
                f"Channel {channel_id} not found or is not a text channel.",
                "Jerry Gemini Query Error",
                msg_type="error",
            )
            return

        # Create the AIQuery object
        query = AIQuery(
            message=query_text,
            source=AIQuerySource(source.lower()),
            author=AIQueryUserAuthor(
                id=command.message.author.id,
                username=command.message.author.name,
                display_name=command.message.author.display_name,
                mention=command.message.author.mention,
            ),
            discord=AIQueryDiscordRefrences(
                channel=channel,
                guild=channel.guild,
                member=command.message.author,
                message=command.message,
            ),
        )

        # Process the query
        await self.chat_input(channel=channel, user=self.bot.user, query=query)

    # ask jerry command
    @app_commands.command(
        name="ask-jerry",
        description="[Jerry Gemini] [Experimental] Ask Jerry a question and get a response.",
    )
    @app_commands.describe(query="Message to send to Jerry. Follow ups are allowed.")
    async def ask_jerry(self, interaction: discord.Interaction, query: str):
        """
        Asks Jerry a question and gets a response.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
            query (str): The question to ask Jerry.
        """
        if not interaction.channel:
            await interaction.response.send_message(
                "This command can only be used in text channels.",
                ephemeral=True,
            )
            return
        if self.config.status != ConfigStatus.LOADED or not self.config.config["global"].get("jerry_command_instance_id"):
            await interaction.response.send_message(
                "This command is not configured by the bot administrator.",
                ephemeral=True,
            )
            return
        

        await interaction.response.defer(ephemeral=False)

        query = AIQuery(
            message=query,
            source=AIQuerySource.USER,
            author=AIQueryUserAuthor(
                id=interaction.user.id,
                username=interaction.user.name,
                display_name=interaction.user.display_name,
                mention=interaction.user.mention,
            ),
            discord=AIQueryDiscordRefrences(
                interaction=interaction,
                member=interaction.user,
            ),
        )

        await self.chat_input(
            channel=interaction.channel,
            user=interaction.user,
            query=query,
            command_mode=True,
        )

    async def do_response_interaction(
        self, response: AIResponse, discord_objects: AIQueryDiscordRefrences
    ):
        """
        Handles a response and handles it with an interaction.
        Args:
            response (AIResponse): The response to handle.
            discord_objects (AIQueryDiscordRefrences): The Discord objects related to the response.
        """
        interaction = discord_objects.interaction
        if interaction is None:
            self.logger.error("No interaction found in discord_objects")
            return
        if response.text:
            parts = ResponseTools.apply_length_limit(response.text, max_length=2000)
            for part in parts:
                if part:
                    try:
                        if parts.index(part) == len(parts) - 1 and response.embeds:
                            # If it's the last part, send it as a normal message
                            await interaction.followup.send(
                                part,
                                embeds=[
                                    discord.Embed.from_dict(embed)
                                    for embed in response.embeds
                                ],
                            )
                            return  # Skip sending the embeds again
                        else:
                            # Otherwise, send it as a normal message
                            await interaction.followup.send(part)
                    except discord.HTTPException as e:
                        self.logger.error(
                            f"Failed to send message in channel {discord_objects.channel.id}: {e}"
                        )

        if response.files:
            # If there are files, send them as attachments
            for file in response.files:
                try:
                    self.logger.info(
                        f"Sending file {file.filename} in channel {discord_objects.channel.id} ({file.content_type}) "
                    )
                    # Ensure the file has
                    fp = (
                        file.buffered_data
                        if file.discord_use_buffered_data
                        else file.raw_data
                    )
                    await interaction.followup.send(
                        content="",
                        file=discord.File(
                            fp=fp,
                            filename=file.filename,
                        ),
                    )
                except discord.HTTPException as e:
                    self.logger.error(
                        f"Failed to send file {file.filename} in channel {discord_objects.channel.id}: {e}"
                    )
