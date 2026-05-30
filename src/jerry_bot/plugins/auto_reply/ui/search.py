"""Main view for the Auto Reply plugin."""

import discord
from typing import Callable, Optional
from collections.abc import Sequence

from ..ar import AutoReply
from .constants import RESPONSE_METHOD_MAPPING, RULE_TYPE_MAPPING, SEARCH_RESULT_LIMIT
from .common import send_error
from .editor import AutoReplyRuleModal

from ..models.db import AutoReplyRule


class AutoReplySearchUI(discord.ui.LayoutView):
    """Main UI for the Auto Reply plugin."""

    def __init__(
        self,
        auto_reply: AutoReply,
        message: Optional[discord.Message] = None,
        message_method: Optional[Callable] = None,
        interaction: Optional[discord.Interaction] = None,
        query: Optional[str] = None,
    ) -> None:
        super().__init__(timeout=None)
        if message is None and message_method is None and interaction is None:
            raise ValueError(
                "Either message, message_method, or interaction must be provided."
            )
        self.ar = auto_reply
        self.message = message
        self.message_method = message_method
        self.interaction = interaction
        self.query = query

        self.page = 1  # Pagination state
        self.rules: Sequence[AutoReplyRule] = []  # Current page of rules
        self.max_pages = 1

        self._edit_rule_select: Optional[discord.ui.Select] = (
            None  # Store reference to the edit select for updating options
        )

    async def render(self) -> None:
        self.rules = await AutoReplyRule.search_paginated(
            page=self.page,
            limit=SEARCH_RESULT_LIMIT,
            search_query=self.query,
        )
        self.max_pages = await self._max_pages()

        self.container = await self.generate_container()
        self.clear_items()
        self.add_item(self.container)

        if self.interaction:
            if self.interaction.response.is_done():
                await self.interaction.edit_original_response(view=self)
            else:
                await self.interaction.response.send_message(view=self, ephemeral=False)
        elif self.message:
            await self.message.edit(view=self)
        elif self.message_method:
            # message_method expects this view as its only parameter
            self.message = await self.message_method(view=self)

    async def prev_page_cb(self, interaction: discord.Interaction):
        if self.page > 1:
            self.page -= 1
        await self.render()
        await interaction.response.defer()  # acknowledge the interaction

    async def next_page_cb(self, interaction: discord.Interaction):
        self.max_pages = await self._max_pages()
        if self.page < self.max_pages:
            self.page += 1
        await self.render()
        await interaction.response.defer()  # acknowledge the interaction

    async def page_indicator_cb(self, interaction: discord.Interaction):
        modal = AutoReplySearchSetPageModal(
            current_page=self.page, max_page=self.max_pages, callback=self.set_page
        )
        await interaction.response.send_modal(modal)

    async def set_page(self, page: int):
        self.page = page
        await self.render()

    async def edit_rule_cb(self, interaction: discord.Interaction):
        if self._edit_rule_select is None:
            if self.rules:
                selected_id = self.rules[0].id  # If only one rule, select it by default
            else:
                await send_error(
                    interaction,
                    title="No Rules",
                    description="There are no rules to edit.",
                )
                return
        else:
            selected_id = self._edit_rule_select.values[
                0
            ]  # Get the selected rule ID from the select
        rule = await AutoReplyRule.get_or_none(id=int(selected_id))
        if rule is None:
            await send_error(
                interaction,
                title="Rule Not Found",
                description=f"No rule found with ID {selected_id}.",
            )
            return

        modal = AutoReplyRuleModal(ar=self.ar, rule=rule)
        await interaction.response.send_modal(modal)
        await self.render()
        
    async def toggle_active_cb(self, interaction: discord.Interaction):
        if self.rules and len(self.rules) == 1:
            rule = self.rules[0]
            rule.is_active = not rule.is_active
            await rule.save()
            await self.render()
            await interaction.response.defer()  # acknowledge the interaction
            return
        await send_error(
            interaction,
            title="Multiple Rules",
            description="Please select a single rule to toggle active status.",
        )
    async def delete_rule_cb(self, interaction: discord.Interaction):
        if self.rules and len(self.rules) == 1:
            rule = self.rules[0]
            await rule.delete()
            await self.render()
            await interaction.response.defer()  # acknowledge the interaction
            return
        await send_error(
            interaction,
            title="Multiple Rules",
            description="Please select a single rule to delete.",
        )
            

    async def refresh_cb(self, interaction: discord.Interaction):
        await self.render()
        await interaction.response.defer()  # acknowledge the interaction

    async def generate_container(self) -> discord.ui.Container:
        container = discord.ui.Container()

        if self.rules and len(self.rules) == 1:
            body = f"### Auto-Reply Rule: **{self.rules[0].name}**"
        elif self.query:
            body = f"### Search Results for: `{self.query}`"
        else:
            body = "### Auto-Reply Rules"

        rule_count = await AutoReplyRule.count_total(search_query=self.query)
        if not self.rules:
            body += "\n*No rules found.*"
        elif self.max_pages > 1 and self.page > 1:
            body += f"\n-# Showing {1 + (self.page - 1) * SEARCH_RESULT_LIMIT} to {min(self.page * SEARCH_RESULT_LIMIT, rule_count)} of {rule_count} result(s)."
        elif len(self.rules) > 1:
            body += f"\n-# {rule_count} result(s) found."

        if self.rules and len(self.rules) == 1:
            rule = self.rules[0]
            body += f"\n**ID:** {rule.id}"
            body += f"\n**Trigger:** `{rule.trigger}`"
            body += f"\n**Response:** {RULE_TYPE_MAPPING.get(rule.response_type, {}).get('emoji', '❔')} {RESPONSE_METHOD_MAPPING.get(rule.response_method, {}).get('emoji', '❔')}"
            body += f"\n**Active:** {'✅' if rule.is_active else '❌'}"
        else:
            for rule in self.rules:
                body += f"\n**{rule.id}** - {rule.name} (`{rule.trigger}`, {RULE_TYPE_MAPPING.get(rule.response_type, {}).get('emoji', '❔')} {RESPONSE_METHOD_MAPPING.get(rule.response_method, {}).get('emoji', '❔')})"
                if not rule.is_active:
                    body += " [Inactive]"

        if len(body) > 4000:
            body = body[:3997] + "..."

        container.add_item(discord.ui.TextDisplay(body))

        actions = discord.ui.ActionRow()
        if self.page > 1:
            actions.add_item(
                self._button("⬅️", discord.ButtonStyle.primary, self.prev_page_cb)
            )
        if self.max_pages > 1 or self.page > 1:
            actions.add_item(
                self._button(
                    f"Page {self.page}/{self.max_pages}",
                    discord.ButtonStyle.secondary,
                    self.page_indicator_cb,
                )
            )
        if not (self.rules and len(self.rules) == 1):
            actions.add_item(
                self._button("🔄", discord.ButtonStyle.secondary, self.refresh_cb)
            )
        if self.page < self.max_pages:
            actions.add_item(
                self._button("➡️", discord.ButtonStyle.primary, self.next_page_cb)
            )

        if actions.children:
            container.add_item(actions)

        if self.rules:
            edit_select_actions = discord.ui.ActionRow()
            if self.rules and len(self.rules) == 1:
                edit_select_actions.add_item(
                    self._button(
                        "Edit",
                        discord.ButtonStyle.primary,
                        self.edit_rule_cb,
                    )
                )
                edit_select_actions.add_item(
                    self._button(
                        "Deactivate" if self.rules[0].is_active else "Activate",
                        discord.ButtonStyle.success if not self.rules[0].is_active else discord.ButtonStyle.danger,
                        self.toggle_active_cb,
                    )
                )
                edit_select_actions.add_item(
                    self._button(
                        "Delete",
                        discord.ButtonStyle.danger,
                        self.delete_rule_cb,
                    )
                )
                edit_select_actions.add_item(
                    self._button(
                        "🔄",
                        discord.ButtonStyle.secondary,
                        self.refresh_cb,
                    )
                )
            else:
                self._edit_rule_select = discord.ui.Select(
                    placeholder="Edit...",
                    options=[self._rule_to_select_option(rule) for rule in self.rules],
                    max_values=1,
                    min_values=1,
                )
                self._edit_rule_select.callback = self.edit_rule_cb
                edit_select_actions.add_item(self._edit_rule_select)
            container.add_item(edit_select_actions)

        return container

    def _rule_to_select_option(self, rule: AutoReplyRule) -> discord.SelectOption:
        name = rule.name
        if len(name) > 25:
            name = name[:22] + "..."
        trigger = rule.trigger
        if len(trigger) > 35:
            trigger = trigger[:32] + "..."
        return discord.SelectOption(
            label=name, description=f"{trigger} | ID: {rule.id}", value=str(rule.id)
        )

    async def _max_pages(self) -> int:
        return max(
            1,
            (
                await AutoReplyRule.count_pages(
                    limit=SEARCH_RESULT_LIMIT, search_query=self.query
                )
            ),
        )

    def _button(
        self, label: str, style: discord.ButtonStyle, callback: Callable
    ) -> discord.ui.Button:
        btn = discord.ui.Button(label=label, style=style)
        btn.callback = callback
        return btn


class AutoReplySearchSetPageModal(discord.ui.Modal):
    def __init__(self, current_page: int, max_page: int, callback: Callable):
        super().__init__(title="Go to Page")
        self._callback = callback
        self.current_page = current_page
        self.max_page = max_page
        self.page_input = discord.ui.TextInput(
            label=f"Page Number (1-{max_page})",
            default=str(current_page),
            placeholder="Enter page number",
            required=True,
        )
        self.add_item(self.page_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_input.value)
            if 1 <= page <= self.max_page:
                # Store the desired page number in the modal instance for retrieval after submission
                self.desired_page = page
                await interaction.response.defer()  # Acknowledge the interaction without sending a message

                await self._callback(
                    page
                )  # Call the provided callback with the desired page number
            else:
                await send_error(
                    interaction,
                    "Invalid Page",
                    f"Please enter a number between 1 and {self.max_page}.",
                )
        except ValueError:
            await send_error(
                interaction,
                "Invalid Input",
                "Please enter a valid integer for the page number.",
            )
