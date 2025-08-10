# jerry-bot Cog Configuration

Jerry-bot cogs are configured via YAML files located in the `/config/config` directory (confusing? Not sure why I didn't name it data). Each cog has its own configuration file, which can be edited to customize the bot's behavior.

This bot is still not intended for public use. This just exists so I don't forget how configure my own bot T-T

## Table of Contents

- [AutoReply](#autoreply)
- [Stickers](#stickers)
- [JerryGemini](#jerrygemini)
- [UptimeManager (squidcore cog)](#uptimemanager-squidcore-cog)

## AutoReply

This cog allows you to set up automatic replies to specific messages. You can define pairs of trigger phrases and responses.

### Filters

Filters are used to ignore certain messages based on their context, such as channel, guild, user, or role. This allows you to prevent the bot from responding in specific situations.

```yaml
filters:
  - type: "ignore" # Ignore messages within a specific channel
    channel: "1234567890123456789" #! Must be a string, not an integer

  - type: "ignore" # Other ignore types
    #! Use one at a time, not all at once. All options are IDs in string format
    channel: "1234"
    guild: "1234"
    user: "1234"
    role: "1234"
```

### Response Variables

Variables are used to define reusable phrases or patterns that can be referenced in responses. This allows you to maintain consistency and avoid repetition in your replies.

```yaml
vars:
  generic_gaslighting:
    random:
      - text: "Lies, all lies"
      - text: "Prove it"
      - text: "Sure you did"
    merge: true # Merge this variable into the response context, defaults to replacing the response context
```

### Autoreply

This section defines the automatic replies that the bot will send when it detects specific trigger phrases in messages. Messages are matched using regular expressions, allowing for flexible pattern matching.

```yaml
autoreply:
  # Nuh-uh and Yuh-uh
  - regex: "nuh+[\\W_]*h?uh" # Use regex to match message content (not case sensitive)
    response: # Use a response object to define the reply
      text: Yuh-uh ✅

  - regex: "yuh+[\\W_]*h?uh"
    response:
      text: Nuh-uh ❌

    # Use a sticker from the sticker cog
  - regex: "^sticker-darrius$"
    response:
      sticker: "css/darrius"

    # Use a reaction to a message
  - regex: "^fish$"
    response:
      reaction: "🐟"

    # Example use of a variable
  - regex: "^((yes|yeah|but+)\\s)?i did(\\s|$)"
    response:
      random: # Randomly select from the list of responses (not 100% functional yet)
        - text: "No you didn't"
        - text: "No you did not"
        - text: "You didn't"
      var: generic_gaslighting

  - regex: "^((no|nah+|nah+\\sbro|but+)\\s)?i (didn'?t|did\\snot)(\\s|$)"
    response:
      random:
        - text: "Yes you did"
        - text: "You did"
        - text: "But you told me you did tho 🤔"
        - text: "What are you talking about, you totally did do that"
      var: generic_gaslighting
```

#### Response Object

A response object can contain various fields to customize the bot's reply:

```yaml
response:
  text: "Your reply text here" # Text response
  sticker: "sticker_name" # Use a sticker from the sticker cog
  reaction: "reaction_emoji" # Add a reaction to the message (emoji name or ID)
  var: "variable_name" # Use a variable defined in the vars section
  merge: true # Merge this variable into the response context, defaults to replacing the response context
```

## Stickers

Currently, all cog operations are handled through application commands. This cog allows you to manage stickers that can be used in responses.

- `/sticker <name>`: Fetch a sticker by name, or search for a sticker by name.
- `/sticker-add <name> <description> <url>`: Add a new sticker with the specified name, description, and URL.
- `/sticker-force <name>`: Get a sticker and send it immediately, useful for user-install methods where the bot does not have permission to send messages in the channel.
- `/sticker-help`: Show help information for the sticker cog. Also shows sticker categories.

### Naming scheme

Stickers are named using a specific scheme to ensure uniqueness and ease of use. The name should be descriptive and follow the format `<category>/<name>`. For example, a sticker for a character named Darrius in the "css" category would be named `css/darrius`.

### Storage

Sticker files are stored in the `/config/data/stickers` directory. Metadata for stickers is stored in MongoDB, allowing for easy management and retrieval.

## JerryGemini

JerryGemini is a cog that allows you to turn Discord channels into a chat interface for the Google Gemini AI. This enables users to interact with the Gemini AI directly within their Discord server.

### Global Configuration

```yaml
global:
  # Time zone setting
  timezone: "America/New_York" # Set your preferred time zone

  # Google Generative AI Model Configuration
  ai:
    provider: "gemini" # AI provider (currently only Google Gemini is supported)
    api_key: "your-api-key-here"
    model: "gemini-2.5-flash" # Model to use
    top_p: 0.95 # Nucleus sampling parameter
    model_top_k: 40 # Top-k sampling parameter
    model_temperature: 2.0 # Response creativity (0.0-2.0)

  # Global Prompt Configuration
  prompt:
    name: "Jerry" # Bot's name
    personal_emoji: "<:jerry:12345>" # Bot's emoji
    extra: | # Additional prompt context
      Custom instructions and context for the AI...
    # Note that there is a built-in prompt that transforms the model into Jerry!

  jerry_command_instance_id: -1 # Instance ID for the Jerry command
```

### Agents

Agents are specialized AI configurations for different purposes:
Chat instances with access to the `agent.run` capability can use these agents to perform specific tasks or provide specialized responses.

```yaml
agents:
  gemini-pro:
    friendly_name: "Google Gemini Pro 💭"
    description: "Agent with Gemini Pro capabilities..."
    ai:
      provider: "gemini"
      api_key: "your-api-key"
      model: "gemini-2.5-pro"

  search:
    friendly_name: "Google Search 🔍 (And URL Context)"
    description: "Agent with web search and URL context abilities..."
    ai:
      provider: "gemini"
      api_key: "your-api-key"
      model: "gemini-2.0-flash"
      gemini_url_context: true # Enable URL context fetching
      gemini_google_search: true # Enable Google search

  image-gen:
    friendly_name: "Image Generation 🖼️"
    description: "Agent for generating images..."
    ai:
      provider: "gemini"
      model: "gemini-2.0-flash-preview-image-generation"
      api_key: "your-api-key"
      gemini_image_generation: true # Enable image generation support
      disallow_system_instruction: true # This agent does not use system instructions
```

### Methods

External service configurations:

```yaml
methods:
  spacebin.post:
    post_url: "https://spaceb.in/" # URL for posting content, must be a spacebin instance
    # https://github.com/lukewhrit/spacebin
    footer:
      text: "Hosted by a really cool person" # Optional footer text for posts
```

### Instances

Instance-specific configurations for different Discord servers/channels:

```yaml
instances:
  # Application command instance
  -1: # ID defined in global config
    prompt:
      extra: |
        This instance only responds to /ask-jerry commands...
    capabilities:
      - agent.run

  # Channel-specific instance
  123456: # Channel ID
    prompt:
      extra: |
        Server-specific context and information...
      personal_emoji: "<:jerry:54321>" # Can use server emoji rather than app emoji
    capabilities:
      - discord.send_direct_message
      - discord.send_text_attachment
      - spacebin.post
      - agent.run

    # Optional debugging
    debug:
      prompt: true
      response: true

  # Memory-enabled instance
  1403877681443110912:
    memory:
      type: "database" # Enable database-backed memory
    capabilities:
      - discord.send_direct_message
      - spacebin.post
      - agent.run
```

### Configuration Options

#### AI Parameters

- `api_key`: Your Google AI API key
- `model`: Gemini model to use (e.g., `gemini-2.5-flash`, `gemini-2.5-pro`)
- `top_p`: Controls diversity via nucleus sampling (0.0-1.0)
- `model_top_k`: Limits vocabulary for each step (1-40)
- `model_temperature`: Controls randomness (0.0-2.0, higher = more creative)

#### Capabilities

Available capabilities for instances:

- `agent.run`: Allow running specialized agents
- `discord.send_direct_message`: Send DMs to users
- `discord.add_reaction`: Add reactions to messages (built-in)
- `discord.send_text_attachment`: Send text as file attachments
- `spacebin.post`: Post content to external paste service (experimental, not recommended)

#### Special Features

- `gemini_url_context`: Fetch and analyze content from URLs
- `gemini_google_search`: Perform Google searches
- `gemini_image_generation`: Generate images
- `disallow_system_instruction`: Disable system instructions for agents

#### Memory System

- `type: "database"`: Enable persistent memory using database storage

### Usage

- Use `/ask-jerry` command to interact with the AI in application command mode
- Regular chat messages work in channels where JerryGemini is active
- Different instances can have different personalities and capabilities based on server/channel

## UptimeManager (squidcore cog)

Built-in squidcore cog for using Uptime Kuma's passive monitor type. Periodically calls a url to indicate that the service is still up.

```yaml
enabled: false # Disabled by default, enable to use

# Provider for uptime monitoring
# Supported providers:
# - uptime_kuma
# (Use 'None' to use a simple get request)
provider: uptime_kuma

# URL for passive monitoring
url: https://uptimekuma.example.com/api/push/123456

# Interval for uptime checks in seconds
interval: 120
```
