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
        "description": "Basic text, no formatting or embeds.",
        "emoji": "💬",
    },
    ResponseType.RANDOM_YAML: {
        "label": "Random Option",
        "description": "Chooses a random option from a YAML list.",
        "emoji": "🎲",
    },
    ResponseType.TEMPLATE: {
        "label": "Jinja2 Template",
        "description": "Renders payload as a Jinja2 template with access to message context.",
        "emoji": "🧩",
    },
}
RESPONSE_METHOD_MAPPING: dict[ResponseMethod, RuleSelectOption] = {
    ResponseMethod.REPLY: {
        "label": "Reply",
        "description": "Replies to the message.",
        "emoji": "💬",
    },
    ResponseMethod.SEND_MESSAGE: {
        "label": "Send Message",
        "description": "Sends a message in the same channel.",
        "emoji": "✉️",
    },
    ResponseMethod.SEND_AND_DELETE: {
        "label": "Send and Delete",
        "description": "Delete the source message and send a new message in the same channel.",
        "emoji": "🗑️",
    },
    ResponseMethod.DM: {
        "label": "Direct Message",
        "description": "Sends a direct message to the user.",
        "emoji": "📥",
    },
    ResponseMethod.REPLY_ORIGINAL: {
        "label": "Reply to Original Message",
        "description": "Replies to the source reply's original message. (Ignores if the source message is not a reply.)",
        "emoji": "↩️",
    },
    ResponseMethod.LOG: {
        "label": "Log",
        "description": "Logs the message to the CLI channel.",
        "emoji": "📝",
    },
    ResponseMethod.REACTION: {
        "label": "Reaction",
        "description": "Adds a reaction to the message. The response payload should be an emoji (Unicode or custom).",
        "emoji": "😀",
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
- `bot`: (discord.ClientUser) The Discord bot user object.
- `now`: (datetime.datetime) The current UTC time.
- `math`: (math) The Python math module.
- `random`: (random) The Python random module.
- `randint`: (callable) Generates a random integer between two values.
- `randchoice`: (callable) Selects a random element from a list.
- `regex_match`: (callable) A function to check if a regex pattern matches a string.
- `ordinal`: (callable) Converts an integer to its ordinal representation (e.g., 1st, 2nd, 3rd).
- `yaml_load`: (callable) Loads a YAML string into a Python object.
- `yaml_dump`: (callable) Dumps a Python object to a YAML string.
- `json_load`: (callable) Loads a JSON string into a Python object.
- `json_dump`: (callable) Dumps a Python object to a JSON string.
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