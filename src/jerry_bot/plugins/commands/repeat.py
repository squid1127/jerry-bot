import discord
from discord import app_commands
from discord.ext import tasks
from discord.utils import escape_markdown
from squid_core import Plugin, PluginCog
from squid_core.components.perms import PermissionLevel

DISCORD_COLORS: dict[str, discord.Colour] = {
    "default": discord.Colour.default(),
    "teal": discord.Colour.teal(),
    "green": discord.Colour.green(),
    "blue": discord.Colour.blue(),
    "purple": discord.Colour.purple(),
    "magenta": discord.Colour.magenta(),
    "gold": discord.Colour.gold(),
    "orange": discord.Colour.orange(),
    "red": discord.Colour.red(),
    "dark_teal": discord.Colour.dark_teal(),
    "dark_green": discord.Colour.dark_green(),
    "dark_blue": discord.Colour.dark_blue(),
    "dark_purple": discord.Colour.dark_purple(),
    "dark_magenta": discord.Colour.dark_magenta(),
    "dark_gold": discord.Colour.dark_gold(),
    "dark_orange": discord.Colour.dark_orange(),
    "dark_red": discord.Colour.dark_red(),
    "light_gray": discord.Colour.light_gray(),
    "dark_gray": discord.Colour.dark_gray(),
    "blurple": discord.Colour.blurple(),
    "og_blurple": discord.Colour.og_blurple(),
    "greyple": discord.Colour.greyple(),
    "brand_green": discord.Colour.brand_green(),
    "brand_red": discord.Colour.brand_red(),
    "fuchsia": discord.Colour.fuchsia(),
    "dark_theme": discord.Colour.dark_theme(),
    "yellow": discord.Colour.yellow(),
}

async def color_autocomplete(
    _interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    current = current.lower()
    matches = [name for name in DISCORD_COLORS if current in name]
    return [app_commands.Choice(name=name, value=name) for name in matches[:25]]


class RepeatLayout(discord.ui.LayoutView):
    def __init__(self, message: str, color: discord.Colour):
        super().__init__()
        container = discord.ui.Container(accent_colour=color)
        container.add_item(discord.ui.TextDisplay(message))
        self.add_item(container)


class StaticCommandRepeatCog(PluginCog):
    def __init__(self, plugin: Plugin):
        self.plugin: Plugin = plugin
        self.bot = plugin.fw.bot
        self.logger = plugin.logger
        self.perms = plugin.fw.perms
        
        self.active_loops: dict[int, tasks.Loop] = {}

    @app_commands.command(name="repeat-start", description="Repeats a message in this channel")
    @app_commands.describe(message="Message to repeat", interval="Repetition interval (minutes)", color="Color of embed")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.autocomplete(color=color_autocomplete)
    async def repeat(self, interaction: discord.Interaction, message: str, interval: int, color: str = "blurple"):
        if not await self.check_permissions(interaction):
            return

        resolved_color = DISCORD_COLORS.get(color.lower())
        if resolved_color is None:
            return await interaction.response.send_message(
                f"Unknown color `{color}`. Pick one from the list.", ephemeral=True
            )
        if interval <= 0:
            return await interaction.response.send_message(
                "Interval must be positive and nonzero.", ephemeral=True
            )

        channel_id = interaction.channel.id

        if channel_id in self.active_loops:
            self.active_loops[channel_id].cancel()

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            @tasks.loop(minutes=interval)
            async def sender():
                view = RepeatLayout(message, resolved_color)
                await interaction.channel.send(
                    view=view,
                    allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False),
                )

            @sender.error
            async def sender_error(exc: Exception):
                self.logger.error(f"Repeat loop failed in channel {channel_id}: {exc}")
                self.active_loops.pop(channel_id, None)

            sender.start()
            self.active_loops[channel_id] = sender

            await interaction.followup.send(
                f"Will send **{escape_markdown(message)}** every `{interval}` minute(s) in this channel."
            )
        except Exception as e:
            self.logger.error(f"Error in repeat-start command: {e}")
            await interaction.followup.send("An error occured.")

    async def check_permissions(self, interaction: discord.Interaction) -> bool:

        def error_message(description: str, title: str = "Error") -> discord.Embed:
            return discord.Embed(
                title=title + " 🚫", description=description, color=discord.Color.red()
            )

        if not (
            await self.plugin.fw.perms.interaction_check(
                interaction, required_level=PermissionLevel.MODERATOR
            )
        ):
            return False

        perms = interaction.channel.permissions_for(interaction.guild.me)
        if not perms.send_messages:
            await interaction.response.send_message(
                embed=error_message(
                    "I need the Send Messages permission in this channel to execute this command."
                ),
                ephemeral=True,
            )
            return False

        return True

    @app_commands.command(name="repeat-stop", description="Stop the repeating message in this channel")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True)
    async def stoprepeat(self, interaction: discord.Interaction):
        channel_id = interaction.channel.id
        loop = self.active_loops.pop(channel_id, None)
        if loop:
            loop.cancel()
            await interaction.response.send_message("Repetition stopped.", ephemeral=True)
        else:
            await interaction.response.send_message("No repeating messages.", ephemeral=True)