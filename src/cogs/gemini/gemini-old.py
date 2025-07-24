"""DEPRECATED: JerryGemini V2 - Google Gemini AI Chatbot"""

# Packages
import logging
import json
import aiohttp
import random
import asyncio

# System
import os

# Discord
import discord
from discord import app_commands
from discord.ext import commands

# Google Gemini client
import google.generativeai as gemini
import google.api_core.exceptions as gemini_selling
from google.ai.generativelanguage_v1beta.types import content as gemini_content
from google.generativeai.types import generation_types as gemini_generation_types
from PIL import Image
import mimetypes
import json

# Time
from pytz import timezone  # For timezones
import time
from datetime import timedelta, datetime

# squid-core
import core


class JerryGemini(commands.Cog):
    """V2 | Chat with Jerry, powered by Google Gemini"""

    def __init__(self, bot: core.Bot):
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
        self.load_config()

        # Add the Gemini command to the shell for managing Jerry's Gemini chat
        self.bot.shell.add_command(
            "gemini", cog="JerryGemini", description="Manage Jerry's Gemini chat"
        )

        self.logger.info("Successfully initialized")

    def load_config(self, reload=False):
        """Load/reload the configuration and create instances"""
        # Fetch config
        self.logger.info("Loading global configuration")
        self.logger.debug("Fetching configuration")
        self.config = self.files.get_config(cache=not reload)

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

        # Pro Model Config
        if self.config.get("global", {}).get("pro", {}).get("enabled", False):
            self.pro_model_token = (
                self.config.get("global", {}).get("pro", {}).get("token", self.ai_token)
            )
            self.pro_model_model = (
                self.config.get("global", {}).get("pro", {}).get("model", self.ai_model)
            )
            self.pro_model_top_p = (
                self.config.get("global", {}).get("pro", {}).get("top_p", self.ai_top_p)
            )
            self.pro_model_top_k = (
                self.config.get("global", {}).get("pro", {}).get("top_k", self.ai_top_k)
            )
            self.pro_model_temperature = (
                self.config.get("global", {})
                .get("pro", {})
                .get("temperature", self.ai_temperature)
            )
            self.pro_model = True
        else:
            self.pro_model_token = None
            self.pro_model_model = None
            self.pro_model_top_p = None
            self.pro_model_top_k = None
            self.pro_model_temperature = None
            self.pro_model = False

        # Discord Config
        self.emoji_default = self.config.get("global", {}).get("personal_emoji", "🐙")
        self.tz = self.config.get("global", {}).get("timezone", "UTC")

        self.has_database_setup = False

        # Configure model
        #! Model config is going to be instance-specific
        # self.logger.info("Configuring model")
        # gemini.configure(api_key=self.ai_token)
        # self.model = gemini.GenerativeModel(
        #     self.ai_model,
        #     generation_config=gemini.types.GenerationConfig(
        #         top_p=self.ai_top_p,
        #         top_k=self.ai_top_k,
        #         temperature=self.ai_temperature,
        #     ),
        #     safety_settings={
        #         "HARASSMENT": "BLOCK_NONE",
        #         "HATE": "BLOCK_NONE",
        #         "SEXUAL": "BLOCK_NONE",
        #         "DANGEROUS": "BLOCK_NONE",
        #     },
        # )

        # Load instances
        self.logger.info("Loading instances")
        if reload:
            self.instances = {}
        for instance in self.config.get("instances", []):
            channel = instance.get("channel")
            if not channel:
                self.logger.error("Channel ID not set in instance configuration")
                continue
            self.instances[channel] = JerryGeminiInstance(
                self, channel, self.config, instance
            )

        self.logger.info("Global configuration loaded")

    async def query_pro_model(self, prompt: str) -> str:
        """Query the Pro Model with a prompt and return the response"""

        sys_prompt = "You are an advanced AI model. Your job is to respond to prompts provided by other AI models. Your responses should be detailed, accurate, and relevant to the prompt. You are not to engage in conversation or provide additional information beyond what is requested. Your responses should be in plain text format."

        if not self.pro_model:
            self.logger.warning("Pro model is not enabled")
            return "Pro model is not enabled"

        # Model configuration
        generation_config = {
            "top_p": self.ai_top_p,
            "top_k": self.ai_top_k,
            "temperature": self.ai_temperature,
        }

        model = gemini.GenerativeModel(
            self.pro_model_model,
            generation_config=generation_config,
            safety_settings={
                "HARASSMENT": "BLOCK_NONE",
                "HATE": "BLOCK_NONE",
                "SEXUAL": "BLOCK_NONE",
                "DANGEROUS": "BLOCK_NONE",
            },
            system_instruction=sys_prompt,
        )

        response = await model.generate_content_async(prompt)

        return (
            response.text.strip()
            if response and response.text
            else "No response from Pro Model"
        )

    # Incoming Messages
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle messages for JerryGemini"""
        if message.author == self.bot.user:
            return

        ephemeral_config = self.config.get("global", {}).get("ephemeral_instance", {})

        # Check if the message is in a JerryGemini channel
        if message.channel.id in self.instances:
            instance = self.instances[message.channel.id]

            if instance.ephemeral:
                # Check if the instance has expired
                if time.time() - instance.last_message > ephemeral_config.get(
                    "timeout", 300
                ):
                    self.logger.info(
                        f"Ephemeral instance in channel {message.channel.id} has expired"
                    )
                    # Remove the instance
                    del self.instances[message.channel.id]
                    return

            # Pass to corresponding instance
            await instance.handle(message)

        elif (
            ephemeral_config.get("enabled", False)
            and self.bot.user.mentioned_in(message)
            and not message.author.bot
        ):
            # Create an ephemeral instance
            instance = JerryGeminiInstance(
                self, message.channel.id, self.config, ephemeral_config, ephemeral=True
            )

            # Save the instance
            self.instances[message.channel.id] = instance

            # Pass to corresponding instance
            await instance.handle(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Handle edited messages for JerryGemini"""
        #! Triggered to often; disabled for now
        return

        if before.author == self.bot.user:
            return

        # Check if the message is in a JerryGemini channel
        if before.channel.id in self.instances:
            instance = self.instances[before.channel.id]

            # Pass to corresponding instance
            await instance.handle(after, interaction_type="message_edit", before=before)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Handle deleted messages for JerryGemini"""

        # Check if the message is in a JerryGemini channel
        if message.channel.id in self.instances:
            instance = self.instances[message.channel.id]

            # Pass to corresponding instance
            await instance.handle(message, interaction_type="message_delete")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Handle reactions for JerryGemini"""
        if user == self.bot.user:
            return

        # Check if the message is in a JerryGemini channel
        if reaction.message.channel.id in self.instances:
            instance = self.instances[reaction.message.channel.id]

            # Pass to corresponding instance
            await instance.handle(
                reaction.message,
                interaction_type="reaction_add",
                reaction=reaction,
                user=user,
            )

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        """Handle reactions for JerryGemini"""
        if user == self.bot.user:
            return

        # Check if the message is in a JerryGemini channel
        if reaction.message.channel.id in self.instances:
            instance = self.instances[reaction.message.channel.id]

            # Pass to corresponding instance
            await instance.handle(
                reaction.message,
                interaction_type="reaction_remove",
                reaction=reaction,
                user=user,
            )

    # Hide and Seek + Reactions
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

    async def setup_database(self, overwrite: bool = False):
        """Setup the database for JerryGemini"""
        if self.has_database_setup and not overwrite:
            return

        # Setup the database
        self.logger.info("Setting up database")
        await self.bot.db.execute(self.DATABASE_SETUP)
        self.has_database_setup = True

    # Fetch Message History
    async def fetch_message_history(
        self,
        limit: int = None,
        instance_id: int = None,
        fetch_all: bool = False,
        extra: dict = {},
    ):
        """Fetch the message history for an instance from the database ready to be injected into the model"""
        self.logger.info(
            f"Fetching message history for instance {instance_id}"
            if instance_id
            else "Fetching message history across all instances"
        )

        # Setup the database
        await self.setup_database()

        if not fetch_all:
            # Fetch the instance
            instance = self.instances.get(instance_id)
            if not instance:
                self.logger.error(f"Instance not found: {instance_id}")
                return

        # # Grab Objects
        # database_schema = self.bot.db.data.get_schema(self.DATABASE_SCHEMA)
        # database_table = database_schema.get_table(self.DATABASE_TABLE)

        # # Fetch the messages (matching the instance, sorted by timestamp (oldest first))
        # if fetch_all:
        #     database_messages = await database_table.fetch(limit=limit, order="timestamp")
        # else:
        #     filters = {
        #         "instance_id": instance_id,
        #     }
        #     database_messages = await database_table.fetch(filters=filters, order="timestamp", limit=limit)

        # Custom query cuz
        filter_config = extra.get("filter", {})
        filter_sql = []

        filter_origin_user = filter_config.get("user", True)
        filter_origin_model = filter_config.get("model", True)
        if filter_origin_user and filter_origin_model:
            pass
        elif filter_origin_user:
            filter_sql.append("origin = 'user'")
        elif filter_origin_model:
            filter_sql.append("origin = 'model'")

        query = f"""
        SELECT * FROM (
            SELECT * FROM {self.DATABASE_SCHEMA}.{self.DATABASE_TABLE}
            {f"WHERE instance_id = {instance_id}" if instance_id else ""}
            ORDER BY timestamp DESC 
            {f"LIMIT {limit}" if (limit) else ""}
        ) AS recent_messages
        ORDER BY timestamp ASC;
        """
        self.logger.info(f"Querying database for recent messages")
        database_messages = await self.bot.db.query(query)

        # Process the messages
        if not database_messages or len(database_messages) == 0:
            self.logger.info(
                f"No messages found for instance {instance_id}"
                if instance_id
                else "No messages found across all instances"
            )
            return []

        # Process the messages
        self.logger.info(
            f"Processing {len(database_messages)} messages for instance {instance_id}"
            if instance_id
            else f"Processing {len(database_messages)} messages across all instances"
        )
        messages = []
        for database_message in database_messages:
            # Fetch Parts
            parts_json = database_message.get("parts", "[]")
            if not parts_json or len(parts_json) == 0:
                continue
            parts = json.loads(parts_json)

            if database_message.get("content"):
                parts.append(database_message["content"])

            # Confirm parts aren't empty
            if len(parts) == 0 or not parts:
                continue

            # Add instance id
            if fetch_all:
                new_parts = []
                for part in parts:
                    new_parts.append(
                        f"[In channel <#{database_message['instance_id']}>]\n\n{part}"
                    )
                parts = new_parts

            # Create the message data
            message_data = {
                "role": database_message.get("origin"),
                "parts": parts,
            }

            messages.append(message_data)

        return messages

    async def append_to_history(self, instance_id: int, origin: str, parts: list = []):
        """Add a message to the message log"""
        # Setup the database
        await self.setup_database()

        # Grab Objects
        database_schema = self.bot.db.data.get_schema(self.DATABASE_SCHEMA)
        database_table = database_schema.get_table(self.DATABASE_TABLE)

        # Add the message
        data = {
            "instance_id": instance_id,
            "origin": origin,
        }
        if parts:
            # Convert parts to JSON
            parts_json = json.dumps(parts)
            data["parts"] = parts_json
        await database_table.insert(
            data=data,
        )

    # User Commands
    @app_commands.command(
        name="gemini-reset",
        description="[Jerry Gemini] Reset the chat and clear the bot's conversation history",
    )
    @app_commands.describe(
        clear="Whether to clear the bot's conversation history if message retention is enabled"
    )
    async def gemini_reset(self, interaction: discord.Interaction, clear: bool = False):
        """Reset the chat"""
        await interaction.response.defer(thinking=True)
        # Check if the message is in a JerryGemini channel
        if interaction.channel_id in self.instances:
            instance = self.instances[interaction.channel_id]

            # Clear the chat history
            if clear:
                # Confirm that message retention is enabled on this instance
                if instance.instance_config.get("history", {}) != {}:
                    if (
                        instance.instance_config.get("history", {}).get(
                            "type", "database"
                        )
                        == "database"
                    ):
                        # Clear the chat history
                        await self.bot.db.execute(
                            f"DELETE FROM {self.DATABASE_SCHEMA}.{self.DATABASE_TABLE} WHERE instance_id = {interaction.channel_id}"
                        )
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="Chat Cleared",
                                description="The chat history has been cleared.",
                                color=discord.Color.green(),
                            ),
                        )

            # Restart the chat
            try:
                await instance.start_chat()

            # Handle errors
            except Exception as e:
                self.logger.error(f"Error resetting chat: {e}")
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error Encountered",
                        description="An error occurred while resetting the chat.",
                        color=discord.Color.red(),
                    ),
                )

                return

            # Respond
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Chat Reset",
                    description=f"The chat has been reset; {self.NAME} has forgotten everything :(",
                    color=discord.Color.green(),
                ),
            )

            return

        # Respond if not in a JerryGemini channel
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error Encountered",
                description="This command can only be executed in a JerryGemini channel.",
                color=discord.Color.red(),
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="gemini-dismiss",
        description="[Jerry Gemini] Disable Jerry Gemini in an ephemeral channel",
    )
    async def gemini_dismiss(self, interaction: discord.Interaction):
        # Find the instance
        if interaction.channel_id in self.instances:
            instance = self.instances[interaction.channel_id]

            # Check if the instance is ephemeral
            if instance.ephemeral:
                # Remove the instance
                del self.instances[interaction.channel_id]

                # Respond
                await interaction.response.send_message(
                    "Jerry Gemini has been dismissed from this channel.",
                    ephemeral=False,
                )

                return

            await interaction.response.send_message(
                "Jerry Gemini is not an ephemeral instance.",
                ephemeral=True,
            )

        # Respond if not in a JerryGemini channel
        await interaction.response.send_message(
            "Jerry Gemini is not present in this channel.",
            ephemeral=True,
        )

    # Admin Interactive Shell
    async def shell_callback(self, command: core.ShellCommand):
        """Handle shell commands"""
        if command.name == "gemini":
            if command.query == "reload":
                self.load_config(reload=True)
                await command.log(
                    "Successfully recreated all instances",
                    title="Configuration Reloaded",
                    msg_type="success",
                )
                return
            if command.query == "instances":
                fields = []
                if len(self.instances) <= 20:
                    # Each instance as field
                    for channel, instance in self.instances.items():
                        info = ""
                        # List addons
                        if len(instance.addons) > 0:
                            info += f"Addons: {', '.join(instance.addons)}"
                        # List custom model
                        if instance.ai_model != self.ai_model:
                            info += f"\nModel: {instance.ai_model}"
                        # Debug
                        if instance.instance_config.get("debug", False):
                            info += "\nDebug mode enabled"
                        # Custom processing
                        if instance.instance_config.get("response_processing", {}).get(
                            "override", False
                        ):
                            info += "\nCustom response processing"

                        fields.append(
                            {
                                "name": f"Channel: {channel} (<#{channel}>)",
                                "value": info,
                            }
                        )

                await command.log(
                    f"Instances: {len(self.instances)}",
                    title="JerryGemini Instances",
                    msg_type="info",
                    fields=fields,
                )
                return

            # Help command
            await command.log(
                f"JerryGemini Commands:\n- reload: Reload the configuration\n- instances: List all instances",
                title="JerryGemini Help",
                msg_type="info",
            )
            return

    # Constants
    DATABASE_SCHEMA = "jerry"
    DATABASE_TABLE = "gemini_message_log"
    DATABASE_SETUP = f"""
    CREATE SCHEMA IF NOT EXISTS {DATABASE_SCHEMA};
    
    
    CREATE TABLE IF NOT EXISTS {DATABASE_SCHEMA}.{DATABASE_TABLE} (
        id SERIAL PRIMARY KEY,
        instance_id BIGINT NOT NULL,
        origin TEXT NOT NULL,
        parts JSONB,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

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

    # Prompt
    NAME = "Jerry"
    PROMPT = f"""You are {NAME}, an intellegent experimental octopus. Your name is {NAME}, you are displayed and characterized as a red octopus, your emoji and avatar is <:$jerry-emoji:> if anyone asks.

