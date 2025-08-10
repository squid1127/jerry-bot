"""AutoReply Cog for JerryBot, revision 3"""

# Packages
import discord
from discord.ext import commands
import logging
from voluptuous import Schema, Optional, Any, All, Length, Match
from enum import Enum
from traceback import format_exc
import re
import random

# squid-core
import core as squidcore

from .stickers import Stickers, StickerErrors
from .gemini import JerryGemini


class AutoReplySchema(Schema):
    """Schema for validating auto-reply configuration."""

    SCHEMA_RESPONSE = Schema(
        {
            Optional("var"): All(str, Length(min=1)),
            Optional("text"): All(str, Length(min=1)),
            Optional("sticker"): All(str, Length(min=1)),
            Optional("reaction"): All(str, Length(min=1)),
            Optional("random"): [
                {
                    Optional("text"): All(str, Length(min=1)),
                    Optional("sticker"): All(str, Length(min=1)),
                    Optional("reaction"): All(str, Length(min=1)),
                    Optional("note"): All(str, Length(min=1)),
                }
            ],
            Optional("merge"): bool,  # Whether to merge this response with the base response
        }
    )
    SCHEMA_FILTER = Schema(
        {
            Optional("type"): All(str, Length(min=1)),
            Optional("guild"): All(str, Length(min=1)),
            Optional("channel"): All(str, Length(min=1)),
            Optional("user"): All(str, Length(min=1)),
            Optional("role"): All(str, Length(min=1)),
        }
    )
    SCHEMA_AUTOREPLY = Schema(
        {
            Optional("regex"): All(str, Length(min=1), Match(r"^(?!\s*$).+")),
            Optional("response"): SCHEMA_RESPONSE,
            Optional("filters"): [SCHEMA_FILTER],
        }
    )
    SCHEMA = Schema(
        {
            Optional("filters"): [SCHEMA_FILTER],
            Optional("autoreply"): [SCHEMA_AUTOREPLY],
            Optional("vars"): {Any(str): SCHEMA_RESPONSE},
        }
    )


class AutoReplyStatus(Enum):
    """Enum for auto-reply status."""

    DISABLED = "disabled"
    ENABLED = "enabled"
    ERROR = "error"
    LOADING = "loading"
    READY = "ready"


