"""
[Revision 2] Stickers module for Jerry bot.
Allows the bot to manage and serve stickers from a specific pack.
"""

import discord
from discord import app_commands
from discord.ext import commands

import aiofiles
import logging
import hashlib
import os

from dataclasses import dataclass

import core as squidcore

logger = logging.getLogger("jerry.stickers")


class StickersMongo:
    """Schema constants"""

    COLLECTION_NAME = "jerry.stickers"
    SCHEMA = {
        "$jsonSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "required": True, "unique": True},
                "description": {"type": "string", "default": ""},
                "file_path": {"type": "string", "required": True},
                "sha256": {"type": "string", "required": True},
            },
        }
    }
    COLLECTION_SEARCH_INDEX = [
        ("name", "text"),
        ("description", "text"),
    ]
    COLLECTION_SEARCH_INDEX_WEIGHT = {
        "name": 10,
        "description": 5,
    }


@dataclass
class Sticker:
    """Data class for a sticker."""

    name: str
    description: str
    sha256: str
    tags: list = None
    file_path: str = None
    attachment: discord.Attachment = None


class StickerAddConfirmView(discord.ui.View):
    """Confirmation view for adding a sticker."""

    def __init__(
        self,
        interaction: discord.Interaction,
        sticker_name: str,
        sticker_description: str,
        sticker_file: discord.Attachment,
        core: "Stickers",
    ):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.sticker_name = sticker_name
        self.sticker_description = sticker_description
        self.sticker_file = sticker_file
        self.core = core

    @discord.ui.button(label="Confirm ✅", style=discord.ButtonStyle.green)
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle the confirmation button click."""
        output = await self.core.add_sticker_to_db(
            self.sticker_name,
            self.sticker_description,
            self.sticker_file,
        )
        await interaction.response.send_message(
            output,
            ephemeral=True,
        )
        await self.interaction.delete_original_response()
        self.stop()

    @discord.ui.button(label="Cancel ❌", style=discord.ButtonStyle.red)
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle the cancel button click."""
        await interaction.response.send_message(
            "Sticker addition cancelled.", ephemeral=True
        )
        await self.interaction.delete_original_response()
        self.stop()


class StickerSearchView(discord.ui.View):
    """View for searching stickers."""

    def __init__(
        self,
        interaction: discord.Interaction,
        core: "Stickers",
        stickers: list[Sticker] = None,
    ):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.core = core
        self.stickers = stickers or []
        self.add_item(StickerSelect(self.stickers))

    async def on_timeout(self):
        """Disable the select menu when the view times out."""
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                item.disabled = True
        await self.interaction.edit_original_response(view=self)
        await super().on_timeout()


class StickerSelect(discord.ui.Select):
    def __init__(self, stickers: list[Sticker]):
        options = [
            discord.SelectOption(
                label=sticker.name,
                description=sticker.description or "No description provided.",
                value=sticker.name,
                emoji="🟢" if sticker.file_path else "❌",
            )
            for sticker in stickers
        ]
        self.stickers = stickers
        super().__init__(placeholder="Select a sticker...", options=options)

    async def callback(self, interaction: discord.Interaction):
        """Handle the sticker selection."""
        await interaction.response.defer(ephemeral=True)

        selected_sticker_name = self.values[0]
        selected_sticker = next(
            (
                sticker
                for sticker in self.stickers
                if sticker.name == selected_sticker_name
            ),
            None,
        )

        if not selected_sticker:
            await interaction.followup.send(
                "❌ Sticker not found.",
                ephemeral=True,
            )
            return

        # Create a view to handle sending or DMing the sticker
        view = StickerGetView(interaction, selected_sticker)
        await interaction.followup.send(
            content="",
            view=view,
            file=discord.File(selected_sticker.file_path),
            embed=discord.Embed(
                title=selected_sticker.name,
                description=selected_sticker.description or "No description provided.",
                color=discord.Color.red(),
            ),
            ephemeral=True,
        )