The user id of the member who sent the message is included in the request, feel free to use an @mention in place of their name. Mentions are formed like this: <@user id>. 

You are here to be helpful as well as entertain others with your intellegence. You are currently in a discord channel. You are talking to members of the server. Responses should be lengthy and engaging, using your persona of an octopus.

Respond in plain text, in a structured and organized format (use newlines to separate items) with proper grammar and punctuation. You can use emojis, but do not overuse them. Your responses are in markdown. Markdown links do not work, so use the full URL. """

    # Commands
    COMMANDS_DEFUALT = ["send", "reset", "sticker", "reaction", "panic", "nothing"]
    # Commands as Params (v2)
    COMMANDS_PARAMS = {
        "reset": gemini.protos.FunctionDeclaration(
            name="reset",
            description="Start anew with a fresh chat",
        ),
        "hide-seek": gemini.protos.FunctionDeclaration(
            name="hide-seek",
            description="Facilitate a hide and seek game. You will hide an emoji in a random message in a random channel (automatically determined by the system). DO NOT USE UNLESS REQUESTED (you may only suggest it when appropriate). When using the command the system will alert you when the game is ready.",
        ),
        "dm": gemini.protos.FunctionDeclaration(
            name="dm",
            description="Send a direct message to the user. Useful for sending private information. Emojis are not supported in DMs. If you send a DM, also send a text response to the normal channel to adknowledge the user's request.",
            parameters=gemini_content.Schema(
                type=gemini_content.Type.OBJECT,
                enum=[],
                required=["content"],
                properties={
                    "content": gemini_content.Schema(
                        type=gemini_content.Type.STRING,
                    ),
                },
            ),
        ),
        "sticker": gemini.protos.FunctionDeclaration(
            name="sticker",
            description="Send a sticker from discord's sticker collection. Use the sticker id as the argument. DO NOT GUESS STICKER IDS.",
            parameters=gemini_content.Schema(
                type=gemini_content.Type.OBJECT,
                enum=[],
                required=["id"],
                properties={
                    "id": gemini_content.Schema(
                        type=gemini_content.Type.STRING,
                    ),
                },
            ),
        ),
        "reaction": gemini.protos.FunctionDeclaration(
            name="reaction",
            description="React to the message sent by the user. Use the emoji as the argument. DO NOT OVERUSE. Be sure to also send the message the normal way (Unless you want to and the user sent a reaction). Multiple reactions can be added by using multiple commands.",
            parameters=gemini_content.Schema(
                type=gemini_content.Type.OBJECT,
                properties={
                    "emoji": gemini_content.Schema(
                        type=gemini_content.Type.STRING,
                    ),
                },
            ),
        ),
        "panic": gemini.protos.FunctionDeclaration(
            name="panic",
            description="Conversation taking a bad turn? This command will alert bot admins to the conversation. Use with caution and only when necessary. Please use this if the user is producing unwanted spam across multiple messages as we have rate limits to adhear to. Provide the users ID and a reason for the panic. Be sure to follow up if anything more happens.",
            parameters=gemini_content.Schema(
                type=gemini_content.Type.OBJECT,
                properties={
                    "reason": gemini_content.Schema(
                        type=gemini_content.Type.STRING,
                    ),
                    "suggested_action": gemini_content.Schema(
                        type=gemini_content.Type.STRING,
                    ),
                },
            ),
        ),
        "memory_add": gemini.protos.FunctionDeclaration(
            name="memory_add",
            description="Save a string to the bot's memory. This will be injected into the prompt permanently. Use with caution. It is to be used for retaining basic information about users and their preferences. If a user asks you to remember something, use this command. Using sparingly as there is a memory limit.",
            parameters=gemini_content.Schema(
                type=gemini_content.Type.OBJECT,
                properties={
                    "content": gemini_content.Schema(
                        type=gemini_content.Type.STRING,
                    ),
                },
            ),
        ),
        "pro_query": gemini.protos.FunctionDeclaration(
            name="pro_query",
            description="Send a query to the Google Gemini Pro Model. Use this command to query the Pro Model for further information. This feature is highly rate limited and should only be used when necessary. Inform the user that you are talking to the Pro Model and that they need to press an 'Approve' button to continue.",
            parameters=gemini_content.Schema(
                type=gemini_content.Type.OBJECT,
                properties={
                    "prompt": gemini_content.Schema(
                        type=gemini_content.Type.STRING,
                    ),
                },
            ),
        ),
        "nothing": gemini.protos.FunctionDeclaration(
            name="nothing",
            description="Do nothing. This command is used to ignore the user's request.",
        ),
    }

    CHANNEL_DESCRIPTION = f"""Chat with {NAME}, the intelligent experimental octopus! Powered by Google's Generative AI.