class AutoReply(commands.Cog):
    """[v3] Cog for handling automatic replies to messages."""

    # Default auto-reply configuration
    DEFAULT_CONFIG = """# Default Config for the AutoReply cog

# filters:
#   - type: "ignore"
#     channel: "123456789012345678"


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

    def __init__(self, bot: squidcore.Bot):
        self.bot = bot
        self.state = AutoReplyStatus.DISABLED

        # Initialized on cog_load
        self.stickers = None
        self.gemini = None
        self.config = None
        self.responded = set()  # Track responded messages

        self.logger = logging.getLogger("jerry.auto_reply")
        


        # Configuration
        self.files = self.bot.filebroker.configure_cog(
            "AutoReply",
            config_file=True,
            config_default=self.DEFAULT_CONFIG,
            config_do_cache=300,
            cache=True,
        )
        self.files.init()

    async def cog_load(self):
        """Load the AutoReply cog."""
        self.logger.info("AutoReply cog loaded.")

        # Cog dependencies
        if "Stickers" in self.bot.cogs:
            self.stickers: Stickers = self.bot.get_cog("Stickers")
            self.logger.info("Stickers cog is available for sticker handling.")
        if "JerryGemini" in self.bot.cogs:
            self.gemini: JerryGemini = self.bot.get_cog("JerryGemini")
            self.logger.info("JerryGemini cog is available for AI-channel filtering.")

        # Verify redis connection
        if self.bot.memory.redis is None:
            self.logger.error(
                "Redis connection is not available. AutoReply cog cannot function."
            )
            self.state = AutoReplyStatus.ERROR
            raise RuntimeError("Redis connection is required for AutoReply cog.")

        # Load configuration
        try:
            config = self.files.get_config()
            config: dict = AutoReplySchema.SCHEMA(config)  # Validate configuration

        except Exception as e:
            self.logger.error(
                f"Failed to load or validate auto-reply configuration: {e}"
            )
            self.state = AutoReplyStatus.ERROR
            raise RuntimeError("Invalid auto-reply configuration.") from e

        # Add Gemini channel filters if available
        if self.gemini:
            gemini_filters = self._gemini_channels_to_ignore()
            if gemini_filters:
                config.setdefault("filters", []).extend(gemini_filters)
                self.logger.info(
                    f"Added {len(gemini_filters)} Gemini channel filters to auto-reply configuration."
                )

        self.logger.info("AutoReply configuration loaded and validated.")
        self.state = AutoReplyStatus.READY
        self.config = config

    def _gemini_channels_to_ignore(self) -> list[dict]:
        """Generate filters for Gemini channels to ignore."""
        if not self.gemini:
            return []
        ignore_channels = []
        gemini_config = self.gemini.config.config
        if not gemini_config:
            self.logger.warning(
                "Gemini configuration is not loaded, skipping Gemini channel filters."
            )
            return ignore_channels

        for channel in gemini_config.get("instances", {}).keys():
            ignore_channels.append(
                {
                    "type": "ignore",
                    "channel": str(channel),
                }
            )

        return ignore_channels
    
    def _check_filters(self, message: discord.Message, filters: list[dict]) -> bool:
        """Check if a message matches any of the provided filters."""
        require_total = 0
        require_passed = 0
        for filter in filters:
            if filter.get("type", "ignore") == "require":
                require_total += 1
                if self._check_filter(message, filter):
                    require_passed += 1
            elif filter.get("type", "ignore") == "ignore":
                # If any ignore filter matches, we skip the message
                if self._check_filter(message, filter):
                    self.logger.debug(
                        f"Message {message.id} matches ignore filter: {filter}, ignoring."
                    )
                    return True
        if require_total > 0 and require_passed < require_total:
            self.logger.debug(
                f"Message {message.id} does not match all require filters, ignoring."
            )
            return True
        return False

    def _check_filter(self, message: discord.Message, filter: dict) -> bool:
        """Check if a message matches a filter."""
        if "guild" in filter:
            if message.guild and str(message.guild.id) == filter.get("guild"):
                return True
        if "user" in filter:
            if str(message.author.id) == filter.get("user"):
                return True
        if "role" in filter:
            if message.guild and any(
                role.id == filter.get("role") for role in message.author.roles
            ):
                return True
        if "channel" in filter:
            if message.channel and str(message.channel.id) == filter.get("channel"):
                return True
        return False
    
    def _scan_message(self, message: str, regex: str) -> bool:
        """Check if the message matches the regex."""
        try:
            pattern = re.compile(regex, re.IGNORECASE)
            return bool(pattern.search(message))
        except re.error as e:
            self.logger.error(f"Invalid regex '{regex}': {e}")
            return False

    def _merge_response(self, base_response: dict, var_response: dict) -> dict:
        """Merge variable response into base response."""
        merged_response = base_response.copy()
        if "text" in var_response:
            merged_response["text"] = var_response["text"]
        if "sticker" in var_response:
            merged_response["sticker"] = var_response["sticker"]
        if "random" in var_response:
            if merged_response.get("random") is None:
                merged_response["random"] = []
            merged_response["random"].extend(var_response.get("random", []))

        return merged_response

    async def _send_response(self, message: discord.Message, response: dict) -> None:
        """Send an auto-reply response to a message."""
        reply_text = response.get("text")
        reply_sticker = response.get("sticker")
        reply_reaction = response.get("reaction")
        random_responses = response.get("random", [])

        if random_responses:
            choice = random.choice(random_responses)
            reply_text = choice.get("text", reply_text)
            reply_sticker = choice.get("sticker", reply_sticker)
            reply_reaction = choice.get("reaction", reply_reaction)

        if reply_text:
            await message.reply(reply_text)
        if reply_sticker and self.stickers:
            try:
                await message.reply(
                    "", file=await self.stickers.get_sticker_file(reply_sticker)
                )
            except StickerErrors.StickerNotFound as e:
                self.logger.warning(f"Sticker not found: {reply_sticker}")

        if reply_reaction:
            await message.add_reaction(reply_reaction)

    async def handle_message(self, message: discord.Message) -> None:
        """Handle incoming messages and return an auto-reply response if applicable."""
        if not self.config:
            self.logger.warning("AutoReply configuration is not loaded.")
            return None

        # Check filters
        if self._check_filters(message, self.config.get("filters", [])):
            self.logger.debug(f"Message {message.id} matches ignore filters, skipping.")
            return None

        # Check for auto-reply patterns
        for pattern in self.config.get("autoreply", []):
            self.logger.debug(
                f"Checking message {message.id} against pattern: {pattern}"
            )
            if "filters" in pattern:
                if self._check_filters(message, pattern["filters"]):
                    self.logger.debug(
                        f"Message {message.id} matches ignore filters for pattern: {pattern}, skipping."
                    )
                    continue
            if "regex" in pattern and self._scan_message(
                message.content, pattern["regex"]
            ):
                self.logger.info(
                    f"Message {message.id} matches auto-reply pattern: {pattern}"
                )
                response = pattern.get("response", {})
                if response.get("var"):
                    self.logger.debug(
                        f"Using variable response for pattern: {response['var']}"
                    )
                    var_name = response["var"]
                    var_response = (
                        self.config.get("vars", {})
                        .get(var_name, {})
                    )
                    if not var_response:
                        self.logger.warning(
                            f"Variable '{var_name}' not found in auto-reply vars."
                        )
                        continue
                    if var_response.get("merge", False):
                        response = self._merge_response(response, var_response)
                    else:
                        response = var_response
                if not response:
                    self.logger.warning(
                        f"No response defined for auto-reply pattern: {pattern}"
                    )
                    continue
                self.logger.debug(
                    f"Sending auto-reply response for message {message.id}: {response}"
                )
                await self._send_response(message, response)

        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Event handler for incoming messages."""
        if message.author.bot or not self.state == AutoReplyStatus.READY:
            return

        self.logger.debug(
            f"Received message: {message.content} from {message.author.name}"
        )

        try:
            await self.handle_message(message)
        except Exception as e:
            self.logger.error(f"Error handling message {message.id}: {e}")
            trackback = format_exc()
            if len(trackback) > 2000:
                trackback = trackback[:1997] + "..."
            await self.bot.shell.log(
                f"Error handling message {message.id} in AutoReply: {e}",
                msg_type="error",
                cog="AutoReply",
                title="AutoReply Error",
                fields= [
                    {
                        "name": "Traceback",
                        "value": f"```{trackback}```",
                        "inline": False,
                    }
                ]
            )
            self.state = AutoReplyStatus.ERROR
