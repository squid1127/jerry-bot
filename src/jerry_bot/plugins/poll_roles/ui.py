"""UI Elements for PollRoles Plugin."""

from .models import Poll
from .manager_protocol import PollRoleManager

from discord import ui
import discord
from enum import Enum


class MessageContainer(ui.LayoutView):
    """A container for the poll message, allowing for interaction with the poll."""

    def __init__(self, content: str, color: discord.Color):
        super().__init__(timeout=None)
        self.content = content
        self.color = color

        self.text = ui.TextDisplay(content)
        self.container = ui.Container(accent_color=color)
        self.container.add_item(self.text)
        self.add_item(self.container)


async def generic_error_view(error_message: str, interaction: discord.Interaction):
    """Create a generic error view to display an error message."""
    view = MessageContainer(error_message, discord.Color.red())

    if interaction.response.is_done():
        await interaction.followup.send(view=view, ephemeral=True)
        return

    await interaction.response.send_message(view=view, ephemeral=True)


class PollManagerViewState(Enum):
    """An enum representing the different states of the PollManagerView."""

    MAIN_MENU = 1
    MAPPING = 2
    UPDATING_ROLES = 3
    TIMED_OUT = 4
    ERROR = 5


class PollManagerView(ui.LayoutView):
    """A view for managing a poll, allowing users to create, edit, and delete polls entries."""

    def __init__(
        self,
        interaction: discord.Interaction,
        manager: PollRoleManager,
        poll: Poll | None,
        message: discord.Message,
    ):
        super().__init__(timeout=None)

        if not interaction.guild:
            raise ValueError("Interaction must be in a guild channel.")
        self.interaction = interaction
        self.manager = manager
        self.poll = poll
        self.message = message
        if not message or not message.poll:
            raise ValueError("Message must contain a poll.")
        self.state = (
            PollManagerViewState.MAIN_MENU if poll else PollManagerViewState.MAPPING
        )

        self.mapping_inputs: dict[str, ui.RoleSelect] = {}
        self.mapping_updates: dict[str, int | None] = {}

        self.error_message: str | None = None

    async def render(self):
        """Render the view based on the current state of the poll."""
        if not await self.refresh_message():
            return  # If refreshing the message failed, we can't continue rendering

        # Clear existing items
        self.clear_items()

        container = ui.Container(accent_color=discord.Color.blue())

        if self.state == PollManagerViewState.MAIN_MENU and self.poll:
            await self.render_main_menu(container)

        elif self.state == PollManagerViewState.MAPPING:
            await self.render_mapping_view(container)

        elif self.state == PollManagerViewState.UPDATING_ROLES:
            container.add_item(
                ui.TextDisplay(
                    "### Updating\nUpdating roles based on current votes. Please wait..."
                )
            )

        elif self.state == PollManagerViewState.TIMED_OUT:
            container.add_item(
                ui.TextDisplay(
                    "This poll management session has timed out. Please run the command again to manage the poll."
                )
            )

        elif self.state == PollManagerViewState.ERROR:
            container.add_item(
                ui.TextDisplay(self.error_message or "An unknown error occurred.")
            )
        else:
            container.add_item(ui.TextDisplay("Invalid state or no poll found."))

        self.add_item(container)

        if self.interaction.response.is_done():
            await self.interaction.edit_original_response(view=self)
        else:
            await self.interaction.response.send_message(view=self, ephemeral=True)

    async def update_roles(self):
        if not self.poll:
            return

        self.state = PollManagerViewState.UPDATING_ROLES
        await self.render()

        await self.manager.process_role_updates(self.poll, self.dc_poll, user_id=None)

        # Check if the poll's active status needs to be updated based on the current state of the poll
        if self.poll.active == self.dc_poll.is_finalised():
            if self.dc_poll.is_finalised():
                await self.manager.close_poll(
                    self.poll.guild_id, self.poll.channel_id, self.poll.message_id
                )
            else:
                self.poll.active = True
                await self.poll.save()
                self.manager.add_poll(self.poll)

        self.state = PollManagerViewState.MAIN_MENU
        await self.render()

    async def error(self, error_message: str):
        """Set the view to the error state with the given error message."""
        self.error_message = error_message
        self.state = PollManagerViewState.ERROR
        await self.render()

    async def refresh_message(self) -> bool:
        """Refresh the poll data from the message to ensure we have the latest information."""

        # Refetch discord message to ensure we have the latest poll data, as it may have changed since the view was created
        try:
            self.message = await self.message.channel.fetch_message(self.message.id)
            if not self.message.poll:
                await self.error(
                    "The poll data for this message could not be found. It may have been deleted."
                )
                return False
        except discord.NotFound:
            await self.error(
                "The message for this poll could not be found. It may have been deleted."
            )
            return False
        except discord.Forbidden:
            await self.error(
                "I do not have permission to access the message for this poll. Please ensure I have permission to view the channel and read message history."
            )
            return False
        except Exception as e:
            await self.error(f"An error occurred while fetching the poll message: {e}")
            return False
        return True

    def mapping_as_string(self) -> str:
        """Convert the poll's option-role mappings to a human-readable string."""
        if not self.poll or not self.poll.mapping:
            return "No mappings found."

        mapping: dict[str, int] = self.poll.mapping

        if not isinstance(mapping, dict):
            return "Invalid mapping format."

        lines = []
        for option, role_id in mapping.items():
            role_mention = f"<@&{role_id}>" if role_id else "No role"
            lines.append(f"- {option}: {role_mention}")

        return "\n".join(lines)

    async def render_main_menu(self, container: ui.Container):
        """Render the main menu view, showing the current mappings and options to edit them."""

        if not self.poll:
            container.add_item(
                ui.TextDisplay("No poll data found. Please set up the poll mappings.")
            )
            return

        content = f"### PollRoles - {'*Active*' if self.poll.active else '*Inactive*'}\n\n**Mapping**:\n{self.mapping_as_string()}"

        if self.poll.active == self.dc_poll.is_finalised():
            content += "\n\n*Warning*: The poll's state is out of sync. This may be due to missed updates. Press 'Update Roles Now' to fix this. This can occur if the poll has just recently closed as the bot has not had time to run cleanup"
        elif not self.poll.active and self.dc_poll.is_finalised():
            content += "\n\n*Note*: This poll is already closed."
        elif not self.poll.live_mode:
            content += "\n\n*Tip*: Enable live updates to have roles update automatically when users vote. (They won't by default)"

        container.add_item(ui.TextDisplay(content))

        button_update = ui.Button(
            label="Update Roles Now", style=discord.ButtonStyle.success
        )
        button_update.callback = self.on_update_roles

        button_mapping = ui.Button(
            label="Edit Mappings", style=discord.ButtonStyle.primary
        )
        button_mapping.callback = self.on_edit_mappings

        button_toggle_live = ui.Button(
            label=f"{'Disable' if self.poll.live_mode else 'Enable'} Live Updates",
            style=discord.ButtonStyle.primary,
            disabled=not self.poll.active,  # Can't toggle live mode if poll is inactive
        )
        button_toggle_live.callback = self.on_toggle_live_mode

        button_refresh = ui.Button(label="Refresh", style=discord.ButtonStyle.secondary)
        button_refresh.callback = self.on_refresh_button

        container.add_item(
            ui.ActionRow(
                button_update, button_mapping, button_toggle_live, button_refresh
            )
        )

    async def render_mapping_view(self, container: ui.Container):
        """Render the mapping view, allowing users to edit the option-role mappings."""

        poll_options: dict[str, int | None] = {}
        mapping = (
            self.poll.mapping
            if self.poll and self.poll.mapping and isinstance(self.poll.mapping, dict)
            else {}
        )

        for option in self.dc_poll.answers:
            role_id = mapping.get(option)
            poll_options[option.text] = role_id

        container.add_item(
            ui.TextDisplay(
                f"### {'Edit' if self.poll else 'Create'} Poll Role Mappings\nSelect a role for each poll option."
            )
        )

        for index, (option_text, role_id) in enumerate(poll_options.items(), start=1):
            role = (
                self.interaction.guild.get_role(role_id)
                if role_id and self.interaction.guild
                else None
            )
            role_input = ui.RoleSelect(
                placeholder="Select a role (Optional)",
                required=False,
                default_values=[role] if role else [],
            )
            role_input.callback = lambda interaction, option_text=option_text, role_input=role_input: self.on_mapping_change(
                interaction, option_text, role_input
            )
            self.mapping_inputs[option_text] = role_input

            container.add_item(ui.TextDisplay(f"{index}. **{option_text}**"))
            container.add_item(ui.ActionRow(role_input))

        button_save = ui.Button(label="Save", style=discord.ButtonStyle.success)
        button_save.callback = self.on_save_mappings
        container.add_item(ui.ActionRow(button_save))

    async def on_edit_mappings(self, interaction: discord.Interaction):
        """Handle the Edit Mappings button click."""
        self.state = PollManagerViewState.MAPPING
        await interaction.response.defer(thinking=False)
        await self.render()

    async def on_toggle_live_mode(self, interaction: discord.Interaction):
        """Handle the Toggle Live Mode button click."""
        if not self.poll:
            await self.error(
                "No poll found to toggle live mode.",
            )
            return
        if not self.poll.active:
            await self.error("Cannot toggle live mode for an inactive poll.")
            return

        self.poll.live_mode = not self.poll.live_mode
        await self.poll.save()
        await interaction.response.defer(thinking=False)
        await self.render()

    async def on_update_roles(self, interaction: discord.Interaction):
        """Handle the Update Roles button click, processing role updates for all votes."""
        if not self.poll:
            await self.error("No poll found to update roles for.")
            return

        await interaction.response.defer(thinking=False)
        await self.update_roles()

    async def on_refresh_button(self, interaction: discord.Interaction):
        """Handle the Refresh button click, re-rendering the view to reflect any changes."""
        await interaction.response.defer(thinking=False)
        await self.render()

    async def on_mapping_change(
        self,
        interaction: discord.Interaction,
        option_text: str,
        role_input: ui.RoleSelect,
    ):
        """Handle changes to the option-role mappings."""
        await interaction.response.defer(thinking=False)
        selected_role = role_input.values[0] if role_input.values else None
        self.mapping_updates[option_text] = selected_role.id if selected_role else None

    async def on_save_mappings(self, interaction: discord.Interaction):
        """Handle the Save button click, saving the updated mappings to the database."""
        await interaction.response.defer(thinking=False)

        if not self.poll:
            self.poll = Poll(
                guild_id=self.interaction.guild_id,
                channel_id=self.interaction.channel_id,
                message_id=self.message.id,
                mapping={},
                active=not self.dc_poll.is_finalised(),
                expire_by=(
                    self.dc_poll.expires_at
                    if self.dc_poll.expires_at and not self.dc_poll.is_finalised()
                    else None
                ),
            )

        for option_text, role_id in self.mapping_updates.items():
            self.poll.mapping[option_text] = role_id

        try:
            await self.poll.save()

            # Clear updates and update roles based on the new mappings
            self.mapping_updates.clear()

            await self.update_roles()

        except Exception as e:
            await self.error(f"An error occurred while saving the mappings: {e}")

    @property
    def dc_poll(self):
        """Get the latest poll data from the message."""
        if not self.message or not self.message.poll:
            raise ValueError("Message must contain a poll.")
        return self.message.poll