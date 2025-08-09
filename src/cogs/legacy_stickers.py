# Packages
import discord
from discord import app_commands
from discord.ext import commands
import logging
import os
import asyncio
import re
import fuzzywuzzy
from PIL import Image
import pyheif

# squid-core
import core

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
    def __init__(self, bot: core.Bot, directory: str):
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