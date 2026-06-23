"""Editor modal for the Auto Reply plugin."""

import discord
from typing import Callable, Optional
import regex as re

from ..ar import AutoReply
from .constants import RULE_TYPE_MAPPING, RESPONSE_METHOD_MAPPING
from ..models.db import AutoReplyRule
from ..models.enums import ResponseType, ResponseMethod
from .common import send_error


class AutoReplyRuleModal(discord.ui.Modal):
    """Modal for creating or editing an Auto Reply Rule."""

    def __init__(self, ar: AutoReply, rule: AutoReplyRule | None = None):
        """Initialize the AutoReplyRuleModal.

        Args:
            rule (AutoReplyRule, optional): The rule to edit. If None, creates a new rule. Defaults to None.
        """
        title = "Rule Editor" if rule else "New Rule"
        super().__init__(title=title)

        self.rule = rule
        self.ar = ar

        self.name_input = discord.ui.TextInput(
            placeholder="Rule name...",
            default=self.rule.name if self.rule else None,
            required=True,
            style=discord.TextStyle.short,
        )

        self.trigger_input = discord.ui.TextInput(
            placeholder="Trigger...",
            default=self.rule.trigger if self.rule else None,
            required=True,
            style=discord.TextStyle.short,
        )

        self.response_type_select = discord.ui.Select(
            placeholder="Select Response Type...",
            options=[
                discord.SelectOption(
                    label=info["label"],
                    description=info["description"],
                    emoji=info["emoji"],
                    value=str(rt.value),
                    default=(self.rule and self.rule.response_type == rt) or False,
                )
                for rt, info in RULE_TYPE_MAPPING.items()
            ],
        )

        self.response_method_select = discord.ui.Select(
            placeholder="Select Response Method...",
            options=[
                discord.SelectOption(
                    label=info["label"],
                    description=info["description"],
                    emoji=info["emoji"],
                    value=str(rm.value),
                    default=(self.rule and self.rule.response_method == rm) or False,
                )
                for rm, info in RESPONSE_METHOD_MAPPING.items()
            ],
        )

        self.response_payload_input = discord.ui.TextInput(
            placeholder="Response payload...",
            default=self.rule.response_payload if self.rule else None,
            required=True,
            style=discord.TextStyle.paragraph,
        )

        self.add_item(
            discord.ui.Label(
                text="Name",
                description="A name for this rule to help you identify it.",
                component=self.name_input,
            )
        )
        self.add_item(
            discord.ui.Label(
                text="Trigger",
                description="A regex pattern that triggers the auto-reply.",
                component=self.trigger_input,
            )
        )
        self.add_item(
            discord.ui.Label(text="Response Type", component=self.response_type_select)
        )
        self.add_item(
            discord.ui.Label(
                text="Response Method", component=self.response_method_select
            )
        )
        self.add_item(
            discord.ui.Label(
                text="Response Payload",
                description="The content of the response (text, sticker ID, etc.).",
                component=self.response_payload_input,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            trigger = self.trigger_input.value
            response_type = ResponseType(int(self.response_type_select.values[0]))
            response_method = ResponseMethod(int(self.response_method_select.values[0]))
            response_payload = self.response_payload_input.value

            # Validate regex pattern
            try:
                re.compile(trigger)
            except re.error as e:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Invalid Trigger",
                        description=f"The regex pattern is invalid: {str(e)}",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            if self.rule:
                # Update existing rule
                self.rule.name = self.name_input.value
                self.rule.trigger = trigger
                self.rule.response_type = response_type
                self.rule.response_method = response_method
                self.rule.response_payload = response_payload
                await self.rule.save()
                message = "Auto-reply rule updated successfully."
                self.ar.plugin.logger.debug(f"Updated rule ID {self.rule.id}")
            else:
                # Create new rule
                new_rule = AutoReplyRule(
                    name=self.name_input.value,
                    response_method=response_method,
                    trigger=trigger,
                    response_type=response_type,
                    response_payload=response_payload,
                )
                await new_rule.save()
                message = "New auto-reply rule created successfully."
                self.ar.plugin.logger.debug(f"Created new rule ID {new_rule.id}")

            try:
                await self.ar.load_cache()
            except Exception as e:
                self.ar.plugin.logger.error(
                    f"Error reloading auto-reply cache: {e}", exc_info=True
                )
                message += "\n\n⚠️ Warning: Cache reload failed. Changes may not be active immediately."

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Auto Reply",
                    description=message,
                    color=discord.Color.green(),
                ),
                ephemeral=True,
            )
        except Exception as e:
            self.ar.plugin.logger.error(
                f"Error in rule modal submission: {e}", exc_info=True
            )
            await send_error(
                interaction, "Error", "Failed to save rule. Please try again."
            )
