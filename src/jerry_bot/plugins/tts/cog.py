"""Cog for the Text-to-Speech plugin."""

from pathlib import Path
from urllib import response

from squid_core import PluginCog, Plugin
from .client import TTSSocketClient
from .models.request import TTSRequest, TTSResponse
from .models.config import TTSPluginConfig

import asyncio

from discord.ext import commands
import discord
from discord import app_commands
from uuid import uuid4

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


        command = app_commands.Command(
            name="tts",
            description="[TTS] Generate TTS audio from text.",
            callback=self.tts_command,
            allowed_contexts=app_commands.AppCommandContext(
                guild=True,
                dm_channel=True,
            ),
        )
        app_commands.describe(text="The text to convert to speech.",
                              voice="The voice to use for TTS. If not specified, the default voice will be used.")(command)
        choices = [app_commands.Choice(name=v.name, value=v.name) for v in self.config.voices]
        app_commands.choices(voice=choices)(command)
        self.fw.bot.tree.add_command(command)

    async def tts_command(self, interaction: discord.Interaction, text: str, voice: str | None = None):
        """Slash command to generate TTS audio from text."""
        await interaction.response.defer(thinking=True)
        
        if voice is None:
            voice_object = self.config.default_voice
        else:
            voice_object = next((v for v in self.config.voices if v.name == voice), None)
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
                await message(
                    interaction,
                    "Failed to generate TTS audio.",
                    error=True
                )

