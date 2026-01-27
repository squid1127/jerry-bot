"""Revision of the Discord UI system for the Auto Reply plugin."""

import discord

from .models.enums import ResponseType
from .models.db import AutoReplyRule, AutoReplyIgnoreData
from .ar import AutoReply
from .search import Search

RULE_TYPE_INFO = {
    ResponseType.TEXT: {
        "label": "Text Reply",
        "description": "Replies with a predefined text message.",
        "emoji": "💬",
    },
    ResponseType.STICKER: {
        "label": "Sticker Reply",
        "description": "Replies with a sticker.",
        "emoji": "🏷️",
    },
    ResponseType.REACTION: {
        "label": "Reaction",
        "description": "Reacts to the message with a predefined emoji.",
        "emoji": "👍",
    },
    ResponseType.TEXT_RANDOM: {
        "label": "Random Text Reply",
        "description": "Replies with a random text message from a list, formatted as YAML.",
        "emoji": "🎲",
    },
    ResponseType.TEXT_TEMPLATE: {
        "label": "Text Reply with Jinja2",
        "description": "Replies with a text message using Jinja2 templating.",
        "emoji": "🧩",
    },
}


class AutoReplyMainUI(discord.ui.LayoutView):
    """Main UI for the Auto Reply plugin."""

    def __init__(
        self,
        ar: AutoReply,
        message: discord.Message = None,
        message_method: callable = None,
    ):
        """Initialize the AutoReplyMainUI.

        Args:
            ar (AutoReply): The AutoReply instance.
            message (discord.Message, optional): The message to edit. Defaults to None.
            message_method (callable, optional): An async method to send/create the message. Defaults to None.
        """
        super().__init__(timeout=None)
        if message is None and message_method is None:
            raise ValueError("Either message or message_method must be provided.")
        self.message = message
        self.message_method = message_method
        self.ar = ar

    def generate_container(self) -> discord.ui.Container:
        container = discord.ui.Container()
        container.add_item(
            discord.ui.TextDisplay(
                content="### Auto Reply Plugin\nManage your auto-reply rules and settings using the buttons below."
            )
        )
        actions = discord.ui.ActionRow()

        create = discord.ui.Button(
            label="Create Rule",
            style=discord.ButtonStyle.success,
        )
        create.callback = self.create_rule_cb
        actions.add_item(create)

        rules = discord.ui.Button(
            label="Edit Rules",
            style=discord.ButtonStyle.primary,
        )
        rules.callback = self.search_cb
        actions.add_item(rules)


        reload = discord.ui.Button(
            label="Reload All",
            style=discord.ButtonStyle.secondary,
        )
        reload.callback = self.reload_cb
        actions.add_item(reload)
        container.add_item(actions)

        return container

    async def on_timeout(self):
        await self.message.edit(view=None)
        self.stop()

    async def render(self):
        self.container = self.generate_container()
        self.clear_items()
        self.add_item(self.container)
        if self.message:
            await self.message.edit(view=self)
        elif self.message_method:
            self.message = await self.message_method(view=self)

    async def reload_cb(self, interaction: discord.Interaction):
        """Callback to reload all auto-reply rules."""
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

    async def search_cb(self, interaction: discord.Interaction):
        """Callback to open the search modal."""
        search = Search(
            title="Search Rules",
            model=AutoReplyRule,
            callback=self.edit_rule_cb,
            render=lambda rule: discord.SelectOption(
                label=f"Rule ID {rule.id} ({RULE_TYPE_INFO[rule.response_type]['label']})",
                description=rule.trigger[:20],
                emoji=RULE_TYPE_INFO[rule.response_type].get("emoji"),
                value=str(rule.id),
            ),
            search_fields=["trigger", "response_payload"],
        )
        await search.show_modal(interaction)

    async def edit_rule_cb(self, interaction: discord.Interaction, rule: AutoReplyRule):
        """Callback to edit a specific rule."""
        view = AutoReplyRuleView(ar=self.ar, rule=rule)
        await view.start(interaction)

    async def create_rule_cb(self, interaction: discord.Interaction):
        """Callback to create a new rule."""
        modal = AutoReplyRuleModal(ar=self.ar)
        await interaction.response.send_modal(modal)