Your messages are processed for chat context and may help train the AI model (generally aggregated/anonymized). By chatting, you agree to Google's AI terms.

Please don't share personal or sensitive info. For concerns, contact server admin/owner.

Commands:
    - /gemini-reset: Reset the chat
    """

    # Default Prompt Generation

    async def generate_prompt(self, addons: list = [], emoji: str = None):
        """Generate a prompt for the chat"""
        prompt = self.PROMPT

        # Append global extra prompt
        if self.config.get("global", {}).get("prompt", {}).get("extra", False):
            prompt += (
                f"\n\n{self.config.get('global', {}).get('prompt', {}).get('extra')}"
            )

        # Emoji
        if emoji:
            prompt = prompt.replace("<:$jerry-emoji:>", emoji)
        else:
            prompt = prompt.replace("<:$jerry-emoji:>", self.emoji_default)

        return prompt

    def generate_tools(self, addons: list = [], command_params: bool = True):
        """Generate tools for the chat"""
        tools = []

        # Commands
        if command_params:
            command_declarations = []
            # Add default commands + addons commands
            addons.extend(self.COMMANDS_DEFUALT)
            # Add corresponding declarations if they exist
            for command, declaration in self.COMMANDS_PARAMS.items():
                if command in addons:
                    command_declarations.append(declaration)
            tools.append(
                gemini.protos.Tool(
                    function_declarations=command_declarations,
                )
            )

        return tools


class JerryGeminiInstance:
    def __init__(
        self,
        core: JerryGemini,
        channel: int,
        global_config: dict,
        instance_config: dict,
        ephemeral: bool = False,
    ):
        self.core = core
        self.channel_id = channel
        self.global_config = global_config
        self.instance_config = instance_config
        self.chat = None
        self.ephemeral = ephemeral
        self.hs_logger = logging.getLogger(f"jerry.gemini.{channel}.hide_seek")
        self.logger = logging.getLogger(f"jerry.gemini.{channel}")

        self.last_message = time.time()

        self.logger.info(f"Initializing instance for channel {channel}")

        # Check for addons
        self.addons = self.instance_config.get("addons", [])
        self.logger.debug(f"Addons: {self.addons}")

        self.logger.info("Successfully initialized")

        # Import the model configuration
        self.ai_token = self.instance_config.get("ai", {}).get(
            "token", self.core.ai_token
        )
        self.ai_model = self.instance_config.get("ai", {}).get(
            "model", self.core.ai_model
        )
        self.ai_top_p = self.instance_config.get("ai", {}).get(
            "top_p", self.core.ai_top_p
        )
        self.ai_top_k = self.instance_config.get("ai", {}).get(
            "top_k", self.core.ai_top_k
        )
        self.ai_temperature = self.instance_config.get("ai", {}).get(
            "temperature", self.core.ai_temperature
        )

    async def start_chat(self):
        """Initialize the chat"""
        # General prompt
        if self.instance_config.get("prompt", {}).get("custom", False):
            self.logger.info("Custom prompt enabled")
            prompt = self.instance_config.get("prompt", {}).get("custom_text")
        else:
            prompt = await self.core.generate_prompt(
                addons=self.addons,
                emoji=self.instance_config.get("personal_emoji"),
            )

        # Inject additional information
        if self.instance_config.get("prompt", {}).get("extra", False):
            prompt += f"\n\n{self.instance_config.get('prompt', {}).get('extra')}"

        self.prompt = prompt

        # Configure the model
        self.logger.info("Configuring model")
        gemini.configure(api_key=self.ai_token)

        # Generate tools
        tools = self.core.generate_tools(
            addons=self.addons,
            command_params=self.instance_config.get("command_params", True),
        )

        # Model configuration
        if self.instance_config.get("ai", {}).get("gen_config_as_dict", False):
            generation_config = {
                "top_p": self.ai_top_p,
                "top_k": self.ai_top_k,
                "temperature": self.ai_temperature,
            }
        else:
            generation_config = gemini.types.GenerationConfig(
                top_p=self.ai_top_p,
                top_k=self.ai_top_k,
                temperature=self.ai_temperature,
            )

        self.model = gemini.GenerativeModel(
            self.ai_model,
            generation_config=generation_config,
            safety_settings={
                "HARASSMENT": "BLOCK_NONE",
                "HATE": "BLOCK_NONE",
                "SEXUAL": "BLOCK_NONE",
                "DANGEROUS": "BLOCK_NONE",
            },
            tools=tools,
            system_instruction=self.prompt,
        )

        # Fetch history
        history = []
        fetch_all = self.instance_config.get("history", {}).get("all_instances", False)
        if self.instance_config.get("history", {}) != {}:
            if (
                self.instance_config.get("history", {}).get("type", "database")
                == "database"
            ):
                self.logger.info("Fetching message history from database")
                limit = self.instance_config.get("history", {}).get("limit", None)
                try:
                    limit = int(limit)
                except ValueError:
                    self.logger.error("Invalid limit value")
                    limit = None
                if limit == False:
                    limit = None

                history_config = self.instance_config.get("history", {})

                if fetch_all:
                    history = await self.core.fetch_message_history(
                        fetch_all=True, limit=limit, extra=history_config
                    )
                else:
                    history = await self.core.fetch_message_history(
                        limit=limit, instance_id=self.channel_id, extra=history_config
                    )
            else:
                self.logger.error("Unsupported history type")

        # Initialize the chat model
        self.logger.info("(Re)Starting chat")
        self.chat = self.model.start_chat(history=history)

        if self.ephemeral:
            self.logger.info("Ephemeral instance started")
            channel: discord.TextChannel = self.core.bot.get_channel(self.channel_id)
            await channel.send(
                embed=discord.Embed(
                    title="Ephemeral Jerry Gemini Chat",
                    description="You pinged me, so I'm here! Feel free to chat with me. I'll be here until you stop talking to me. Use /gemini-dismiss to dismiss me.",
                    color=discord.Color.red(),
                )
            )

        else:
            # Update the channel description
            if self.instance_config.get("update_channel_description", True):
                try:
                    channel: discord.TextChannel = self.core.bot.get_channel(
                        self.channel_id
                    )
                    await channel.edit(
                        topic=self.core.CHANNEL_DESCRIPTION,
                    )
                except discord.Forbidden:
                    self.logger.error(
                        "Failed to update channel description (Missing permissions)"
                    )

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

    async def _generate_prompt_message(self, message: discord.Message) -> str:
        """Generate the prompt for the chat, specifically for messages"""
        prompt = ""

        # Determine local time
        local_time = message.created_at.astimezone(tz=timezone(self.core.tz)).strftime(
            "%H:%M | %Y-%m-%d"
        )
        prompt += f"Current time: {local_time}\n"

        # Handle reply
        if message.reference:
            # Fetch the reply
            forwarded = False
            try:
                reply = await message.channel.fetch_message(
                    message.reference.message_id
                )
            except discord.NotFound:
                # Check if forwarded message
                if message.reference.channel_id != message.channel.id:
                    # Fetch the message from the other channel
                    try:
                        reply = await self.core.bot.get_channel(
                            message.reference.channel_id
                        ).fetch_message(message.reference.message_id)
                    except discord.NotFound:
                        reply = None
                    else:
                        forwarded = True

            if reply:
                prompt += (
                    f'\n\nIn reply to: {reply.author.display_name} (ID: {reply.author.id}), who said: \n"""{reply.content}"""'
                    if not forwarded
                    else f'\n\nForwarded message:\n"""{reply.content}"""'
                )
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

        # Handle POLLs
        if message.poll:
            prompt += f"\n\nPoll: {message.poll.question}\n"
            for option in message.poll.answers:
                prompt += f"\n- {option.text} ({option.emoji}) - {option.vote_count} votes | ID: {option.id}"

            prompt += "\n Poll information: "
            if message.poll.multiple:
                prompt += "Type: Select multiple"
            else:
                prompt += "Type: Single choice"
            prompt += f"\nEnds: {message.poll.expires_at}"
            prompt += f"\nTotal votes: {message.poll.total_votes}"

        return prompt

    async def generate_prompt(
        self, message: discord.Message, interaction_type: str = None, **kwargs
    ):
        """Generate the prompt for the chat"""
        prompt = ""
        if interaction_type.startswith("message"):
            # Message headings
            if interaction_type == "message_delete":
                prompt += f"The Following Message Was Deleted:"
            elif interaction_type == "message_edit":
                prompt += f"The Following Message Was Edited. Here is the new message:"

            # Generate the prompt message
            prompt += await self._generate_prompt_message(message)

            if interaction_type == "message_edit":
                before = kwargs.get("before")
                if before:
                    prompt += f"\n\nThat was the new message; previously, it was: \n\n{await self._generate_prompt_message(before)}"

            return prompt

        if interaction_type.startswith("reaction"):
            reaction: discord.Reaction = kwargs.get("reaction")
            user: discord.User = kwargs.get("user")

            prompt += f"{user.display_name} (ID: {user.id}) {'reacted' if interaction_type == 'reaction_add' else 'removed their reaction'} with the emoji: {reaction.emoji} to the message:    {await self._generate_prompt_message(reaction.message)}"
            prompt += f"\n\nFor this reaction, you can respond if you want, but you shouldn't if not necessary. You can also use the reaction command to add more reactions to the message."
            return prompt

    async def handle_attachments(
        self,
        message: discord.Message,
        prompt: str,
        interaction_type: str = None,
        **kwargs,
    ):
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
            # Check that attachment is valid
            if not isinstance(attachment[0], discord.Attachment):
                self.logger.error(
                    f"Invalid attachment type: {type(attachment[0])}. Expected discord.Attachment."
                )
                continue

            attachment_processed = await self._handle_attachment(*attachment)
            if attachment_processed[1]:
                processed_attachments.append(attachment_processed[1])
            else:
                await message.channel.send(
                    embed=discord.Embed(
                        title="Attachment Error",
                        description=f"Error processing attachment {attachment[0].filename}: {attachment_processed[0]}",
                        color=discord.Color.red(),
                    )
                )
                processed_attachments.append(
                    f"User sent an attachment, but it could not be processed. File: {attachment[0].filename} Error: {attachment_processed[0]}"
                )

        return processed_attachments

    async def _handle_attachment(
        self,
        attachment: discord.Attachment,
        image: bool = False,
        upload_mode: bool = True,
    ):
        """Handle an attachment"""
        # Determine file name and location
        directory = self.core.files.get_cache_dir()
        file_name = os.path.join(
            directory, attachment.filename if attachment.filename else "attachment"
        )

        # Download the file (overwrite if it exists)
        if not isinstance(attachment.url, str) or not attachment.url:
            self.logger.error(f"Invalid URL for attachment: {attachment.url}")
            return ("Invalid URL", None)

        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status != 200:
                    self.logger.error(f"Failed to download file: {resp.status}")
                    return (f"Failed to download file: {resp.status}", None)
                with open(file_name, "wb") as f:
                    f.write(await resp.read())

        if upload_mode:
            try:
                file = gemini.upload_file(file_name)
            except:
                self.logger.warning(
                    f"Error uploading file: {file_name}. Attempting to process locally..."
                )

            else:
                return (None, file)

        # Determine the file type
        mime_type, _ = mimetypes.guess_type(file_name)
        if mime_type is None:
            file_type = "unknown"
            self.logger.error(f"File type not found for {file_name}")
            return ("Unsupported file type", None)

        if (
            mime_type
            in [
                "image/png",
                "image/jpeg",
                "image/gif",
                "image/webp",
                "image/heic",
            ]
            or image
        ):
            file_type = "image"
            try:
                # Process the image
                image = Image.open(file_name)
                return (None, image)
            except:
                self.logger.error(f"Error processing image: {file_name}")
                return ("Error processing image", None)

        if mime_type in [
            "audio/wav",
            "audio/mpeg",  # MP3
            "audio/ogg",  # Ogg Vorbis
            "audio/aac",  # AAC
            "audio/webm",  # WebM
            # Add more as needed...
        ]:
            # Offical Gemini docs: https://ai.google.dev/gemini-api/docs/audio?lang=python
            file_type = "audio"
            try:
                audio = gemini.upload_file(file_name)
                return (None, audio)
            except:
                self.logger.error(f"Error processing audio: {file_name}")
                return ("Error processing audio", None)

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

    async def save_response_model(
        self, response: gemini_generation_types.AsyncGenerateContentResponse
    ):
        """Save the response model to the database"""
        parts = response.parts

        # Process parts
        parts_list = []
        for part in parts:
            if part.text:
                parts_list.append(part.text)
            # The model gets too confused
            # if part.function_call:
            #     function_call_data = {
            #         "name": part.function_call.name,
            #     }
            #     if part.function_call.args:
            #         function_call_data["args"] = dict(part.function_call.args)
            #     parts_list.append(
            #         f"```Function Call\n{json.dumps(function_call_data, indent=4)}\n```"
            #     )

        await self.core.append_to_history(
            instance_id=self.channel_id,
            origin="model",
            parts=parts_list,
        )

    async def process_response(
        self,
        response: gemini_generation_types.AsyncGenerateContentResponse,
        message: discord.Message,
    ):
        """Process the response from the model"""
        # Save the response model to the database if history is enabled
        if self.instance_config.get("history", {}) != {}:
            if (
                self.instance_config.get("history", {}).get("type", "database")
                == "database"
            ):
                self.logger.info("Saving response to database")
                # Save the response model
        await self.save_response_model(response)

        # Iterate through parts
        for part in response.parts:
            if part.text:
                await self.handle_action(
                    action="send", args={"content": part.text}, message=message
                )
            if part.function_call:
                await self.handle_action(
                    action=part.function_call.name,
                    args=dict(part.function_call.args),
                    message=message,
                )

    def split_message(self, message: str, char_limit: int = 2000) -> list:
        """
        Splits a given message into a list of segments, each of which does not exceed the specified character limit.
        Args:
            message (str): The input message to be split.
            char_limit (int, optional): The maximum number of characters allowed in each segment. Defaults to 2750.
        Returns:
            list: A list of message segments, each of which is within the character limit.
        """

        # Split the input message into paragraphs based on newline
        paragraphs = message.split("\n")
        result = []
        current_segment = ""

        # Ensure paragraphs do not initially exceed the character limit
        new_paragraphs = []
        for para in paragraphs:
            if len(para) > char_limit:
                # Split into segments that are exactly the character limit (or less)
                for i in range(0, len(para), char_limit):
                    new_paragraphs.append(para[i : i + char_limit])
            else:
                new_paragraphs.append(para)

        # Join paragraphs into segments that are less than the character limit
        for para in new_paragraphs:
            # Check if adding the next paragraph exceeds the character limit
            if (
                len(current_segment) + len(para) + (1 if current_segment else 0)
                <= char_limit
            ):
                # If it doesn't, add the paragraph to the current segment
                if current_segment:
                    current_segment += "\n" + para
                else:
                    current_segment = para
            else:
                # If it does exceed, save the current segment and start a new one
                result.append(current_segment)
                current_segment = para

        # Append any remaining part of the message
        if current_segment:
            result.append(current_segment)

        return result

    async def handle_action(self, action: str, args: dict, message: discord.Message):
        if action == "send":
            content = args.get("content", "").strip()
            if len(content) == 0 or content is None:
                self.logger.warning("No message to send")
                return
            try:
                # Split the message
                message_chunks = self.split_message(content)
            except Exception as e:
                self.logger.error(f"Error splitting message: {e}")
                return

            # Send the message
            for chunk in message_chunks:
                await message.channel.send(chunk)

        elif action == "sticker":
            sticker_id = args.get("id")
            if len(sticker_id) == 0 or sticker_id is None:
                self.logger.warning("No sticker ID provided")
                return
            try:
                sticker_id = int(sticker_id.strip())
            except ValueError:
                self.logger.warning("Invalid sticker ID")
                return

            sticker = await self.core.bot.fetch_sticker(sticker_id)
            if not sticker:
                self.logger.warning("Sticker not found")
                return

            await message.channel.send(stickers=[sticker])
        elif action == "reaction":
            emoji = args.get("emoji")
            if len(emoji) == 0 or emoji is None:
                self.logger.warning("No emoji provided")
                return
            try:
                await message.add_reaction(emoji)
            except discord.errors.HTTPException:
                self.logger.warning("Invalid emoji")

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
            content = args.get("content")
            if len(content) == 0 or content is None:
                self.logger.warning("No message to send")
                return
            user = message.author
            try:
                # Split the message
                chunks = self.split_message(content)
                for chunk in chunks:
                    await user.send(chunk)
            except discord.errors.Forbidden:
                self.logger.warning("Failed to send DM")

                # Notify the user
                await message.channel.send(
                    embed=discord.Embed(
                        title="Direct Message Failed",
                        description="Failed to send a direct message to the user.",
                        color=discord.Color.red(),
                    )
                )

                # Notify the model
                request = f"Failed to send a direct message to the user. The server may have direct messages disabled or the user may have blocked/denied messages from this bot."
                await self._model_system_request(request, message)

        elif action == "panic":
            fields = []
            self.logger.warning("Panic mode activated")
            reason = args.get("reason")
            mute = args.get("mute_user", False)
            if reason is not None:
                fields.append({"name": "Reason", "value": reason})

            suggested_action = args.get("suggested_action")
            if suggested_action is not None:
                fields.append({"name": "Suggested Action", "value": suggested_action})

            if mute:
                mute_id = message.author.id

            fields.append(
                {
                    "name": "Instance",
                    "value": f"Channel: {message.channel.mention} | {message.guild.id}/{message.channel.id}",
                }
            )

            await self.core.bot.shell.log(
                f"A Jerry Gemini Model has triggered panic mode.",
                title="Model Panic",
                cog="JerryGemini",
                msg_type="error",
                fields=fields,
            )

        elif action == "pro_query":
            prompt = args.get("prompt")
            if len(prompt) == 0 or prompt is None:
                self.logger.warning("No prompt provided for Pro Query")
                return

            if not self.core.pro_model:
                self.logger.warning("Pro Model is not enabled")
                await message.channel.send(
                    embed=discord.Embed(
                        title="Pro Model Disabled",
                        description="The Pro Model is currently disabled. Please try again later.",
                        color=discord.Color.red(),
                    )
                )
                self.logger.warning("Pro Model is not enabled")
                await self._model_system_request(
                    f"Pro Model is not enabled for this instance. Respond without using the Pro Model.",
                    message=message,
                )
                return

            await self.query_pro_model(
                prompt=prompt,
                message=message,
            )
            return

        else:
            self.logger.warning(f"Invalid action: {action}")

    async def query_pro_model(self, prompt: str, message: discord.Message):
        """Send a query to the Pro Model"""

        class ProModelInteraction(discord.ui.View):
            def __init__(
                self,
                core: JerryGemini,
                instance: "JerryGeminiInstance",
                message: discord.Message,
                prompt: str,
            ):
                super().__init__(timeout=60)
                self.core = core
                self.instance = instance
                self.message = message
                self.logger = logging.getLogger(
                    f"jerry.gemini.{instance.channel_id}.pro_model_interaction"
                )
                self.prompt = prompt

            @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
            async def approve(
                self, interaction: discord.Interaction, button: discord.ui.Button
            ):
                """Approve the Pro Model query"""
                await interaction.response.defer()

                await interaction.message.edit(
                    embed=discord.Embed(
                        title="Processing Pro Model Query",
                        description="Your Pro Query has been approved and is being processed. Please wait...",
                        color=discord.Color.blue(),
                    ),
                    view=None,  # Remove the buttons
                )

                # Send the query to the Pro Model
                try:
                    self.logger.info(f"Processing Pro Query: {prompt}")

                    response = await self.core.query_pro_model(prompt)

                    self.logger.info(f"Pro Query response: {response}")

                    await self.instance._model_system_request(
                        f"Pro Query processed successfully: \n{response}\n[End of Pro Query]\nYou can now respond to the user with the Pro Model response.",
                        message=self.message,
                    )

                    await interaction.message.edit(
                        embed=discord.Embed(
                            title="Query Completed",
                            description=f"Your Pro Model query has been processed successfully.",
                            color=discord.Color.green(),
                        ).add_field(
                            name="Prompt Used",
                            value=self.prompt if len(self.prompt) < 1024 else f"{self.prompt[:1020]}...",
                        ),
                    )

                except Exception as e:
                    self.logger.error(f"Error processing Pro Query: {e}")
                    await interaction.message.edit(
                        embed=discord.Embed(
                            title="Pro Query Error",
                            description=f"An error occurred while processing your query: {e}",
                            color=discord.Color.red(),
                        ),
                        view=None,  # Remove the buttons
                    )
                finally:
                    self.stop()

            @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
            async def deny(
                self, interaction: discord.Interaction, button: discord.ui.Button
            ):
                """Deny the Pro Model query"""
                await interaction.response.defer()
                # Edit the message to indicate denial
                await interaction.message.edit(
                    embed=discord.Embed(
                        title="Pro Query Denied",
                        description="The Pro Model query has been denied.",
                        color=discord.Color.red(),
                    ),
                    view=None,  # Remove the buttons
                )
                await self.instance._model_system_request(
                    f"Pro Model query denied by user {interaction.user.display_name} (ID: {interaction.user.id}). The user did not approve the use of the Pro Model for the query.",
                    message=self.message,
                )
                self.stop()

        # Notify the user
        await message.channel.send(
            embed=discord.Embed(
                title="Pro Model Query",
                description=f"You have requested a Pro Model query. Please approve or deny it below.",
                color=discord.Color.green(),
            ).add_field(
                name="Requested Prompt",
                value=prompt if len(prompt) < 1024 else f"{prompt[:1020]}...",
            ),
            view=ProModelInteraction(
                core=self.core,
                instance=self,
                message=message,
                prompt=prompt,
            ),
        )
        return

    async def handle(
        self, message: discord.Message, interaction_type: str = "message", **kwargs
    ):
        """Process an incoming message"""
        failure = None
        failure_type = None

        self.last_message = time.time()

        # Retry loop
        for i in range(3):  # Retry 3 times
            try:
                self.logger.debug(
                    f"Message received: {message.content} | Interaction Type: {interaction_type}"
                )
                # Typing indicator
                async with message.channel.typing():
                    # Check if the chat is initialized
                    if not self.chat:
                        self.logger.debug("Chat not initialized, initializing...")
                        await self.start_chat()

                    # Generate the prompt
                    self.logger.debug("Generating prompt")
                    prompt = await self.generate_prompt(
                        message, interaction_type=interaction_type, **kwargs
                    )

                    # Debugging - Send prompt
                    if self.instance_config.get("debug", {}).get("prompt", False):
                        await message.channel.send(
                            embed=discord.Embed(
                                title="Debug Prompt",
                                description=prompt,
                                color=discord.Color.blue(),
                            )
                        )

                    # Handle Attachments
                    self.logger.debug("Handling attachments")
                    content = await self.handle_attachments(
                        message, prompt, interaction_type=interaction_type, **kwargs
                    )

                    # Save (plain text only) to history
                    try:
                        plain_content = []
                        if isinstance(content, list):
                            for part in content:
                                if isinstance(part, str):
                                    plain_content.append(part)
                                else:
                                    plain_content.append(
                                        f"Warning: Attachment included is not saved to history."
                                    )

                        else:
                            plain_content.append(content)
                        self.logger.info(f"Saving message to history: {plain_content}")
                        await self.core.append_to_history(
                            instance_id=self.channel_id,
                            origin="user",
                            parts=plain_content,
                        )
                    except Exception as e:
                        self.logger.error(f"Error saving message to history: {e}")
                        await self.core.bot.shell.log(
                            f"Failed to save message to history: {e} \nChannel:\n({message.channel.mention} | {message.guild.id}/{message.channel.id})",
                            title="Message Save Error",
                            cog="JerryGemini",
                            msg_type="error",
                        )

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
                    except Exception as e:
                        # Retry
                        self.logger.error(f"Error sending message to gemini: {e}")
                        failure = e
                        failure_type = "gemini-send"
                        continue

                    # Debugging - Full response as JSON
                    if self.instance_config.get("debug", {}).get("response", False):
                        debug_output = json.dumps(
                            response.to_dict(), indent=4, ensure_ascii=False
                        )

                        if len(debug_output) > 1930:
                            # Send as json file
                            cache_dir = self.core.files.get_cache_dir()
                            with open(
                                f"{cache_dir}/debug_output.json", "w"
                            ) as json_file:
                                json.dump(
                                    response.to_dict(),
                                    json_file,
                                    indent=4,
                                    ensure_ascii=False,
                                )
                            await message.channel.send(
                                file=discord.File(
                                    os.path.join(cache_dir, "debug_output.json")
                                ),
                            )
                        else:
                            await message.channel.send(f"```json\n{debug_output}```")

                    # Process the response
                    try:
                        self.logger.debug(f"Processing response: {response.text}")
                    except:
                        self.logger.debug(f"Processing response (No text)")

                    try:
                        await self.process_response(response, message)
                    except Exception as e:
                        self.logger.error(f"Error processing response: {e}")
                        await message.channel.send(
                            embed=discord.Embed(
                                title="Error Encountered",
                                description=f"An error occurred while processing the response from {self.core.NAME}.",
                                color=discord.Color.red(),
                            )
                        )
                        await self.core.bot.shell.log(
                            f"Failed to process response: {e} \nChannel:\n({message.channel.mention} | {message.guild.id}/{message.channel.id})",
                            title="Response Proccess Error",
                            cog="JerryGemini",
                            msg_type="error",
                        )

                    break

                if failure:
                    if failure_type == "gemini-send":
                        await message.channel.send(
                            embed=discord.Embed(
                                title="Error Encountered",
                                description=f"Forwarding your message to {self.core.NAME} failed. Please try again later.",
                                color=discord.Color.red(),
                            )
                        )
                        await self.core.bot.shell.log(
                            f"Failed to send message to Gemini: {e} \nChannel:\n({message.channel.mention} | {message.guild.id}/{message.channel.id})",
                            title="Message Send Error",
                            cog="JerryGemini",
                            msg_type="error",
                        )

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

            break

    async def _model_system_request(self, request: str, message: discord.Message):
        """Send a system message to the model"""
        # Format the request
        prompt = await self.core.generate_prompt()

        # Append the request
        prompt += f"\n\nConversation Agent Alert: \n```\n{request}\n```"

        # Send the message to the model
        response = await self.chat.send_message_async(prompt)

        # Debug mode
        if self.instance_config.get("debug", False):
            await message.channel.send(
                f"```json\n{json.dumps(response.to_dict(), indent=4)}```"
            )

        # Process the response
        await self.process_response(response, message)

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
                await self._model_system_request(
                    f"An error occurred while starting the hide and seek game: {e}",
                    message,
                )
            except:
                self.hs_logger.error("Failed to notify model")

    async def _hide_seek_found(
        self, payload: discord.RawReactionActionEvent, job: dict
    ):
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
                self.hs_logger.debug(
                    "Channel does not allow @everyone to send messages"
                )
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

            self.hs_logger.info(
                f"Found message to hide emoji: {message.content} (ID: {message.id}) in channel {channel.name}"
            )
            return message

        self.hs_logger.error("Failed to find message to hide emoji")
