"""# Constants for JerryGemini configuration"""

from typing import Dict, Any
from typing import Optional as TypingOptional
from enum import Enum
from voluptuous import Schema, Required, Optional, All, Length, Range, ALLOW_EXTRA


# Config Defaults
class ConfigDefaults(Enum):
    """Default configuration values for JerryGemini."""

    # AI Identity and Provider
    AI_NAME: str = "Jerry"
    AI_EMOJI: str = "🐙"

    # Prompt Configuration
    PROMPT = """You are {ai_name}, an intellegent experimental octopus. Your name is {ai_name}, you are displayed and characterized as a red octopus, your emoji and avatar is {ai_emoji} if anyone asks.

The user id of the member who sent the message is included in the request, feel free to use an @mention in place of their name. Mentions are formed like this: <@user id>. 

You are here to be helpful as well as entertain others with your intellegence. You are currently in a discord channel. You are talking to members of the server. Responses should be lengthy and engaging, using your persona of an octopus.

Respond in plain text, in a structured and organized format (use newlines to separate items) with proper grammar and punctuation. You can use emojis, but do not overuse them. Your responses are in markdown. Markdown links are unsupported, so use the full URL. You can also call methods to perform actions, such as sending DMs, adding reactions, etc. If one of these methods fails, please inform and explain to the user why it failed. Many methods will return responses, after which you can respond to the user and/or call another method. For methods that return None (Don't return a response), you can use the discord.send_message method to send a message at the same phase as the method call.

You are currently in a discord channel <#{instance_id}>, so you can use discord features like mentions, emojis, and markdown formatting.

{extra}"""

    # Methods
    BUILTIN_METHODS = ["discord.add_reaction", "discord.send_message"]

    # Agents
    AGENT_PROMPT = """You are an LLM agent receiving a prompts from an AI model. Your task is to respond to the prompt to the best of your ability. If you are not capable of responding, say so as the response. Your response should be formatted in standard markdown."""
    AGENT_METHOD = "agent.run"
    AGENT_INTRODUCTION = f"Below, you are given AI agents that you can use to perform specific tasks, using the {AGENT_METHOD} method. Each agent has a name, description, and a prompt that you can use to interact with it. You can use the agent.run method to run the agent with the given prompt. Please ensure you have explicit consent from the user before running an agent. Agents are as follows:\n"


# Default configuration file contents for JerryGemini
class ConfigFileDefaults:
    # Configuration schema for config
    CONFIG_SCHEMA_AI: Schema = Schema(
        {
            Optional("provider", default="gemini"): All(str, Length(min=1)),
            Optional("api_key"): str,
            Optional("model"): str,
            Optional("top_p", default=0.95): All(float, Range(min=0.0, max=1.0)),
            Optional("model_top_k", default=40): int,
            Optional("model_temperature", default=1.0): float,
            Optional("max_tokens", default=-1): int,
        },
        extra=ALLOW_EXTRA,
    )
    CONFIG_SCHEMA_PROMPT: Schema = Schema(
        {
            Optional("default", default=True): bool,
            Optional("extra", default=""): str,
            Optional("name", default=ConfigDefaults.AI_NAME): str,
            Optional("personal_emoji", default=ConfigDefaults.AI_EMOJI): str,
        }
    )
    CONFIG_SCHEMA: Schema = Schema(
        {
            # Global configuration for JerryGemini
            Required("global"): {
                Optional("timezone", default="UTC"): str,
                Optional("time_in_prompt", default=False): bool,
                Required("ai"): CONFIG_SCHEMA_AI,
                Optional("prompt", default={}): CONFIG_SCHEMA_PROMPT,
                Optional("capabilities", default=[]): All(list, [str]),
                Optional("jerry_command_instance_id", default=None): int,
            },
            # Agents (Extra callable models)
            Required("agents"): dict[
                str,
                Schema(
                    {
                        Required("description"): str,
                        Required("ai"): CONFIG_SCHEMA_AI,
                        Optional("prompt", default=ConfigDefaults.AGENT_PROMPT): str,
                        Optional(
                            "image_output", default=False
                        ): bool,  # Whether the agent can generate images
                    }
                ),
            ],
            # Model Methods
            Optional("methods", default={}): dict[
                str,
                dict[str, Any],
            ],  # Methods are defined as a dictionary of method names to their configurations
            # Channels/Instances
            Required("instances"): dict[
                int,
                Schema(
                    {
                        Optional("prompt", default={}): CONFIG_SCHEMA_PROMPT,
                        Optional("personal_emoji", default=None): str,
                        Optional("capabilities", default=[]): All(list, [str]),
                        Optional("ai", default={}): CONFIG_SCHEMA_AI,
                        Optional("debug", default={}): {
                            Optional("prompt", default=False): bool,
                            Optional("response", default=False): bool,
                        },
                    }
                ),
            ],
        },
    )

    DEFAULT_CONFIG_CONTENTS = """# Configuration for JerryGemini
global:

  # Time zone
  timezone: "America/New_York" # Replace with your desired timezone
  time_in_prompt: true # Include time in the prompt allowing the bot to use the current time in its responses

  # AI Model Configuration
  ai:
    provider: gemini
    api_key: "wth" # Replace with your actual API key (https://aistudio.google.com/apikey)
    model: gemini-2.5-flash
    top_p: 0.95
    model_top_k: 40
    model_temperature: 2.0

  # Emoji for the bot
  personal_emoji: "<:jerry:12345>" # App-specific emoji ID for Jerry

  # Global Prompt
  prompt:
    default: true # Use the default prompt (Jerry)
    extra: Global information for the bot
    
# Agents (Extra callable models)
agents:
    gemini-pro:
        description: "Pro version of Gemini with advanced capabilities."
        ai:
        provider: gemini
        model: gemini-2.5-pro
        top_p: 0.95
        model_top_k: 40
        model_temperature: 1.0
    
# Instances (Channels)
instances:
  123456: # Replace with the actual channel ID
    prompt:
      extra: Put instance-specific instructions here. This will be stacked on top of the global prompt.
    personal_emoji: "<:jerry:123456>" # Server-specific emoji ID for Jerry
    capabilities:
      - hide-seek
      - files
      - dm
      - memory_add
      - pro_query
      
    # debug:
    #   prompt: true
    #   response: true
    """
