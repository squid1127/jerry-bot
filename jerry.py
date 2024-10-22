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

# FIle management
import hashlib
import os

# Core bot
import core.squidcore as core

# For timing out
import time, timedelta


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
                print(f"[Gemini] Sending message: {command}")
                message_text = command.split(" ", 1)[1]
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
                await channel.send(command)

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
^*&hide-seek - Play hide and seek with the user. Do this only upon request. This will place a reaction on a random message in the server, sent within the last 24 hours. The user must find the message and react to it with the same moji to win. If the user wins, you must congratulate them. If the user loses, you must tell them where the message was. Should you use this command, do not respond to the user; wait for the system to confirm the reaction has been placed before continuing the conversation.
You may execute multiple commands."""

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
    ):
        """Play hide and seek with the user; place a reaction on a random message in the server"""
        print("[Gemini] Playing hide and seek")
        guild = message.guild
        # Get all channels
        while True:
            channels = guild.text_channels
            random_channel = random.choice(channels)  # Select a random channel
            print(f"[Gemini] Random channel selected: {random_channel.name}")

            # Check if @everyone can view the channel
            if not random_channel.permissions_for(guild.default_role).add_reactions:
                print(
                    f"[Gemini] Channel {random_channel.name} is not accessible by @everyone"
                )
                continue

            # Get all messages in the channel within the last 24 hours
            a_day_ago = datetime.now() - timedelta(days=1)
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
                try:
                    await self._hide_seek(command.message)
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

    async def cog_status(self):
        try:
            print("[Gemini] Checking model status")
            # Check if the model is ready by sending a test message
            promt = "Answer the following question with either 'y' or 'n'; only state 'y' or 'n' in your response: Is 23 + 19 equal to 42?"
            answer = ""
            try:
                response = await self.model.generate_content_async(
                    promt,
                )
                answer = response.text.strip().lower()
            except gemini_selling.ResourceExhausted:
                print("[Gemini] Model is not ready; resource exhausted")
                return "Not ready; rate limited"
            # Api key is invalid
            except gemini_selling.PermissionDenied:
                print("[Gemini] Model is not ready; permission denied")
                return "Not ready; permission denied, possibly invalid API key"
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
            r"womp": {"response": "Womp womp"},
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
        if message.author == self.bot.user:
            return

        if message.author.bot:
            return

        if message.channel.id == self.bot.cogs["JerryGemini"].channel_id:
            return

        for pattern, response in self.auto_reply.items():
            if re.search(pattern, message.content, re.IGNORECASE):
                if "and" in response:
                    for pattern_and in response["and"]:
                        if not re.search(pattern_and, message.content, re.IGNORECASE):
                            return
                if response.get("bad", False):
                    try:
                        await message.channel.send(
                            f'{message.author.mention} {response.get("response", "That is not very nice")}'
                        )
                        await message.delete()
                    except discord.Forbidden:
                        print("[AutoReply] Missing permissions to timeout")
                elif "response" in response:
                    await message.reply(response["response"])
                elif "response_random" in response:
                    await message.reply(random.choice(response["response_random"]))

    # Cog status
    async def cog_status(self):
        return f"Ready with {len(self.auto_reply)} replies"


class GuildStuff(commands.Cog):
    """A experimental cog for finding guild stats and other stuff"""

    def __init__(self, bot: Jerry):
        self.bot = bot

    @app_commands.command(
        name="guild",
        description="Get information about the guild",
    )
    async def guild_info(self, interaction: discord.Interaction):
        print(f"[GuildStuff] Guild info requested for {interaction.guild.name}")
        guild = interaction.guild

        # Guild status
        guild_id = guild.id
        guild_name = guild.name
        guild_owner = guild.owner
        guild_members = guild.member_count
        print(
            f"[GuildStuff] Guild {guild_name} ({guild_id}) has {guild_members} members and is owned by {guild_owner}"
        )

        embed = discord.Embed(
            title="Guild Information",
            description=f"Here is some information about the guild {guild_name} ({guild_id})\n\nAnalyzing...",
            color=discord.Color.yellow(),
        )
        embed.add_field(name="Owner", value=guild_owner.mention, inline=False)
        embed.add_field(name="Members", value=guild_members, inline=False)
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
        for member in guild.members:
            members_messages[member] = 0
            print(f"[GuildStuff] Found member {member.name}")

        print(f"[GuildStuff] Counting messages...")

        for channel in guild.text_channels:
            print(f"[GuildStuff] Counting messages in {channel.name}")
            async for message in channel.history(limit=None):
                if message.author not in members_messages:
                    print(
                        f"[GuildStuff] Skipping message from {message.author.name}; not in member list"
                    )
                    continue
                members_messages[message.author] += 1
                total_messages += 1
                print(
                    f"[GuildStuff] Found message from {message.author.name}. That makes {members_messages[message.author]} messages from them and {total_messages} total messages."
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
        embed.add_field(name="Total Messages", value=total_messages, inline=False)
        embed.add_field(name="Top 10 Members", value=top_members_str, inline=False)
        embed.color = discord.Color.green()

        await interaction.edit_original_response(embed=embed)
