"""UI rendering logic for Gemini configuration menu"""

import discord
from discord import ui
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core import UIService
    from .menu import GeminiConfigMenu


class MenuRenderer:
    """Handles all UI rendering for the Gemini config menu"""

    def __init__(self, service: "UIService", menu: "GeminiConfigMenu"):
        self.service = service
        self.menu = menu

    async def render_error(self, error_message: str) -> ui.Container:
        """Renders an error display"""
        container = ui.Container(
            ui.TextDisplay(f"### Error\n{error_message}"),
            accent_color=discord.Color.red(),
        )

        button_back = ui.Button(
            label="Back to Overview", style=discord.ButtonStyle.gray
        )
        button_back.callback = self.menu.flow_back_to_overview
        container.add_item(ui.ActionRow(button_back))

        return container

    async def render_overview(self, channel_id: int, guild_id: int) -> ui.Container:
        """Renders the overview page with channel, profiles, and guild status"""
        container = ui.Container()
        channel_obj = await self.service.get_channel(channel_id, active=True)

        # Header
        channel = self.menu.interaction.channel
        title = f"## Gemini Config | {channel.mention if isinstance(channel, discord.TextChannel) else 'Unknown Channel'}\n### Overview"

        # Channel section
        await self._render_channel_section(container, channel_id, title)

        if channel_obj:
            # LLM Profiles section
            await self._render_llm_profiles_section(container, channel_id)

            # Guild section
            await self._render_guild_section(container, guild_id)

        return container

    async def _render_channel_section(
        self, container: ui.Container, channel_id: int, title: str
    ) -> None:
        """Renders the channel configuration section"""
        channel = await self.service.get_channel(channel_id, active=True)

        if channel is None:
            channel = await self.service.get_channel(channel_id, active=False)
            if channel is None:
                description = "\n❌ Channel not configured"
                label = "Configure"
            else:
                description = "\n❌ Channel is Inactive"
                label = "Re-Activate"

            container.add_item(ui.TextDisplay(title + description))
            button_activate = ui.Button(label=label, style=discord.ButtonStyle.green)
            button_activate.callback = self.menu.flow_activate_show
            container.add_item(ui.ActionRow(button_activate))
        else:
            summary = "\n✅ Channel is Active"

            if channel.mention_mode:
                summary += "\n💬 Mention mode enabled"
            if channel.override_system_prompt and channel.prompt:
                summary += "\n⚙️ Custom system prompt set"
            elif channel.override_system_prompt:
                summary += "\n❗ System prompt override enabled but no prompt set"
            elif channel.prompt:
                summary += "\n📝 Custom user prompt set"

            container.add_item(ui.TextDisplay(title + summary))

            button_deactivate = ui.Button(
                label="Deactivate", style=discord.ButtonStyle.red
            )
            button_deactivate.callback = self.menu.flow_deactivate

            button_edit = ui.Button(
                label="Edit Channel", style=discord.ButtonStyle.blurple
            )
            button_edit.callback = self.menu.flow_edit_show
            container.add_item(ui.ActionRow(button_edit, button_deactivate))

    async def _render_llm_profiles_section(
        self, container: ui.Container, channel_id: int
    ) -> None:
        """Renders the LLM profiles section"""
        
        container.add_item(ui.Separator())

        llm_profiles = await self.service.get_llm_profiles(channel_id)

        description = (
            "### LLM Profiles\n"
            if llm_profiles
            else "### LLM Profiles\nNone configured yet. (Required)"
        )

        if llm_profiles:
            for profile in llm_profiles:
                description += f"- {profile.model_name}"
                if self.menu.llm_profile_tab.value == 1:  # PROFILE
                    provider = self.service.get_provider(profile.provider_name)
                    description += f" - {provider.friendly_name if provider else profile.provider_name}"
                elif self.menu.llm_profile_tab.value == 2:  # FAIL_OVER
                    description += " - ?"
                description += "\n"

        container.add_item(ui.TextDisplay(description))

        button_add_profile = ui.Button(
            label="Add LLM Profile", style=discord.ButtonStyle.green
        )
        button_add_profile.callback = self.menu.flow_new_llm_profile_show

        button_tab_next = ui.Button(
            label=(
                "Fail-over Options"
                if self.menu.llm_profile_tab.value == 1
                else "Model Options"
            ),
            style=discord.ButtonStyle.gray,
        )
        button_tab_next.callback = self.menu.flow_tab_next
        container.add_item(ui.ActionRow(button_add_profile, button_tab_next))

        if llm_profiles:
            llm_profiles_select = ui.Select(
                placeholder=(
                    "Edit LLM Profiles"
                    if self.menu.llm_profile_tab.value == 1
                    else "Edit Fail-over Options"
                ),
                options=[
                    discord.SelectOption(
                        label=profile.model_name,
                        value=str(profile.id),
                        description=f"Edit the {profile.model_name} profile",
                    )
                    for profile in llm_profiles
                ],
                min_values=0,
                max_values=1,
            )
            llm_profiles_select.callback = self.menu.flow_edit_llm_profile_show
            container.add_item(ui.ActionRow(llm_profiles_select))

    async def _render_guild_section(
        self, container: ui.Container, guild_id: int
    ) -> None:
        """Renders the guild/server configuration section"""
        container.add_item(ui.Separator())

        guild = await self.service.get_guild(guild_id)
        description = "### Server\n"

        if guild:
            description += "✅ Server record exists\n"
            if guild.prompt:
                description += "⚙️ Custom system prompt set\n"
            if guild.trusted:
                description += "🔒 Server is Trusted (Ephemeral Mode Enabled)\n"
            else:
                description += "🔓 Server is Untrusted (Ephemeral Mode Disabled)\n"

            button_trust_guild = ui.Button(
                label="Trust Server" if not guild.trusted else "Untrust Server",
                style=(
                    discord.ButtonStyle.green
                    if not guild.trusted
                    else discord.ButtonStyle.red
                ),
            )
            button_trust_guild.callback = self.menu.flow_toggle_guild_trust
            container.add_item(ui.TextDisplay(description))
            container.add_item(ui.ActionRow(button_trust_guild))
        else:
            description += "❌ No server record (Required)\n"
            button_edit = ui.Button(
                label="Configure Server", style=discord.ButtonStyle.green
            )
            button_edit.callback = self.menu.flow_create_guild
            container.add_item(ui.TextDisplay(description))
            container.add_item(ui.ActionRow(button_edit))
