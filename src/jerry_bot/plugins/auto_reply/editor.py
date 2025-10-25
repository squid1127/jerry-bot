"""AutoReply editor module - Discord ui for managing auto-reply settings."""

import discord

from squid_core.components.ui import UIView, UIType
from squid_core.plugin import Plugin
from .models.db import AutoReplyRuleData, AutoReplyRule
from .models.enums import ResponseType, IgnoreType

RULE_TYPE_INFO = {
    ResponseType.TEXT: {
        "label": "Text Reply",
        "description": "Replies with a predefined text message.",
    },
    ResponseType.STICKER: {
        "label": "Sticker Reply",
        "description": "Replies with a sticker.",
    },
    ResponseType.TEXT_RANDOM: {
        "label": "Random Text Reply",
        "description": "Replies with a random text message from a list, formatted as YAML.",
    },
    ResponseType.REACTION: {
        "label": "Reaction",
        "description": "Reacts to the message with a predefined emoji.",
    },
}
RULE_REQUIRED = ["trigger", "response_type", "response_payload"]


class SearchView(UIView):
    """UI view for editing AutoReply settings."""

    def __init__(
        self, plugin: Plugin, search_results: list[AutoReplyRuleData] = None
    ) -> None:
        super().__init__(ui_type=UIType.MESSAGE, timeout=180.0, plugin=plugin)
        description = "Manage your auto-reply rules below."
        if search_results is not None and len(search_results) > 0:
            description += f"\nFound {len(search_results)} matching rules."
        elif search_results is not None:
            description += "\nNo matching rules found."
        else:
            description += "\nProvide search criteria to find rules."
        self.rules = search_results or []

        self.embed = discord.Embed(
            title="AutoReply Rules", description=description, color=discord.Color.blue()
        )

        self.add_button(
            label="New",
            style=discord.ButtonStyle.primary,
            callback=self.create_new_rule,
            skip_defer=True,
        )

        if self.rules:
            self.view.add_item(SearchSelect(rules=self.rules, view=self))

    async def create_new_rule(self, interaction: discord.Interaction) -> None:
        """Callback to create a new auto-reply rule."""
        await interaction.response.defer(thinking=True)
        view = RuleEditor(plugin=self.plugin, new=True)
        await view.init_interaction(interaction)

    async def show_modal(
        self, interaction: discord.Interaction, rule: AutoReplyRuleData
    ) -> None:
        """Show modal to edit the selected auto-reply rule."""
        pass


