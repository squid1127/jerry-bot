"""Help message for the Auto Reply plugin."""

HELP_MSG = """## Auto Reply Plugin Help
This plugin allows you to set up automatic replies based on message triggers. You can create rules that specify how the bot should respond when certain patterns are detected in messages.
### Triggers
Triggers are defined using regular expressions (regex). When a message matches the regex pattern, the corresponding auto-reply rule is activated.
### Ignoring
There are a series of commands to ignore auto-replies for specific channels, users, roles, or entire guilds. Use the `/ar-ignore` command group to manage these settings.
### Response Types
The plugin supports various response types:
- **Text Reply**: Sends a predefined text message.
- **Sticker Reply**: Sends a sticker as a reply.
- **Reaction**: Reacts to the message with a specified emoji.
- **Random Text Reply**: Sends a random text message from a list defined in YAML format.
- **Text Reply with Jinja2**: Sends a text message generated using Jinja2 templating.
### Random Text Reply YAML Format
For the Random Text Reply type, the response payload should be formatted in YAML as follows:
```yaml
responses:
  - "First possible reply."
  - "Second possible reply."
  - "Third possible reply."
```
### Jinja2 Templating
When using the Text Reply with Jinja2 type, you can utilize Jinja2 templating features to create dynamic responses. Refer to the [Jinja2 documentation](https://jinja.palletsprojects.com/en/3.1.x/) for more information on how to use templates.

Globals available in templates:
- `content`: The content of the triggering message.
- `message`: The Discord message object.
- `author`: The Discord user object of the message author.
- `channel`: The Discord channel object where the message was sent.
- `guild`: The Discord guild object where the message was sent.
- `bot`: The Discord bot user object.
- `now`: The current UTC time.
- `utcnow`: Alias for `now`.
- `math`: The Python math module.
- `random`: The Python random module.
- `randint`: A function to generate a random integer.
- `randchoice`: A function to choose a random element from a list.
- `regex_match`: A function to check if a regex pattern matches a string.
- `ordinal`: A function to convert an integer to its ordinal representation (e.g., 1st, 2nd, 3rd).
- `asteval`: A function to safely evaluate a mathematical expression.
"""

ERR_MSG_JINJA_RENDER = """Something broke :("""