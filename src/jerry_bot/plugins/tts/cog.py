"""Cog for the Text-to-Speech plugin."""

import asyncio
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from squid_core import Plugin, PluginCog

from .listener import TTSListener
from .models.config import TTSPluginConfig
from .models.exceptions import TTSServerConnectionError
from .models.request import TTSRequest
from .socket import TTSSocketClient
from .voice import TTSVoiceClient

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


def guild_command(func):
    """Decorator to make an app command guild-only"""

    app_commands.allowed_installs(guilds=True, users=False)(func)
    app_commands.allowed_contexts(guilds=True, dms=False)(func)
    return func


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
        self._lock: asyncio.Lock = asyncio.Lock()
        self.config: TTSPluginConfig = config

        self.listeners: list[TTSListener] = []
        self.voice_clients: dict[int, TTSVoiceClient] = {}

        generate_command = app_commands.Command(
            name="tts-generate",
            description="[TTS] Generate TTS from text.",
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
            description="[TTS] Speak the messages sent by you (in this channel) in the voice channel you are in.",
            callback=self.tts_listen_command,
            allowed_contexts=app_commands.AppCommandContext(
                guild=True,
                dm_channel=False,
            ),
        )
        app_commands.describe(voice="The TTS voice to use.")(listen_command)
        app_commands.choices(voice=choices)(listen_command)

        listen_for_command = app_commands.Command(
            name="tts-listen-for",
            description="[TTS] Speak the messages sent by another user (in this channel) in the voice channel you are in",
            callback=self.tts_listen_for_command,
            allowed_contexts=app_commands.AppCommandContext(
                guild=True,
                dm_channel=False,
            ),
        )
        app_commands.describe(
            member="User whose messages should be read",
            voice="The TTS voice.",
        )(listen_for_command)
        app_commands.choices(voice=choices)(listen_for_command)
        # app_commands.default_permissions(administrator=True)(listen_for_command)

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
            try:
                request = TTSRequest.from_voice_config(text, voice_object)
                response = await self.socket_client.generate_tts(request)
            except TTSServerConnectionError:
                self.plugin.logger.exception(
                    "TTS service connection error running /tts-generate"
                )
                await message(interaction, message="TTS service failed.")
                return

            if response.filename and (self.output_dir / response.filename).exists():
                await interaction.followup.send(
                    file=discord.File(
                        fp=self.output_dir / response.filename,
                        filename=f"tts{Path(response.filename).suffix}",
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
            self.create_or_update_listener(member, member, voice, interaction.channel)
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
        if (
            not isinstance(interaction.user, discord.Member)
            or interaction.guild is None
        ):
            await message(interaction, GUILD_ONLY_MESSAGE, error=True)
            return

        try:
            self.create_or_update_listener(
                interaction.user, member, voice, interaction.channel
            )
            await message(
                interaction,
                f"Now listening to {member.mention} in {interaction.channel.mention} with voice '{voice}'.",
            )
        except ValueError as e:
            await message(interaction, str(e), error=True)

    @app_commands.command(
        name="tts", description="[TTS] See who's using Jerry TTS."
    )
    @guild_command
    async def tts_info_command(self, interaction: discord.Interaction):
        """Slash command to get information about the TTS plugin."""

        if interaction.guild is None:
            await message(interaction, GUILD_ONLY_MESSAGE, error=True)
            return

        owners: dict[discord.Member, list[TTSListener]] = {}
        for context in self.listeners:
            if context.guild == interaction.guild:
                owners.setdefault(context.owner, []).append(context)

        if not owners:
            content = "-# No listeners are active here."
        else:
            content = "-# Active instances:"
            for owner, listeners in owners.items():
                content += f"\n- {owner.mention}:"
                for listener in listeners:
                    if listener.target == owner:
                        content += f"\n  - Listening to themselves - {listener.listen_channel.mention}"
                    else:
                        content += f"\n  - {listener.target.mention} - {listener.listen_channel.mention}"

        if len(content) > 4096:
            content = content[:4093] + "..."

        embed = discord.Embed(
            title="Jerry TTS",
            description=content,
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(
        name="tts-stop", description="[TTS] Stop listening to a user's messages."
    )
    @guild_command
    async def tts_stop_command(self, interaction: discord.Interaction):
        """Slash command to stop listening to a user's messages."""
        await interaction.response.defer(thinking=True)

        if interaction.guild is None or not isinstance(
            interaction.user, discord.Member
        ):
            await message(interaction, GUILD_ONLY_MESSAGE, error=True)
            return

        to_pop = self._get_listeners(interaction.guild, owner=interaction.user)
        if not to_pop:
            await message(interaction, "No active listeners", error=True)
        targets = []
        for listener in to_pop:
            self.listeners.remove(listener)
            self.plugin.logger.info(
                f"Removed TTS listener(s) for {interaction.user}({listener.owner}) in guild {interaction.guild.name} because they left the voice channel."
            )
            targets.append(listener.target)

        await message(
            interaction,
            f"Stopped listening to {', '.join(['you' if t == interaction.user else t.mention for t in targets])}",
        )

    def get_or_create_voice_client(self, guild: discord.Guild) -> TTSVoiceClient:
        """Get or create a TTSVoiceClient for a guild."""
        if guild.id not in self.voice_clients:
            self.voice_clients[guild.id] = TTSVoiceClient(
                self.plugin.logger, guild, timeout=self.config.user_timeout
            )
        return self.voice_clients[guild.id]

    def create_or_update_listener(
        self,
        owner: discord.Member,
        target: discord.Member,
        voice: str,
        listen_channel: discord.TextChannel,
    ):
        """Create or update a TTSListener for a user in a guild."""
        voice_object = next((v for v in self.config.voices if v.name == voice), None)
        if voice_object is None:
            raise ValueError(f"Voice configuration '{voice}' not found.")

        listeners = self._get_listeners(
            listen_channel.guild, owner=owner, target=target
        )
        if listeners:
            # Update existing listener
            listener = listeners[0]
            listener.voice_config = voice_object
            listener.update_listen_channel(listen_channel)
        else:
            # Create a new listener
            listener = TTSListener(
                owner=owner,
                target=target,
                config=self.config,
                voice_config=voice_object,
                listen_channel=listen_channel,
                socket_client=self.socket_client,
                voice_client=self.get_or_create_voice_client(target.guild),
                logger=self.plugin.logger,
                base_path=self.plugin.get_working_directory(),
            )
            self.listeners.append(listener)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle incoming messages and enqueue TTS requests if applicable."""
        if message.guild is None:
            return  # Ignore messages from DMs

        for listener in self.listeners:
            # The listener already checks if the message applies to its context
            await listener.handle_message(message)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Handle voice state updates to manage TTS listeners and voice clients."""

        # If the user leaves the voice channel, remove their listener
        if before.channel is not None and after.channel is None:
            to_pop = self._get_listeners(before.channel.guild, owner=member)
            for listener in to_pop:
                self.listeners.remove(listener)
                self.plugin.logger.info(
                    f"Removed TTS listener(s) for {member}({listener.owner}) in guild {member.guild.name} because they left the voice channel."
                )

    async def stop(self):
        """Clean up resources when the cog is unloaded."""
        for voice_client in self.voice_clients.values():
            await voice_client.stop(from_timeout=False)
        self.voice_clients.clear()

    def _get_listeners(
        self,
        guild: discord.Guild,
        owner: discord.Member | None = None,
        target: discord.Member | None = None,
    ) -> list[TTSListener]:
        """Get the listener that matches the given id(s)"""
        return [
            l
            for l in self.listeners
            if l.guild == guild
            and (owner is None or l.owner == owner)
            and (target is None or l.target == target)
        ]