class SearchSelect(discord.ui.Select):
    """Select menu for choosing an AutoReply rule to edit."""

    def __init__(self, rules: list[AutoReplyRuleData], view: SearchView) -> None:
        options = [
            discord.SelectOption(
                label=rule.trigger,
                description=f"ID: {rule.db_id}",
                value=str(rule.db_id),
            )
            for rule in rules
        ]
        super().__init__(
            placeholder="Select an AutoReply rule to edit...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.search_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        """Callback when a rule is selected."""
        await interaction.response.defer(thinking=True)
        selected_rule_id = int(self.values[0])
        for rule in self.search_view.rules:
            if rule.db_id == selected_rule_id:
                editor = RuleEditor(plugin=self.search_view.plugin, rule=rule)
                await editor.init_interaction(interaction)
                return
        await interaction.response.send_message(
            "⚠️ Uh oh! This rule seems to have disappeared!", ephemeral=True
        )


class RuleEditor(UIView):
    """View for editing a specific AutoReply rule."""

    def __init__(
        self, plugin: Plugin, rule: AutoReplyRuleData = None, new: bool = False
    ) -> None:
        super().__init__(ui_type=UIType.INTERACTION, timeout=300.0, plugin=plugin)

        self.rule: AutoReplyRuleData | None = rule
        self.new = new
        self.updates = {}

        if not (new or rule):
            raise ValueError(
                "Either 'new' must be True or a valid 'rule' must be provided."
            )

        self.add_button(
            label="Edit",
            style=discord.ButtonStyle.primary,
            callback=self.open_edit_modal,
            skip_defer=True,
        )
        if new:
            self.add_button(
                label="Create",
                style=discord.ButtonStyle.success,
                callback=self.create_rule,
            )
            self.type_select = RuleTypeSelect(editor=self)
            self.view.add_item(self.type_select)
        else:
            self.add_button(
                label="Delete",
                style=discord.ButtonStyle.danger,
                callback=self.delete_rule,
            )
            self.add_button(
                label="Save",
                style=discord.ButtonStyle.success,
                callback=self.save_rule,
            )
            self.type_select = RuleTypeSelect(
                editor=self, current_type=self.rule.response_type.value
            )
            self.view.add_item(self.type_select)

        self.embed = self.embed_generator(message=None)

    def embed_generator(self, message: str) -> discord.Embed:
        """Generate an embed representing the current state of the rule."""
        embed = discord.Embed(
            title="New Rule" if self.new else "Edit Rule",
            description=message,
            color=discord.Color.green(),
        )
        if self.rule:
            embed.add_field(name="Trigger", value=self.rule.trigger, inline=False)
            response_type = self.updates.get("response_type", self.rule.response_type)
            responset_type_str = RULE_TYPE_INFO[response_type]["label"] + (
                "*" if "response_type" in self.updates else ""
            )
            embed.add_field(
                name="Response Type",
                value=responset_type_str,
                inline=False,
            )
            payload = self.updates.get("response_payload", self.rule.response_payload)
            embed.add_field(name="Response Payload", value=payload, inline=False)
        else:
            embed.add_field(
                name="Trigger",
                value=self.updates.get("trigger", "Not set (required)"),
                inline=False,
            )
            response_type = self.updates.get("response_type", None)
            responset_type_str = (
                RULE_TYPE_INFO[response_type]["label"]
                if response_type
                else "Not set (required)"
            )
            embed.add_field(
                name="Response Type",
                value=responset_type_str,
                inline=False,
            )
            embed.add_field(
                name="Response Payload",
                value=self.updates.get("response_payload", "Not set (required)"),
                inline=False,
            )
        return embed

    async def cache_reload(self) -> bool:
        """Reload the plugin's cache after changes, returning success status."""
        try:
            await self.plugin.load_cache()
            return True
        except Exception as e:
            self.embed = self.embed_generator(f"⚠️ Failed to reload cache: {e}")
            await self.render()
            return False

    async def create_rule(self, interaction: discord.Interaction) -> None:
        """Create a new AutoReply rule with the provided updates."""

        if not all(key in self.updates for key in RULE_REQUIRED):
            self.embed = self.embed_generator(
                "⚠️ Cannot create rule. Please ensure all required fields are set."
            )
            await self.render()
            return

        try:
            new_rule = AutoReplyRule(**self.updates)
            await new_rule.save()
        except Exception as e:
            self.embed = self.embed_generator(f"⚠️ Failed to create rule: {e}")
            await self.render()
            return
        if await self.cache_reload():
            self.embed = self.embed_generator("✅ Rule created successfully!")
            await self.render()

        # Destroy the editor after creation
        rule = new_rule.as_dataclass()
        editor = RuleEditor(plugin=self.plugin, rule=rule)
        await self.view_transition(new_view=editor)

    async def save_rule(self, interaction: discord.Interaction) -> None:
        """Save changes to the existing AutoReply rule."""
        if not self.rule:
            self.embed = self.embed_generator("⚠️ No rule loaded to save.")
            await self.render()
            return

        try:
            db_rule = await AutoReplyRule.get_or_none(id=self.rule.db_id)
            if not db_rule:
                raise ValueError("Rule not found in database.")
            for key, value in self.updates.items():
                setattr(db_rule, key, value)
            await db_rule.save()
        except Exception as e:
            self.embed = self.embed_generator(f"⚠️ Failed to save rule: {e}")
            await self.render()
            return

        if await self.cache_reload():
            self.embed = self.embed_generator("✅ Rule saved successfully!")
            await self.render()

    async def delete_rule(self, interaction: discord.Interaction) -> None:
        """Delete the existing AutoReply rule."""
        if not self.rule:
            self.embed = self.embed_generator("⚠️ No rule loaded to delete.")
            await self.render()
            return

        try:
            db_rule = await AutoReplyRule.get_or_none(id=self.rule.db_id)
            if not db_rule:
                raise ValueError("Rule not found in database.")
            await db_rule.delete()
        except Exception as e:
            self.embed = self.embed_generator(f"⚠️ Failed to delete rule: {e}")
            await self.render()
            return

        if await self.cache_reload():
            self.embed = self.embed_generator("✅ Rule deleted successfully!")
            await self.render()

        await self.destroy()

    async def open_edit_modal(self, interaction: discord.Interaction) -> None:
        """Open a modal to edit rule details."""
        await interaction.response.send_modal(
            RuleModal(
                editor=self,
                trigger=self.updates.get(
                    "trigger", self.rule.trigger if self.rule else ""
                ),
                payload=self.updates.get(
                    "response_payload", self.rule.response_payload if self.rule else ""
                ),
            )
        )


class RuleTypeSelect(discord.ui.Select):
    """Select menu for choosing the type of AutoReply rule."""

    def __init__(self, editor: RuleEditor, current_type: int | None = None) -> None:
        options = [
            discord.SelectOption(
                label=info["label"],
                description=info["description"],
                value=str(response_type.value),
            )
            for response_type, info in RULE_TYPE_INFO.items()
        ]
        super().__init__(
            placeholder=(
                "Choose rule type..." if current_type is None else "Change rule type..."
            ),
            min_values=1,
            max_values=1,
            options=options,
        )
        self.editor = editor

    async def callback(self, interaction: discord.Interaction) -> None:
        """Callback when a rule type is selected."""
        await interaction.response.defer(thinking=False)

        selected_type = self.values[0]

        self.editor.updates["response_type"] = ResponseType(int(selected_type))

        self.editor.embed = self.editor.embed_generator(
            f"✅ Set response type to {RULE_TYPE_INFO[ResponseType(int(selected_type))]['label']}."
        )
        await self.editor.render()


class RuleModal(discord.ui.Modal):
    """Modal for inputting AutoReply rule details."""

    def __init__(
        self, editor: RuleEditor, trigger: str = "", payload: str = ""
    ) -> None:
        super().__init__(title="AutoReply Rule Details")

        self.editor = editor

        self.trigger_input = discord.ui.TextInput(
            label="Trigger",
            placeholder="Enter the trigger text...",
            default=trigger,
            required=True,
            max_length=200,
        )
        self.add_item(self.trigger_input)

        self.payload_input = discord.ui.TextInput(
            label="Response Payload",
            placeholder="Enter the response payload...",
            default=payload,
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=2000,
        )
        self.add_item(self.payload_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Callback when the modal is submitted."""
        await interaction.response.defer()

        self.editor.updates["trigger"] = self.trigger_input.value
        self.editor.updates["response_payload"] = self.payload_input.value

        self.editor.embed = self.editor.embed_generator(f"✅ Updated rule details.")
        await self.editor.render()
