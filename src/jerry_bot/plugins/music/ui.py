"""Discord UI components for the music plugin."""

import asyncio
from discord import ui
import discord

from .player import GuildMusicPlayer
from .models.enums import PlaybackState
from .models.db import MusicTrack

LISTEN_EVENTS = {"add_track", "add_playlist", "track_start", "stop", "pause", "resume"}


class MusicControlView(ui.LayoutView):
    """A Discord UI view for music playback controls."""

    def __init__(
        self,
        player: GuildMusicPlayer,
        context: discord.Interaction | discord.Message,
        timeout: float | None = 300.0,
    ) -> None:

        self.message: discord.Message | None = None
        self.interaction: discord.Interaction | None = None

        if isinstance(context, discord.Interaction):
            self.interaction = context
        elif isinstance(context, discord.Message):
            self.message = context
        else:
            raise TypeError("context must be either Interaction or Message")

        super().__init__(timeout=timeout)
        self.player = player
        self.alive = True

        player.subscribe(self._on_player_event)

    def _custom_button_id(self, action: str) -> str:
        """Generate a custom button ID for a given action."""
        return f"plugin:music:{self.player.guild.id}:{action}"

    def _button_constructor(self, action: str, emoji: str) -> ui.Button:
        """Construct a button for a given action."""
        button = ui.Button(emoji=emoji, custom_id=self._custom_button_id(action))
        button.callback = lambda inter: self.handle_button(inter, action)

        return button

    def build_container(self) -> ui.Container:
        """Build the container for the music control buttons."""
        container = ui.Container(accent_color=discord.Color.blurple())

        title = f"**{(self.player.channel.mention + ' - ') if self.player.channel else ''}{self.player.state.name.title()}**"
        container.add_item(ui.TextDisplay(content=title))

        container.add_item(ui.Separator())

        if self.player.state in {PlaybackState.PLAYING, PlaybackState.PAUSED}:

            track = self.player.current_track
            track_info = f"**{track.title}**" if track.title else "*Unknown*"

            if track.artists:
                track_info += "\nby " + ", ".join(track.artists)
            if track.album:
                track_info += f"\nfrom *{track.album}*"

            container.add_item(ui.TextDisplay(content=track_info))

        else:
            container.add_item(
                ui.TextDisplay(content="Use `/music-queue` to start playback.")
            )

        if self.alive and self.player.state != PlaybackState.STOPPED:
            # container.add_item(ui.Separator())
            controls = ui.ActionRow()

            controls.add_item(
                self._button_constructor(
                    "toggle_playback",
                    "⏸️" if self.player.state == PlaybackState.PLAYING else "▶️",
                )
            )
            controls.add_item(self._button_constructor("skip_track", "⏭️"))
            controls.add_item(self._button_constructor("stop_playback", "⏹️"))
            controls.add_item(self._button_constructor("show_queue", "📃"))
            container.add_item(controls)

        return container
    
    async def _queue_text(self, char_limit: int = 1000) -> str:
        """Generate the text representation of the music queue."""
        lines = []
        total_length = 0
        queue_size = 0
        
        queue = await self.player.queue.list()

        for idx, track in enumerate(queue):
            line = f"{idx + 1}. {track.title or 'Unknown Title'}"
            if track.artists:
                line += f" - {', '.join(track.artists)}"
            line += "\n"

            line_length = len(line)
            if total_length + line_length > char_limit:
                lines.append(f"...and {len(queue) - queue_size} more tracks.")
                break

            lines.append(line)
            total_length += line_length
            queue_size += 1

        if not lines:
            return "*The queue is empty.*"

        return "".join(lines)
    
    async def queue_container(self) -> ui.Container:
        """Build the container for the music queue display."""
        container = ui.Container(accent_color=discord.Color.blurple())
        container.add_item(ui.TextDisplay(content="**Music Queue**"))
        container.add_item(ui.Separator())
        queue_text = await self._queue_text()
        container.add_item(ui.TextDisplay(content=queue_text))
        
        return container

    async def handle_button(
        self, interaction: discord.Interaction, action: str
    ) -> None:
        """Handle button interactions."""
        if not self.alive:
            await interaction.response.send_message(
                "This music control interface is no longer active.", ephemeral=True
            )
            return
        elif interaction.user.voice is None or interaction.user.voice.channel is None:
            await interaction.response.send_message(
                "You must be in a voice channel to use these controls.",
                ephemeral=True,
            )
            return
        elif (
            self.player.channel is not None
            and interaction.user.voice
            and interaction.user.voice.channel != self.player.channel
        ):
            await interaction.response.send_message(
                "You must be in the same voice channel as the bot to use these controls.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=False)
        if action == "toggle_playback":
            if self.player.state == PlaybackState.PLAYING:
                await self.player.pause()
            elif self.player.state == PlaybackState.PAUSED:
                await self.player.resume()
        elif action == "skip_track":
            await self.player.skip()
        elif action == "stop_playback":
            await self.player.stop()
        elif action == "show_queue":
            queue_view = ui.LayoutView()
            queue_view.add_item(await self.queue_container())
            await interaction.followup.send("", view=queue_view, ephemeral=True)
            
    async def _on_player_event(self, event: str) -> None:
        """Handle player events to update the UI."""
        if event in LISTEN_EVENTS and self.alive:
            await self.render()

    async def render(self) -> None:
        """Render the view with updated content."""
        self.clear_items()
        self.add_item(self.build_container())

        if self.message:
            await self.message.edit(view=self)
        elif self.interaction:
            if self.interaction.response.is_done():
                await self.interaction.edit_original_response(view=self)
            else:
                await self.interaction.response.edit_message(view=self)

    async def on_timeout(self) -> None:
        """Handle the timeout of the view."""
        self.alive = False
        self.stop()
