"""
[Revision 2] Information Channels module for Jerry bot.
Allows the bot to create embedded messages in designated channels.
"""

import discord
from discord import app_commands
from discord.ext import commands

import logging
import os
import yaml

from dataclasses import dataclass

import core as squidcore

logger = logging.getLogger("jerry.information_channels")


# Errors
class InformationChannelErrors:
    class InformationChannelNotFound(Exception):
        """Exception raised when an information channel is not found in the database."""

        pass

    class InformationMissingPermission(Exception):
        """Exception raised when the bot is missing permissions to access an information channel."""

        pass

    class InformationInvalidConfig(Exception):
        """Exception raised when the configuration of the information channel is invalid."""

        pass


# Mongo Scheme
class InformationChannelsMongo:
    """Schema constants"""

    COLLECTION_NAME = "jerry.information_channels"
    SCHEMA = {
        "$jsonSchema": {
            "type": "object",
            "required": ["server_id", "channel_id", "webhook"],
            "properties": {
                "server_id": {"bsonType": "long"},
                "channel_id": {"bsonType": "long"},
                "message": {
                    "type": "object",
                    "required": ["content"],
                    "properties": {
                        "content": {"type": "string"},
                        "embeds": {"type": "array", "items": {"type": "object"}},
                    },
                },
                "webhook": {
                    "type": "object",
                    "required": ["use"],
                    "properties": {
                        "use": {"type": "boolean"},
                        "username": {"type": "string"},
                        "image_url": {"type": "string"},
                    },
                },
            },
        }
    }
    COLLECTION_SEARCH_INDEX = [
        ("server_id", 1),
        ("channel_id", 1),
    ]
    EXAMPLE_MESSAGE_CONFIG = """use: false # Set to true
embeds:
  # Embed title
  - title:

    # Description
    description:

    color: 0x9b78f5
    fields: # \\/ Delete this section to remove fields

      # Field Title & Value
      - name:
        value:
        inline: false
"""


# Views
class ConfirmationView(discord.ui.View):
    """A view for confirming actions."""

    def __init__(
        self,
        interaction: discord.Interaction,
        yes: callable = None,
        no: callable = None,
        **kwargs,
    ):
        super().__init__(timeout=60)
        self.yes = yes
        self.no = no
        self.callable_args = kwargs
        self.interaction = interaction

    async def end_interaction(self):
        try:
            await self.interaction.delete_original_response()
        except discord.HTTPException:
            pass
        self.stop()

    @discord.ui.button(label="Yes ✔", style=discord.ButtonStyle.success)
    async def yes_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.yes:
            await self.yes(interaction, **self.callable_args)
        else:
            await interaction.response.send_message(
                "This button doesn't do anything ⚠️", ephemeral=True
            )
        await self.end_interaction()

    @discord.ui.button(label="No ✖", style=discord.ButtonStyle.danger)
    async def no_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.no:
            await self.no(interaction, **self.callable_args)
        else:
            await interaction.response.send_message("Cancelled ❌", ephemeral=True)
        await self.end_interaction()

    async def on_timeout(self):
        await self.end_interaction()


class MainMenuView(discord.ui.View):
    """A view for the main menu."""

    def __init__(
        self,
        interaction: discord.Interaction,
        core: "InformationChannels",
        config: dict,
        do_action: str = "menu",
    ):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.core = core
        self.do_action = do_action
        self.config = config

    async def end_interaction(self):
        try:
            await self.interaction.delete_original_response()
        except discord.HTTPException:
            pass
        self.stop()

    @discord.ui.button(label="Update", style=discord.ButtonStyle.primary)
    async def update_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = MainMenuUpdateContent(interaction, self.core, self.config)
        await interaction.response.send_modal(modal)
        await self.end_interaction()

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        confirmation = ConfirmationView(
            interaction=interaction,
            yes=self.core.interactive_delete_channel,
        )
        await interaction.response.send_message(
            "",
            embed=discord.Embed(
                title=f"#{interaction.channel.name} | Delete",
                description="Are you sure you want to delete this information channel?",
                color=discord.Color.red(),
            ),
            view=confirmation,
            ephemeral=True,
        )
        await self.end_interaction()

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.secondary)
    async def dismiss_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.end_interaction()

    async def on_timeout(self):
        await self.end_interaction()