class StickerGetView(discord.ui.View):
    """View when using the sticker command to get a sticker."""

    def __init__(self, interaction: discord.Interaction, sticker: Sticker):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.sticker = sticker

    # Send the sticker to the channel
    @discord.ui.button(label="Send Here", style=discord.ButtonStyle.green)
    async def send_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle the send button click."""
        await interaction.response.defer(ephemeral=True)
        if self.sticker.file_path:
            channel = interaction.channel or interaction.user.dm_channel
            if channel is None:
                await interaction.followup.send(
                    "❌ Could not find a channel associated with this interaction. Please try again later. (Bot should be installed in this location.)",
                    ephemeral=True,
                )
                return
            try:
                await channel.send(
                    "",
                    file=discord.File(self.sticker.file_path),
                )
                await interaction.followup.send(
                    "✅",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ Missing permissions to send files in this channel. Ensure the bot is installed in this channel and has the required permissions.",
                    ephemeral=True,
                )
                return
        else:
            await interaction.followup.send(
                "❌ Sticker file not found. If this is an error, please contact the bot admins.",
                ephemeral=True,
            )

    # DM the sticker to the user
    @discord.ui.button(label="DM Me", style=discord.ButtonStyle.blurple)
    async def dm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle the DM button click."""
        await interaction.response.defer(ephemeral=True)
        if self.sticker.file_path:
            try:
                await interaction.user.send(
                    "",
                    file=discord.File(self.sticker.file_path),
                )
                await interaction.followup.send(
                    "✅ Sticker sent to your DMs.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ Could not send you a DM. Please check your privacy settings.",
                    ephemeral=True,
                )
        else:
            await interaction.followup.send(
                "❌ Sticker file not found. If this is an error, please contact the bot admins.",
                ephemeral=True,
            )

    # On timeout, disable the buttons
    async def on_timeout(self):
        """Disable the buttons when the view times out."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await self.interaction.edit_original_response(view=self)
        await super().on_timeout()


class Stickers(commands.Cog):
    """A cog for managing and serving stickers in the Jerry bot."""

    def __init__(self, bot: squidcore.Bot):
        self.bot = bot
        self.files = self.bot.filebroker.configure_cog(
            "Stickers",
            perm=True,
        )
        self.assets_path = self.files.get_perm_dir()
        self.logger = logging.getLogger("jerry.stickers")

        self.stickers_collection = None

    async def cog_load(self):
        """Load the sticker pack."""
        if not os.path.exists(self.assets_path):
            self.logger.warning(
                f"Sticker pack path {self.assets_path} does not exist, creating it."
            )
            os.makedirs(self.assets_path, exist_ok=True)

        if self.bot.memory.mongo_db is None:
            self.logger.error("MongoDB is not connected. Cannot load stickers.")
            return

        existing_collections = await self.bot.memory.mongo_db.list_collection_names()
        if StickersMongo.COLLECTION_NAME not in existing_collections:
            self.logger.info("Creating stickers collection in MongoDB.")
            await self.bot.memory.mongo_db.create_collection(
                StickersMongo.COLLECTION_NAME
            )
            await self.bot.memory.mongo_db[StickersMongo.COLLECTION_NAME].create_index(
                StickersMongo.COLLECTION_SEARCH_INDEX,
                weights=StickersMongo.COLLECTION_SEARCH_INDEX_WEIGHT,
                name="sticker_search_index",
            )
        self.stickers_collection = self.bot.memory.mongo_db[
            StickersMongo.COLLECTION_NAME
        ]

    async def cog_status(self):
        return "Ready"

    async def add_sticker_to_db(
        self,
        sticker_name: str,
        sticker_description: str,
        sticker_file: discord.Attachment,
    ) -> str:
        """Add a sticker to the MongoDB collection."""
        output_message = ""

        file = await sticker_file.read()
        extension = sticker_file.filename.split(".")[-1].lower()
        sha256_hash = hashlib.sha256(file).hexdigest()

        # Generate a unique file path
        file_path = os.path.join(self.assets_path, f"{sha256_hash}.{extension}")
        if not os.path.exists(file_path):
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file)

        else:
            self.logger.warning(
                f"Sticker file {file_path} already exists. Skipping file write."
            )
            output_message += f"Warning: This sticker's file already exists in storage. Is this a duplicate? Hash 👇\n||SHA256: {sha256_hash}||\n"

        # Prepare the sticker document
        sticker_doc = {
            "name": sticker_name,
            "description": sticker_description,
            "file_path": file_path,
            "sha256": sha256_hash,
            "tags": [],
        }
        # Check if the sticker already exists
        existing_sticker = await self.stickers_collection.find_one(
            {"name": sticker_name}
        )
        if existing_sticker:
            self.logger.warning(
                f"Sticker '{sticker_name}' already exists in the database. Skipping addition."
            )
            return (
                output_message
                + f"A sticker with the name '{sticker_name}' already exists in the database, please choose a different name."
            ).strip()

        # Insert the sticker into the collection
        result = await self.stickers_collection.insert_one(sticker_doc)
        if result.acknowledged:
            self.logger.info(
                f"Sticker '{sticker_name}' added successfully with ID {result.inserted_id}."
            )
        else:
            self.logger.error(
                f"Failed to add sticker '{sticker_name}' to the database."
            )
            return "Failed to add sticker to the database."

        return (
            output_message + f"Sticker '{sticker_name}' added successfully! ✅"
        ).strip()

    async def get_sticker_by_name(self, sticker_name: str) -> Sticker | None:
        """Retrieve a sticker by its name."""
        sticker = await self.stickers_collection.find_one({"name": sticker_name})
        if not sticker:
            self.logger.error(f"Sticker '{sticker_name}' not found in the database.")
            return None

        file_path = sticker.get("file_path")
        if not file_path or not os.path.exists(file_path):
            self.logger.error(
                f"File for sticker '{sticker_name}' not found at {file_path}."
            )
            return None

        file = discord.File(file_path)

        return Sticker(
            name=sticker["name"],
            description=sticker.get("description", ""),
            file_path=sticker.get("file_path", ""),
            sha256=sticker.get("sha256", ""),
            tags=sticker.get("tags", []),
            attachment=None,  # Attachments are not used in this context
        )

    async def search_stickers(self, query: str) -> list[Sticker]:
        """Search for stickers by name or description."""
        if not query:
            return []

        search_query = {"$text": {"$search": query}}
        score = {"score": {"$meta": "textScore"}}

        stickers = []
        async for sticker in (
            self.stickers_collection.find(search_query, score)
            .sort([("score", {"$meta": "textScore"})])
            .limit(20)
        ):
            file_path = sticker.get("file_path")
            if file_path and os.path.exists(file_path):
                stickers.append(
                    Sticker(
                        name=sticker["name"],
                        description=sticker.get("description", ""),
                        file_path=file_path,
                        sha256=sticker.get("sha256", ""),
                        tags=sticker.get("tags", []),
                    )
                )
            else:
                self.logger.warning(
                    f"File for sticker '{sticker['name']}' not found at {file_path}."
                )

        return stickers

    async def get_categories(self) -> list[str]:
        """Get a list of sticker categories."""
        categories = set()
        async for sticker in self.stickers_collection.find({}):
            if "/" in sticker["name"]:
                category = sticker["name"].split("/")[0]
                categories.add(category)
        return sorted(categories)
    
    @app_commands.command(
        name="sticker-help",
        description="Get help on how to use the sticker commands.",
    )
    async def sticker_help(self, interaction: discord.Interaction):
        """Provide help on how to use the sticker commands."""
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Sticker Commands Help",
                description=(
                    "A curated sticker pack for Jerry bot.\n"
                ),
                color=self.bot.JERRY_RED,
            ).add_field(
                name="Sticker Categories",
                value=", ".join(await self.get_categories()) or "No categories found.",
                inline=False,
            ).add_field(
                name="Commands",
                value=(
                    "Use `/sticker <category/name>` to retrieve a sticker by its name. (eg: minecraft/fish). You can also search for stickers by name or description.\n"
                    "Use `/sticker-force <category/name>` to forcefully send a sticker to the channel or DM. Where bot is not installed. (Contact bot admins to install the bot as a user integration)\n"
                    "Use `/sticker-add` to add a new sticker (Jerry bot admins only)."
                ),
                inline=False
            ).add_field(
                name="Adding Stickers",
                value=(
                    "This sticker pack is curated by the Jerry bot team. If you have suggestions for new stickers, please contact the bot admins."
                ),
                inline=False
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="sticker",
        description="Grab a sticker from jerry's sticker database. (Supports search)",
    )
    @app_commands.describe(
        sticker="Sticker name or search query (formatted as category/name, e.g., minecraft/fish)."
    )
    async def sticker(self, interaction: discord.Interaction, sticker: str):
        """Retrieve a sticker by name."""

        await interaction.response.defer(ephemeral=True)

        sticker_file = await self.get_sticker_by_name(sticker)
        if sticker_file is None:
            # await interaction.followup.send(
            #     f"Sticker '{sticker}' not found. �",
            #     ephemeral=True,
            # )
            # return
            stickers = await self.search_stickers(sticker)
            if not stickers:
                await interaction.followup.send(
                    "",
                    embed=discord.Embed(
                        description=f"Sticker '{sticker}' not found. Please check the name or try searching for a different sticker.",
                        color=self.bot.JERRY_RED,
                    ).set_footer(
                        text="Tip: Use /sticker-help to find sticker categories."
                    ),
                    ephemeral=True,
                )
                return
            # If no exact match, show search results
            view = StickerSearchView(interaction, self, stickers)
            await interaction.followup.send(
                "",
                embed=discord.Embed(
                    description="No exact match found. Below are some similar stickers:",
                    color=self.bot.JERRY_RED,
                ).set_footer(
                    text="Tip: Use /sticker-help to find sticker categories."
                ),
                ephemeral=True,
                view=view,
            )
            return

        # Apply the view to the interaction
        view = StickerGetView(interaction, sticker_file)
        await interaction.followup.send(
            file=discord.File(sticker_file.file_path),
            embed=discord.Embed(
                title=f"{sticker_file.name}",
                description=sticker_file.description or "No description provided.",
                color=self.bot.JERRY_RED,
            ),
            ephemeral=True,
            view=view,
        )

    @app_commands.command(
        name="sticker-force",
        description="Forcefully send a sticker to the channel or DM. (Works anywhere)",
    )
    @app_commands.describe(sticker="The name of the sticker to send.")
    async def sticker_force(self, interaction: discord.Interaction, sticker: str):
        """Forcefully send a sticker to the channel or DM."""

        await interaction.response.defer(ephemeral=False)
        sticker_file = await self.get_sticker_by_name(sticker)
        if sticker_file is None:
            await interaction.followup.send(
                f"Sticker '{sticker}' not found. �",
            )
            return
        
        # Check if the file exists
        if sticker_file.file_path and os.path.exists(sticker_file.file_path):
            try:
                await interaction.followup.send(
                    "",
                    file=discord.File(sticker_file.file_path),
                )
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Failed to send sticker: {e}",
                )
                return
        else:
            await interaction.followup.send(
                "❌ Sticker file not found. This means that the bot admins are selling D:"
            )
            return

    @app_commands.command(
        name="sticker-add",
        description="[Admin Only] Add a sticker to the pack.",
    )
    @app_commands.describe(
        sticker_name="The name of the sticker. This should be formatted as catagory/name (eg: minecraft/fish).",
        sticker_description="A description for the sticker.",
        sticker_file="The file of the sticker to add.",
    )
    async def add_sticker(
        self,
        interaction: discord.Interaction,
        sticker_name: str,
        sticker_description: str,
        sticker_file: discord.Attachment,
    ):
        """Add a sticker to the pack."""
        if not await self.bot.permissions.interaction_check(
            interaction, squidcore.PermissionLevel.ADMIN
        ):
            return
        await interaction.response.defer(ephemeral=True)

        await interaction.followup.send(
            "",
            file=await sticker_file.to_file(
                filename=sticker_file.filename,
            ),
            ephemeral=True,
            view=StickerAddConfirmView(
                interaction, sticker_name, sticker_description, sticker_file, self
            ),
            embed=discord.Embed(
                title="Image Preview 🖼️",
                color=self.bot.JERRY_RED,
            )
            .add_field(
                name="Sticker Name",
                value=sticker_name,
            )
            .add_field(
                name="Description",
                value=sticker_description or "No description provided.",
            ),
        )
