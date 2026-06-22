"""Constants for the Auto Reply UI"""

from ..models.enums import ResponseType, ResponseMethod
from typing import TypedDict


class RuleSelectOption(TypedDict):
    label: str
    description: str
    emoji: str


RULE_TYPE_MAPPING: dict[ResponseType, RuleSelectOption] = {
    ResponseType.PLAIN: {
        "label": "Plain Text",
        "description": "A basic, static text response.",
        "emoji": "💬",
    },
    ResponseType.RANDOM_YAML: {
        "label": "Random Option",
        "description": "Picks one random text option from a provided YAML list.",
        "emoji": "🎲",
    },
    ResponseType.TEMPLATE: {
        "label": "Jinja2 Template",
        "description": "Evaluates the payload as a Jinja2 template, allowing dynamic variables like message content.",
        "emoji": "🧩",
    },
}
RESPONSE_METHOD_MAPPING: dict[ResponseMethod, RuleSelectOption] = {
    ResponseMethod.REPLY: {
        "label": "Reply",
        "description": "Replies directly to the triggering message.",
        "emoji": "💬",
    },
    ResponseMethod.SEND_MESSAGE: {
        "label": "Send Message",
        "description": "Sends a new message in the same channel without specifically replying.",
        "emoji": "✉️",
    },
    ResponseMethod.SEND_AND_DELETE: {
        "label": "Send and Delete",
        "description": "Deletes the triggering message and sends a new message in its place.",
        "emoji": "🗑️",
    },
    ResponseMethod.DM: {
        "label": "Direct Message",
        "description": "Sends a private Direct Message to the user who triggered the rule.",
        "emoji": "📥",
    },
    ResponseMethod.REPLY_ORIGINAL: {
        "label": "Reply to Original Message",
        "description": "Replies to the message that the triggering message was replying to (does nothing if not a reply).",
        "emoji": "↩️",
    },
    ResponseMethod.LOG: {
        "label": "Log",
        "description": "Silently logs the matched message to the CLI console or channel instead of responding.",
        "emoji": "📝",
    },
    ResponseMethod.REACTION: {
        "label": "Reaction",
        "description": "Reacts to the message. The payload must evaluate to emoji separated by spaces (Unicode or custom).",
        "emoji": "😀",
    },
    ResponseMethod.REACT_ORIGINAL: {
        "label": "Reaction on Original Message",
        "description": "Reacts to the message that the triggering message was replying to (does nothing if not a reply).",
        "emoji": "🪞",
    },
}

HELP_MSG = """## Auto Reply Plugin Help
This plugin allows you to set up automatic replies based on message triggers. You can create rules that specify how the bot should respond when certain patterns are detected in messages.
### Triggers
Triggers are defined using regular expressions (regex). When a message matches the regex pattern, the corresponding auto-reply rule is activated.
### Ignoring
There are a series of commands to ignore auto-replies for specific channels, users, roles, or entire guilds. Use the `/ar-ignore` command group to manage these settings.
### Response Types
The plugin supports various response types:
- **Plain Text**: Sends a predefined text message.
- **Random Option**: Chooses a random option from a YAML list.
- **Jinja2 Template**: Renders payload as a Jinja2 template with access to message context.
### Random Text Reply YAML Format
For the Random Text Reply type, the response payload should be formatted in YAML(list[str]) as follows:
```yaml
  - "First possible reply."
  - "Second possible reply."
  - "Third possible reply."
```
### Jinja2 Templating
When using the Text Reply with Jinja2 type, you can utilize Jinja2 templating features to create dynamic responses. Refer to the [Jinja2 documentation](https://jinja.palletsprojects.com/en/3.1.x/) for more information on how to use templates.

Context available in templates:
- `content`: (str) Trigger message's content
- `message`: (discord.Message) Trigger message object.
- `author`: (discord.User) Author of the trigger message.
- `channel`: (discord.TextChannel) Trigger message's channel.
- `guild`: (discord.Guild) Trigger message's guild.
- `trigger`: (str) The trigger that activated the auto-reply.
- `match`: (tuple[str]) The matched portion of the message content.
{globals_help}
"""

CLI_HELP_MSG = """### AutoReply CLI Command Help:
- `jerry ar` - Open the AutoReply management interface.
- `jerry ar -h` or `jerry ar --help` - Show this help message.

**Query**:
- `jerry ar <query>` - Search auto-reply rules by name or trigger.
- `jerry ar -s <query>` or `jerry ar --search <query>` - Search auto-reply rules by name or trigger in the CLI.
- `jerry ar -l` or `jerry ar --list` - List all auto-reply rules in the CLI.
For `query`, specify a keyword to search or use `id=<rule_id>` to search by rule ID.

**Rule Management**:
- `jerry ar -r <rule_id>` or `jerry ar --remove <rule_id>` - Remove an auto-reply rule by its ID.
- `jerry ar -t <rule_id>` or `jerry ar --toggle <rule_id>` - Toggle an auto-reply rule's active status by its ID.
- `jerry ar -f` or `jerry ar --reload` - Reload all auto-reply rules from the database.
"""

SEARCH_RESULT_LIMIT = 20