class MainMenuUpdateContent(discord.ui.Modal, title="Update Content"):

    def __init__(
        self,
        interaction: discord.Interaction,
        core: "InformationChannels",
        config: dict,
    ):
        super().__init__(timeout=500)

        self.interaction = interaction
        self.core = core
        self.config = config

        current_embeds = config.get("message", {}).get("embeds", [])
        if current_embeds:
            embed_dict = {
                "use": True,
                "embeds": current_embeds
            }
            embed_default = yaml.dump(embed_dict)
        else:
            embed_default = InformationChannelsMongo.EXAMPLE_MESSAGE_CONFIG
        content_default = config.get("message", {}).get("content", "")

        self.content = discord.ui.TextInput(
            label="Content",
            style=discord.TextStyle.paragraph,
            placeholder="Plaintext message (optional)",
            required=False,
            default=content_default,
        )
        self.embeds = discord.ui.TextInput(
            label="Embeds",
            style=discord.TextStyle.paragraph,
            placeholder="YAML array of embed objects (optional)",
            required=False,
            default=embed_default,
        )

        logger.info(f"config: {self.config}")

        self.add_item(self.content)
        self.add_item(self.embeds)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        view = MainMenuView(
            self.interaction, core=self.core, config=self.config, do_action="menu"
        )

        # Parse yaml
        embeds = []
        try:
            embed_config = (
                yaml.safe_load(self.embeds.value) if self.embeds.value else {}
            )
            if embed_config.get("use") == True:
                embeds = embed_config.get("embeds", [])

        except yaml.YAMLError as e:
            await interaction.followup.send(
                "",
                embed=discord.Embed(
                    title=f"#{interaction.channel.name} | Invalid YAML",
                    description=f"Error parsing YAML: {e}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
                view=view,
            )
            return

        logger.info(
            f"#{interaction.channel.name} | Content: {self.content.value} | Embeds: {self.embeds.value}"
        )

        # Update the channel in the database
        try:
            if embeds:
                await self.core.update_channel(
                    self.interaction.guild.id,
                    self.interaction.channel.id,
                    {"message": {"content": self.content.value, "embeds": embeds}},
                )
            else:
                await self.core.update_channel(
                    self.interaction.guild.id,
                    self.interaction.channel.id,
                    {"message": {"content": self.content.value}},
                )
        except Exception as e:
            await interaction.followup.send(
                "",
                embed=discord.Embed(
                    title=f"#{self.interaction.channel.name} | Error",
                    description=f"Error updating channel: {e}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
                view=view,
            )
            return

        # Get new config
        config = await self.core.get_channel(
            self.interaction.guild.id, self.interaction.channel.id
        )

        # Write the content to the channel
        try:
            await self.core.write_to_channel(config)
        except Exception as e:
            await interaction.followup.send(
                "",
                embed=discord.Embed(
                    title=f"#{self.interaction.channel.name} | Error",
                    description=f"Error writing to channel: {e}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
                view=view,
            )
            return

        # Return to main menu
        await interaction.followup.send(
            "",
            embed=discord.Embed(
                title=f"#{self.interaction.channel.name} | Success",
                description="Channel updated successfully.\n\n"
                + self.core._channel_summary(config),
                color=discord.Color.green(),
            ),
            view=view,
            ephemeral=True,
        )


# Core cog
class InformationChannels(commands.Cog):
    """A cog for managing and serving information channels in the Jerry bot."""

    def __init__(self, bot: squidcore.Bot):
        self.bot = bot
        self.logger = logging.getLogger("jerry.information_channels")

        self.information_channels_collection = None

    async def cog_load(self):
        """Load the information channels."""

        if self.bot.memory.mongo_db is None:
            self.logger.error(
                "MongoDB is not connected. Cannot initialize information channels."
            )
            return

        existing_collections = await self.bot.memory.mongo_db.list_collection_names()
        if InformationChannelsMongo.COLLECTION_NAME not in existing_collections:
            self.logger.info("Creating information channels collection in MongoDB.")
            await self.bot.memory.mongo_db.create_collection(
                InformationChannelsMongo.COLLECTION_NAME,
                validator=InformationChannelsMongo.SCHEMA,
                validationLevel="strict",  # optional: strict (default) or moderate
                validationAction="error",  # optional: error (default) or warn
            )
            await self.bot.memory.mongo_db[
                InformationChannelsMongo.COLLECTION_NAME
            ].create_index(
                InformationChannelsMongo.COLLECTION_SEARCH_INDEX,
                name="information_search_index",
            )
        self.information_channels_collection = self.bot.memory.mongo_db[
            InformationChannelsMongo.COLLECTION_NAME
        ]

    async def cog_status(self):
        return "Ready" if self.information_channels_collection else "Not Ready"

    async def get_channel(self, guild: int, channel: int) -> dict:
        """Get information channel by guild and channel ID."""
        entry = await self.information_channels_collection.find_one(
            {"server_id": guild, "channel_id": channel}
        )
        if entry is None:
            raise InformationChannelErrors.InformationChannelNotFound(
                "No matching channel found in database."
            )

        return entry

    async def update_channel(self, guild: int, channel: int, updates: dict):
        """Update information channel by guild and channel ID."""
        result = await self.information_channels_collection.update_one(
            {"server_id": guild, "channel_id": channel}, {"$set": updates}
        )
        if result.modified_count == 0:
            await self.get_channel(
                guild, channel
            )  # This will raise an error if the channel doesn't exist

    async def delete_channel(self, guild: int, channel: int):
        """Delete information channel by guild and channel ID."""
        result = await self.information_channels_collection.delete_one(
            {"server_id": guild, "channel_id": channel}
        )
        if result.deleted_count == 0:
            raise InformationChannelErrors.InformationChannelNotFound(
                "No matching channel found in database."
            )

    async def write_to_channel(self, config: dict):
        """Write content to an information channel."""
        try:
            channel = self.bot.get_guild(config["server_id"]).get_channel(
                config["channel_id"]
            )
            if not channel:
                raise KeyError

        except KeyError:
            self.logger.error(f"Channel not found: {config['channel_id']}")
            raise InformationChannelErrors.InformationChannelNotFound(
                f"Channel not found: {config['channel_id']}"
            )

        if not config.get("message"):
            raise InformationChannelErrors.InformationInvalidConfig(
                f"Invalid message configuration for channel: {config['channel_id']}"
            )
        if not config["message"].get("content") and not config["message"].get("embeds"):
            raise InformationChannelErrors.InformationInvalidConfig(
                f"No content to send for channel: {config['channel_id']}"
            )

        # Purge channel
        await channel.purge(limit=100, check=lambda m: m.author == self.bot.user)

        # Write content to channel
        embeds = []
        for embed in config["message"].get("embeds", []):
            embeds.append(discord.Embed.from_dict(embed))

        await channel.send(
            content=config["message"].get("content", ""),
            embeds=embeds,
        )

    async def interactive_delete_channel(self, interaction: discord.Interaction):
        """Delete an information channel interactively."""
        channel = interaction.channel
        title = f"#{channel.name} | Deleted"

        # Defer the response
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.HTTPException:
            pass

        # Delete the information channel from the database
        try:
            await self.delete_channel(interaction.guild.id, channel.id)
        except Exception as e:
            await interaction.followup.send(
                embed=discord.Embed(
                    title=title,
                    description="Failed to delete information channel. ❌",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            self.logger.error(f"Failed to delete information channel: {e}")
            return

        await interaction.followup.send(
            embed=discord.Embed(
                title=title,
                description="Information channel deleted successfully. ✅",
                color=discord.Color.green(),
            ),
            ephemeral=True,
        )

    def _channel_summary(self, config: dict) -> str:
        """Generate a summary of the information channel configuration."""
        message_config = config.get("message", {})
        message = ""
        tip = False
        if message_config.get("content") or message_config.get("embeds", []):
            message += f"Content added ✅\n"
        else:
            message += f"No content added ❌\n"
            tip = True

        if config.get("webhook", {}).get("use"):
            if config["webhook"].get("username") and config["webhook"].get("image_url"):
                message += f"Webhook configured ✅\n"
            else:
                message += f"Webhook not fully configured ❌\n"
        else:
            message += f"Bot sender configured ✅\n"

        if tip:
            message += f'\nTip: Use "Update" to add content.'
        return message.strip() or "No configuration set."

    async def interactive_create_channel(self, interaction: discord.Interaction):
        """Create an information channel interactively."""
        channel = interaction.channel
        title = f"#{channel.name} | Creating"

        # Defer the response
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.HTTPException:
            pass

        # Create the information channel in the database
        try:
            await self.information_channels_collection.insert_one(
                {
                    "server_id": interaction.guild.id,
                    "channel_id": channel.id,
                    "webhook": {
                        "use": False,
                    },
                }
            )
            info_channel = await self.get_channel(interaction.guild.id, channel.id)
        except Exception as e:
            await interaction.followup.send(
                embed=discord.Embed(
                    title=title,
                    description="Failed to create information channel.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            self.logger.error(f"Failed to create information channel: {e}")
            return

        # await interaction.followup.send(
        #     embed=discord.Embed(
        #         # title=title,
        #         description="Information channel created successfully. ✅",
        #         color=discord.Color.green(),
        #     ),
        #     ephemeral=True,
        # )

        return await self.interactive_main_menu(
            interaction, action="menu", config=info_channel
        )

    async def interactive_main_menu(
        self, interaction: discord.Interaction, config: dict, action: str = "menu"
    ):
        """Display the main menu for information channels."""
        view = MainMenuView(interaction, self, do_action=action, config=config)
        await interaction.followup.send(
            embed=discord.Embed(
                title=f"#{interaction.channel.name} | Summary",
                description=(
                    self._channel_summary(config)
                    if config
                    else "No information channel configured."
                ),
                color=discord.Color.blue(),
            ),
            view=view,
        )

    @app_commands.command(name="information_channel")
    # @app_commands.describe(
    #     action="Shortcut for the action to perform",
    # )
    # @app_commands.choices(
    #     action=[
    #         app_commands.Choice(name="Interactive Menu (Default)", value="menu"),
    #         app_commands.Choice(name="Update", value="update"),
    #         app_commands.Choice(name="Config", value="config"),
    #     ]
    # )
    @app_commands.guild_install()
    @app_commands.guild_only()
    async def information_channel(
        self,
        interaction: discord.Interaction,
        # action: str = "menu",
    ):
        """Create or manage an information channel. Assumes the current channel is the target."""
        if not await self.bot.permissions.interaction_check(interaction, squidcore.PermissionLevel.APPROVED): # Need to be approved by bot
            return
        
        await interaction.response.defer(ephemeral=True)

        action = "menu"  # Default action
    
        # Channel
        channel = interaction.channel
        title = f"#{channel.name}"

        # Verify Permission (manage messages, per-channel)
        if not channel.permissions_for(interaction.guild.me).manage_messages:
            await interaction.followup.send(
                "",
                embed=discord.Embed(
                    description="I do not have permission to manage messages in this channel. ❌",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # Get Information Channel
        try:
            info_channel = await self.get_channel(interaction.guild.id, channel.id)
        except InformationChannelErrors.InformationChannelNotFound:
            # Create a new information channel
            create_confirmation = ConfirmationView(
                interaction=interaction, yes=self.interactive_create_channel
            )
            await interaction.followup.send(
                "",
                embed=discord.Embed(
                    title=f"{title} | Create",
                    description="Create information channel here?",
                    color=discord.Color.green(),
                ),
                view=create_confirmation,
            )
            return

        # Manage Existing Information Channel
        await self.interactive_main_menu(
            interaction, action="menu", config=info_channel
        )
