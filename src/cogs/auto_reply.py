# Packages
import discord
from discord.ext import commands
import logging
import os
import re
import shutil
import random
import aiohttp
from typing import Optional

# squid-core
import core

class AutoReply(commands.Cog):
    """
    (V2) Listens for messages and replies with a set message configurable in a YAML file.
    """

    def __init__(self, bot: core.Bot):
        self.bot = bot
        self.logger = logging.getLogger("jerry.auto_reply")

        # Configuration
        self.files = self.bot.filebroker.configure_cog(
            "AutoReplyV2",
            config_file=True,
            config_default=self.DEFAULT_CONFIG,
            config_do_cache=300,
            cache=True,
        )
        self.files.init()

        self.auto_reply_cache = {}
        self.auto_reply_cache_timeout = 0  # Default
        self.auto_reply_cache_last_updated = 0

        self.replied_messages_cache = {}

        # Command
        self.bot.shell.add_command(
            "autoreply", cog="AutoReplyV2", description="Manage Jerry's auto-reply"
        )

        # Load and verify the configuration
        config = self.get_config()

        self.logger.debug("Cfg: " + str(config))

        if config.get("invalid"):
            self.logger.error("Invalid configuration: " + config["invalid"])
            return

        if config.get("config", {}).get("wipe_image_cache_on_start", True):
            self.clear_image_cache()

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

    def clear_image_cache(self):
        """Clear the image cache"""
        self.logger.info("Clearing image cache")
        try:
            shutil.rmtree(self.files.get_cache_dir())
            os.makedirs(self.files.get_cache_dir())
        except FileNotFoundError:
            pass
        except Exception as e:
            self.logger.error(f"Error clearing image cache: {e}")

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

        if response.get("type") == "reaction":
            if not (response.get("emoji") or response.get("id")):
                return (False, "Response type is reaction, but no emoji was provided")

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
            if key not in [
                "text",
                "type",
                "random",
                "vars",
                "path",
                "url",
                "bad",
                "emoji",
                "id",
                "note",
            ]:
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
        # Ignore messages from the bot
        if message.author == self.bot.user:
            return

        response = await self.process_message(message)

        if response is None:
            return

        elif isinstance(response, discord.Message):
            self.logger.debug(
                f"Auto-reply message sent: {response.content}, caching message"
            )
            self.replied_messages_cache[message.id] = response
            return

        self.logger.debug(f"How did we get here? 🤔")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        # Ignore if the content is the same
        if before.content.strip() == after.content.strip():
            return

        # Ignore messages edited by the bot
        if before.author == self.bot.user:
            return

        # Check the message cache
        if before.id in self.replied_messages_cache:
            edit: discord.Message = self.replied_messages_cache[before.id]
        else:
            edit = None

        response = await self.process_message(after, edit)

        if response is None:
            if edit:
                # await edit.delete()
                # self.replied_messages_cache.pop(before.id)

                edit_edit = await edit.edit(
                    content="Bro why did you edit your message 🤔🤨"
                )
                self.replied_messages_cache[after.id] = edit_edit

            return

        elif isinstance(response, discord.Message):
            self.logger.debug(
                f"Auto-reply message sent: {response.content}, caching message"
            )
            self.replied_messages_cache[after.id] = response
            return

        self.logger.debug(f"How did we get here? 🤔")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.id in self.replied_messages_cache:
            edit = self.replied_messages_cache[message.id]

            message_as_embed = discord.Embed(
                description=message.content,
                color=discord.Color.blurple(),
            )
            message_as_embed.set_author(
                name=message.author.display_name, icon_url=message.author.avatar.url
            )
            message_as_embed.set_footer(text="Original Message")

            bots_message_as_embed = discord.Embed(
                description=edit.content,
                color=self.bot.JERRY_RED,
            )
            bots_message_as_embed.set_author(
                name="Me", icon_url=self.bot.user.avatar.url
            )
            bots_message_as_embed.set_footer(text="My GOATED Response")

            edit_response = "Hey why did you delete this? 🤔"

            edit_edit = await edit.edit(
                content=edit_response, embeds=[message_as_embed, bots_message_as_embed]
            )

            self.replied_messages_cache[message.id] = edit_edit

    async def process_message(
        self, message: discord.Message, edit: discord.Message = None
    ) -> Optional[discord.Message]:
        """Process a discord message for auto-reply"""

        config = self.get_config()

        if config.get("invalid"):
            await self.bot.shell.log(
                f"Auto-reply configuration error: {config.get('error', 'Unknown error')}",
                "Auto-Reply",
                msg_type="error",
                cog="AutoReply",
            )
            return None

        self.logger.debug(config)

        response = await self._scan_message(message, config)
        if not response:
            self.logger.debug("No response found")
            return None

        self.logger.debug(response)

        return await self._do_reponse(message, response, config, edit)

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
        self,
        message: discord.Message,
        response: dict,
        config: dict = None,
        edit: discord.Message = None,
    ) -> Optional[discord.Message]:
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
            return None

        if response.get("text"):
            if response.get("bad"):
                if edit:
                    try:
                        return await edit.edit(content=response["text"])
                    except:
                        pass
                return await message.channel.send(response["text"])
            else:
                if edit:
                    try:
                        return await edit.edit(content=response["text"])
                    except Exception as e:
                        self.logger.error(f"Failed to edit message: {e}")
                return await message.reply(response["text"])

        elif response.get("random"):
            return await self._do_reponse(
                message, random.choice(response["random"]), config=config, edit=edit
            )

        elif response.get("type") == "file":
            if response.get("url"):
                file = await self._handle_file(url=response["url"], config=response)
            elif response.get("path"):
                file = await self._handle_file(path=response["path"], config=response)
            else:
                self.logger.error("File response is missing URL or path")
                return None

            if file:
                if response.get("bad"):
                    if edit:
                        try:
                            return await edit.edit(file=file)
                        except:
                            pass
                    return await message.channel.send(file=file)
                else:
                    if edit:
                        try:
                            return await edit.edit(file=file)
                        except:
                            pass
                    return await message.reply(file=file)

        elif response.get("type") == "reaction":
            if response.get("emoji"):
                await message.add_reaction(response["emoji"])
            elif response.get("id"):
                try:
                    emoji_id = int(response["id"])
                except ValueError:
                    self.logger.error(f"Invalid emoji ID: {response['id']}")
                    return None
                emoji = self.bot.get_emoji(emoji_id)
                if emoji:
                    await message.add_reaction(emoji)
                else:
                    self.logger.error(f"Failed to find emoji with ID {response['id']}")
            else:
                self.logger.error("Reaction response missing both emoji and id")

            return None

        return None

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



