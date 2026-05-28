"""Main view for the Auto Reply plugin."""

import discord
from typing import Callable, Optional

from ..ar import AutoReply
from .constants import CLI_HELP_MSG, HELP_MSG
from .common import send_error

from .editor import AutoReplyRuleModal
from .search import AutoReplySearchUI


class AutoReplyMainUI(discord.ui.LayoutView):
    """Main UI for the Auto Reply plugin."""

    def __init__(
        self,
        auto_reply: AutoReply,
        message: Optional[discord.Message] = None,
        message_method: Optional[Callable] = None,
    ) -> None:
        super().__init__(timeout=None)
        if message is None and message_method is None:
            raise ValueError("Either message or message_method must be provided.")
        self.ar = auto_reply
        self.message = message
        self.message_method = message_method

    def _button(
        self, label: str, style: discord.ButtonStyle, callback: Callable
    ) -> discord.ui.Button:
        btn = discord.ui.Button(label=label, style=style)
        btn.callback = callback
        return btn

    def generate_container(self) -> discord.ui.Container:
        container = discord.ui.Container()
        container.add_item(
            discord.ui.TextDisplay(
                (
                    "### Auto Reply Plugin\n"
                    "Manage your auto-reply rules and settings using the buttons below."
                )
            )
        )

        actions = discord.ui.ActionRow()
        actions.add_item(
            self._button(
                "Create Rule", discord.ButtonStyle.success, self.create_rule_cb
            )
        )
        actions.add_item(
            self._button("List Rules", discord.ButtonStyle.primary, self.list_cb)
        )
        actions.add_item(
            self._button("Reload All", discord.ButtonStyle.secondary, self.reload_cb)
        )
        actions.add_item(
            self._button("Help", discord.ButtonStyle.secondary, self.help_cb)
        )
        container.add_item(actions)

        container.add_item(discord.ui.TextDisplay("Search using `jerry ar <query>`."))
        return container

    async def render(self) -> None:
        self.container = self.generate_container()
        self.clear_items()
        self.add_item(self.container)
        if self.message:
            await self.message.edit(view=self)
        elif self.message_method:
            # message_method expects this view as its only parameter
            self.message = await self.message_method(view=self)

    async def reload_cb(self, interaction: discord.Interaction) -> None:
        """Callback to reload all auto-reply rules."""
        try:
            await interaction.response.defer(thinking=True)
            await self.ar.load_cache()
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Auto Reply",
                    description="All auto-reply rules have been reloaded.",
                    color=discord.Color.green(),
                ),
                ephemeral=True,
            )
        except Exception:
            self.ar.plugin.logger.exception("Error reloading auto-reply cache")
            await send_error(
                interaction,
                "Error",
                "Failed to reload auto-reply rules. Please try again.",
            )

    async def list_cb(self, interaction: discord.Interaction) -> None:
        """Callback to open the search modal (not implemented)."""
        try:
            ui = AutoReplySearchUI(auto_reply=self.ar, interaction=interaction)
            await ui.render()
        except Exception:
            self.ar.plugin.logger.exception("Error opening search modal")
            await send_error(
                interaction, "Error", "Failed to open search. Please try again."
            )

    async def create_rule_cb(self, interaction: discord.Interaction) -> None:
        """Callback to create a new rule (not implemented)."""
        try:
            modal = AutoReplyRuleModal(self.ar)
            await interaction.response.send_modal(modal)
        except Exception:
            self.ar.plugin.logger.exception("Error opening create rule modal")
            await send_error(
                interaction, "Error", "Failed to open rule creator. Please try again."
            )

    async def help_cb(self, interaction: discord.Interaction) -> None:
        """Callback to show help message."""
        try:
            view = discord.ui.LayoutView(timeout=None)
            container = discord.ui.Container()
            container.add_item(discord.ui.TextDisplay(content=HELP_MSG))
            container.add_item(
                discord.ui.ActionRow(
                    self._button(
                        "CLI Help", discord.ButtonStyle.secondary, self.cli_help_cb
                    )
                )
            )
            view.add_item(container)
            await interaction.response.send_message(view=view, ephemeral=True)
        except Exception:
            self.ar.plugin.logger.exception("Error showing help message")
            await send_error(
                interaction, "Error", "Failed to display help. Please try again."
            )

    async def cli_help_cb(self, interaction: discord.Interaction) -> None:
        """Callback to show CLI help message."""
        try:
            ui = AutoReplyCLIHelpUI(interaction=interaction)
            await ui.render()
        except Exception:
            self.ar.plugin.logger.exception("Error showing CLI help message")
            await send_error(
                interaction, "Error", "Failed to display CLI help. Please try again."
            )


class AutoReplyCLIHelpUI(discord.ui.LayoutView):
    """UI for displaying Auto Reply CLI command help."""

    def __init__(
        self,
        message_method: Callable | None = None,
        interaction: discord.Interaction | None = None,
    ):
        super().__init__(timeout=None)
        self.message_method = message_method
        self.interaction = interaction

    def generate_container(self) -> discord.ui.Container:
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(content=CLI_HELP_MSG))
        return container

    async def render(self) -> None:
        self.container = self.generate_container()
        self.clear_items()
        self.add_item(self.container)
        if self.interaction:
            if self.interaction.response.is_done():
                await self.interaction.edit_original_response(view=self)
            else:
                await self.interaction.response.send_message(view=self, ephemeral=True)
        elif self.message_method:
            await self.message_method(view=self)