class AutoReplyRuleModal(discord.ui.Modal):
    """Modal for creating or editing an Auto Reply Rule."""

    def __init__(self, ar: AutoReply ,rule: AutoReplyRule = None):
        """Initialize the AutoReplyRuleModal.

        Args:
            rule (AutoReplyRule, optional): The rule to edit. If None, creates a new rule. Defaults to None.
        """
        title = "Rule Editor" if rule else "New Rule"
        super().__init__(title=title)

        self.rule = rule
        self.ar = ar

        self.trigger_input = discord.ui.TextInput(
            placeholder="Trigger...",
            default=self.rule.trigger if self.rule else None,
            required=True,
            style=discord.TextStyle.paragraph,
        )

        self.response_type_select = discord.ui.Select(
            placeholder="Select Response Type...",
            options=[
                discord.SelectOption(
                    label=info["label"],
                    description=info["description"],
                    emoji=info["emoji"],
                    value=str(rt.value),
                )
                for rt, info in RULE_TYPE_INFO.items()
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
                text="Response Payload",
                description="The content of the response (text, sticker ID, etc.).",
                component=self.response_payload_input,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        trigger = self.trigger_input.value
        response_type = ResponseType(int(self.response_type_select.values[0]))
        response_payload = self.response_payload_input.value

        if self.rule:
            # Update existing rule
            self.rule.trigger = trigger
            self.rule.response_type = response_type
            self.rule.response_payload = response_payload
            await self.rule.save()
            message = "Auto-reply rule updated successfully."
        else:
            # Create new rule
            new_rule = AutoReplyRule(
                trigger=trigger,
                response_type=response_type,
                response_payload=response_payload,
            )
            await new_rule.save()
            message = "New auto-reply rule created successfully."
            
        try:
            await self.ar.load_cache()
        except Exception as e:
            self.ar.plugin.logger.error(f"Error reloading auto-reply cache: {e}")

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Auto Reply",
                description=message,
                color=discord.Color.green(),
            ),
            ephemeral=True,
        )
        
class AutoReplyRuleView(discord.ui.LayoutView):
    """View for displaying an Auto Reply Rule."""

    def __init__(self, ar: AutoReply, rule: AutoReplyRule):
        """Initialize the AutoReplyRuleView.

        Args:
            ar (AutoReply): The AutoReply instance.
            rule (AutoReplyRule): The rule to display.
        """
        super().__init__(timeout=600)
        self.rule = rule
        self.ar = ar

    def generate_container(self) -> discord.ui.Container:
        container = discord.ui.Container()
        container.add_item(
            discord.ui.TextDisplay(
                content=f"### Auto Reply Rule ID {self.rule.id}\n"
                        f"**Trigger:** {self.rule.trigger}\n"
                        f"**Response Type:** {RULE_TYPE_INFO[self.rule.response_type]['label']}\n"
                        f"**Response Payload:** {self.rule.response_payload}"
            )
        )
        
        actions = discord.ui.ActionRow()
        
        edit = discord.ui.Button(
            label="Edit",
            style=discord.ButtonStyle.primary,
        )
        edit.callback = self.edit_rule_cb
        actions.add_item(edit)
        
        delete = discord.ui.Button(
            label="Delete",
            style=discord.ButtonStyle.danger,
        )
        delete.callback = self.delete_rule_cb
        actions.add_item(delete)
        
        container.add_item(actions)
        
        return container
    
    async def on_timeout(self):
        await self.interaction.edit_original_response(view=None)
        self.stop()
        
    async def start(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.container = self.generate_container()
        self.clear_items()
        self.add_item(self.container)
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.send_message(view=self, ephemeral=True)
            
    async def edit_rule_cb(self, interaction: discord.Interaction):
        """Callback to edit the rule."""
        modal = AutoReplyRuleModal(ar=self.ar, rule=self.rule)
        await interaction.response.send_modal(modal)
        
    async def delete_rule_cb(self, interaction: discord.Interaction):
        """Callback to delete the rule."""
        await self.rule.delete()
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Auto Reply",
                description="Auto-reply rule deleted successfully.",
                color=discord.Color.green(),
            ),
            ephemeral=True,
        )
        
        try:
            await self.ar.load_cache()
        except Exception as e:
            self.ar.plugin.logger.error(f"Error reloading auto-reply cache: {e}")
        
        await self.on_timeout()