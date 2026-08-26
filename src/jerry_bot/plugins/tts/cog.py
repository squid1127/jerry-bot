"""Cog for the Text-to-Speech plugin."""

from pathlib import Path
from urllib import response

from squid_core import PluginCog, Plugin
from squid_core.decorators import DiscordEventListener
from .socket import TTSSocketClient
from .models.request import TTSRequest, TTSResponse
from .models.config import TTSPluginConfig, TTSVoiceConfig
from .listener import TTSListener
from .voice import TTSVoiceClient

import asyncio

from discord.ext import commands
import discord
from discord import app_commands
from uuid import uuid4

GUILD_ONLY_MESSAGE = "This command can only be used in a guild."


async def message(interaction: discord.Interaction, message: str, error: bool = False):
    """Send a message to the user."""
    embed = discord.Embed(
        description=message,
    )
    if error:
        embed.color = discord.Color.red()
    else:
        embed.color = discord.Color.green()
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    await interaction.response.send_message(embed=embed, ephemeral=True)


class TTSCog(PluginCog):
    """Cog for the Text-to-Speech plugin."""

    def __init__(
        self,
        plugin: Plugin,
        client: TTSSocketClient,
        output_dir: Path,
        config: TTSPluginConfig,
    ):
        super().__init__(plugin)
        self.socket_client: TTSSocketClient = client
        self.output_dir: Path = output_dir
        self._lock = asyncio.Lock()
        self.config: TTSPluginConfig = config

        self.listeners: dict[tuple[int, int], TTSListener] = (
            {}
        )  # Key: (guild_id, user_id), Value: TTSListener
        self.voice_clients: dict[int, TTSVoiceClient] = (
            {}
        )  # Key: guild_id, Value: TTSVoiceClient

        generate_command = app_commands.Command(
            name="tts-generate",
            description="[TTS] Generate TTS audio from text.",
            callback=self.tts_generate_command,
            allowed_contexts=app_commands.AppCommandContext(
                guild=True,
                dm_channel=True,
            ),
        )
        app_commands.describe(
            text="The text to convert to speech.",
            voice="The voice to use for TTS. If not specified, the default voice will be used.",
        )(generate_command)

        choices = [
            app_commands.Choice(name=v.name, value=v.name) for v in self.config.voices
        ]
        app_commands.choices(voice=choices)(generate_command)

        listen_command = app_commands.Command(
            name="tts-listen",
            description="[TTS] Listen to a user's messages and convert them to speech.",
            callback=self.tts_listen_command,
            allowed_contexts=app_commands.AppCommandContext(
                guild=True,
                dm_channel=False,
            ),
        )
        app_commands.describe(voice="The voice to use for TTS.")(listen_command)
        app_commands.choices(voice=choices)(listen_command)
        
        listen_for_command = app_commands.Command(
            name="tts-listen-for",
            description="[TTS] Listen to another user's messages and convert them to speech.",
            callback=self.tts_listen_for_command,
            allowed_contexts=app_commands.AppCommandContext(
                guild=True,
                dm_channel=False,
            ),
        )
        app_commands.describe(
            member="The user whose messages should be converted to speech.",
            voice="The voice to use for TTS.",
        )(listen_for_command)
        app_commands.choices(voice=choices)(listen_for_command)
        app_commands.default_permissions(administrator=True)(listen_for_command)
        
        self.fw.bot.tree.add_command(generate_command)
        self.fw.bot.tree.add_command(listen_command)
        self.fw.bot.tree.add_command(listen_for_command)

    async def tts_generate_command(
        self, interaction: discord.Interaction, text: str, voice: str | None = None
    ):
        """Slash command to generate TTS audio from text."""
        await interaction.response.defer(thinking=True)

        if voice is None:
            voice_object = self.config.default_voice
        else:
            voice_object = next(
                (v for v in self.config.voices if v.name == voice), None
            )
        if voice_object is None:
            await message(
                interaction,
                "No default voice configuration found. Please set a default voice in the configuration.",
            )
            return

        async with self._lock:
            request = TTSRequest.from_voice_config(text, voice_object)
            response = await self.socket_client.generate_tts(request)

            if response.filename and (self.output_dir / response.filename).exists():
                await interaction.followup.send(
                    file=discord.File(
                        fp=self.output_dir / response.filename,
                        filename=f"tts{(self.output_dir / response.filename).suffix}",
                    )
                )
            else:
                await message(interaction, "Failed to generate TTS audio.", error=True)

    async def tts_listen_command(self, interaction: discord.Interaction, voice: str):
        """Slash command to listen to a user's messages and convert them to speech."""
        await interaction.response.defer(thinking=True)

        member = interaction.user
        if not isinstance(member, discord.Member) or interaction.guild is None:
            await message(interaction, GUILD_ONLY_MESSAGE, error=True)
            return
        if member.bot:
            await message(interaction, "Cannot listen to bot users.", error=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await message(
                interaction,
                "This command can only be used in a text channel.",
                error=True,
            )
            return

        try:
            self.create_or_update_listener(member, voice, interaction.channel)
            await message(
                interaction,
                f"Now listening in {interaction.channel.mention} with voice '{voice}'.",
            )
        except ValueError as e:
            await message(interaction, str(e), error=True)
            return


    async def tts_listen_for_command(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        voice: str,
    ):
        """Start listening to another user's messages on their behalf."""
        await interaction.response.defer(thinking=True)

        if not isinstance(interaction.channel, discord.TextChannel):
            await message(
                interaction,
                "This command can only be used in a text channel.",
                error=True,
            )
            return

        try:
            self.create_or_update_listener(member, voice, interaction.channel)
            await message(
                interaction,
                f"Now listening to {member.mention} in {interaction.channel.mention} with voice '{voice}'.",
            )
        except ValueError as e:
            await message(interaction, str(e), error=True)

    @app_commands.command(
        name="tts-stop-for",
        description="[TTS] Stop listening to another user's messages",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        member="The user whose messages should be converted to speech.",
    )
    async def tts_stop_for_command(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        """Stop listening to another user's messages on their behalf."""
        await interaction.response.defer(thinking=True)

        if interaction.guild is None:
            await message(interaction, GUILD_ONLY_MESSAGE, error=True)
            return

        listener = self.listeners.pop((interaction.guild.id, member.id), None)
        if listener:
            await message(interaction, f"Stopped listening to {member.mention}.")
        else:
            await message(
                interaction,
                f"No active listener found for {member.mention}.",
                error=True,
            )

    @app_commands.command(
        name="tts-stop", description="[TTS] Stop listening to a user's messages."
    )
    async def tts_stop_command(self, interaction: discord.Interaction):
        """Slash command to stop listening to a user's messages."""
        await interaction.response.defer(thinking=True)

        if interaction.guild is None:
            await message(interaction, GUILD_ONLY_MESSAGE, error=True)
            return

        listener = self.listeners.pop((interaction.guild.id, interaction.user.id), None)
        if listener:
            await message(
                interaction, f"Stopped listening to {interaction.user.mention}."
            )
        else:
            await message(
                interaction,
                f"No active listener found for {interaction.user.mention}.",
                error=True,
            )

    def get_or_create_voice_client(self, guild: discord.Guild) -> TTSVoiceClient:
        """Get or create a TTSVoiceClient for a guild."""
        if guild.id not in self.voice_clients:
            self.voice_clients[guild.id] = TTSVoiceClient(
                guild, timeout=self.config.user_timeout
            )
        return self.voice_clients[guild.id]

    def create_or_update_listener(
        self, member: discord.Member, voice: str, listen_channel: discord.TextChannel
    ):
        """Create or update a TTSListener for a user in a guild."""
        voice_object = next((v for v in self.config.voices if v.name == voice), None)
        if voice_object is None:
            raise ValueError(f"Voice configuration '{voice}' not found.")

        listener = self.listeners.get((member.guild.id, member.id))
        if listener:
            # Update existing listener
            listener.voice_config = voice_object
            listener.listen_channel = listen_channel
        else:
            # Create a new listener
            listener = TTSListener(
                member=member,
                output_dir=self.output_dir,
                voice_config=voice_object,
                listen_channel=listen_channel,
                socket_client=self.socket_client,
                voice_client=self.get_or_create_voice_client(member.guild),
                logger=self.plugin.logger,
            )
            self.listeners[(member.guild.id, member.id)] = listener

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle incoming messages and enqueue TTS requests if applicable."""
        if message.guild is None:
            return  # Ignore messages from DMs

        listener = self.listeners.get((message.guild.id, message.author.id))
        if listener:
            self.plugin.logger.info(
                f"Handling message from {message.author} in guild {message.guild.name}"
            )
            await listener.handle_message(message)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Handle voice state updates to manage TTS listeners and voice clients."""

        guild_id = member.guild.id
        user_id = member.id

        # If the user leaves the voice channel, remove their listener
        if before.channel is not None and after.channel is None:
            listener = self.listeners.pop((guild_id, user_id), None)
            if listener:
                self.plugin.logger.info(
                    f"Removed TTS listener for {member} in guild {member.guild.name}"
                )

    async def stop(self):
        """Clean up resources when the cog is unloaded."""
        for voice_client in self.voice_clients.values():
            await voice_client.stop(from_timeout=False)
        self.voice_clients.clear()
