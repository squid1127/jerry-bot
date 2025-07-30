"""Model-run functions/methods for interactive features in JerryGemini."""

# Package imports
import logging
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass

# Internal imports
from .ai_types import (
    AIQuery,
    AIMethodStatus,
    AIQuerySource,
    AIResponse,
    AIMethodCall,
    AIMethodResponse,
    AIAgentQuery,
    AIAgentResponse,
)
from .prompts import ResponseTools
from .providers import AIProvider, ProviderRegistry
from .constants import ConfigDefaults


# Method-related imports
import discord
import aiohttp
from io import BytesIO

logger = logging.getLogger("jerry.JerryGemini.methods")


@dataclass
class AIMethodParameter:
    """
    Represents a parameter for an AI method.
    """

    name: str
    param_type: type
    array_subtype: Optional[type] = None
    description: str = ""
    required: bool = True


class AIMethod(ABC):
    """
    Abstract base class for AI methods. All AI methods should inherit from this class.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initializes the AIMethod with the provided configuration.

        Args:
            config (Dict[str, Any]): Optional configuration dictionary for the method.
        """
        self.config = config
        self.logger = logging.getLogger(
            f"jerry.JerryGemini.method.{self.__class__.__name__}"
        )

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Abstract property to provide the name of the AI method. Must be implemented by subclasses.

        Returns:
            str: The name of the AI method.
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Abstract property to provide a description of the AI method. Must be implemented by subclasses.

        Returns:
            str: A string describing the AI method.
        """
        pass

    @property
    @abstractmethod
    def arguments(self) -> list[AIMethodParameter]:
        """
        Abstract property to define the arguments for the AI method. Must be implemented by subclasses.

        Returns:
            list[AIMethodParameter]: A list of parameters for the AI method.
        """
        pass

    @abstractmethod
    async def run(
        self, method_call: AIMethodCall
    ) -> AIMethodResponse | list[AIResponse]:
        """
        Abstract method to run the AI method. Must be implemented by subclasses.

        Args:
            method_call (AIMethodCall): The method call object containing the method name and arguments.

        Returns:
            AIMethodResponse: The response object containing the result of the method call.
            list[AIResponse]: A list of AIResponse objects if applicable. This implies that all responses were already handled by the method.
        """
        pass

    async def __str__(self):
        return f"AIMethod(name={self.name}, description={self.description})"


class AIMethodRegistry:
    """
    Registry for AI methods. Allows for dynamic registration and retrieval of AI methods.
    """

    _methods: Dict[str, AIMethod] = {}

    @classmethod
    def register_method(cls, method: type):
        """
        Registers an AI method.

        Args:
            method (type): The class of the AIMethod to register.
        """
        cls._methods[method.name] = method

    @classmethod
    def get_method(cls, method_name: str) -> Optional[AIMethod]:
        """
        Retrieves an AI method by its name.

        Args:
            method_name (str): The name of the method to retrieve.

        Returns:
            Optional[AIMethod]: The registered AIMethod instance or None if not found.
        """
        return cls._methods.get(method_name)

    @classmethod
    def get_all_methods(cls) -> Dict[str, AIMethod]:
        """
        Retrieves all registered AI methods.

        Returns:
            Dict[str, AIMethod]: A dictionary of all registered AIMethod instances.
        """
        return cls._methods.copy()


# Methods
class AgentRunner(AIMethod):
    """
    Method to run an agent with a specific query.
    """

    name = "agent.run"
    description = (
        "Runs an agent with the provided query. Returns: Agent response | Error message"
    )
    arguments = [
        AIMethodParameter(
            name="agent",
            param_type=str,
            description="The name of the agent to run.",
            required=True,
        ),
        AIMethodParameter(
            name="prompt",
            param_type=str,
            description="The prompt to send to the agent. This should be an LLM prompt that the agent can understand.",
            required=True,
        ),
        AIMethodParameter(
            name="save_output",
            param_type=bool,
            description="Whether to use discord.send_text_attachment to save the output of the agent. This is suggested if, for example, the agent is generating a report or something that should be directed to the user.",
            required=False,
        ),
    ]

    @staticmethod
    async def run(method_call: AIMethodCall) -> list[AIResponse] | AIMethodResponse:
        """
        Runs the agent with the provided query.

        Args:
            method_call (AIMethodCall): The method call object containing the query.

        Returns:
            AIMethodResponse: The response object indicating success or failure.
        """
        responses = []
        config = method_call.method_config.get("agents", {}).get(
            method_call.arguments["agent"]
        )
        if not config:
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model=f"Agent {method_call.arguments['agent']} not found. Make sure you're not referencing the friendly name of the agent, but the actual name in the config.",
            )

        logger.info(
            f"Running agent {method_call.arguments['agent']} with prompt: {method_call.arguments['prompt']}"
        )
        embed = {
            "author": {
                "name": config.get("friendly_name", "AI Agent"),
                "icon_url": config.get("icon_url", ""),
            },
            "description": "Running agent...This may take a while.",
            "fields": [
                {
                    "name": "Prompt",
                    "value": (
                        method_call.arguments["prompt"]
                        if len(method_call.arguments["prompt"]) < 1024
                        else method_call.arguments["prompt"][:1021] + "..."
                    ),
                    "inline": False,
                }
            ],
            "color": 0x278DF2,
        }
        responses.extend(
            await method_call.response_method(
                method_call,
                AIMethodResponse(
                    method_name=method_call.method_name,
                    status=AIMethodStatus.SUCCESS,
                    response_user=AIResponse(
                        text="",
                        embeds=[embed],
                        source=AIQuerySource.METHOD,
                    ),
                ),
            )
        )

        try:
            provider = AgentRunner.initialize_provider(config)
        except ValueError as e:
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model=f"Failed to initialize provider: {str(e)}",
            )

        try:
            response = await provider.agent_input(
                AIAgentQuery(
                    prompt=method_call.arguments["prompt"],
                    system_prompt=config.get("prompt", ""),
                )
            )
        except Exception as e:
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model=f"Failed to run agent: {str(e)}",
            )

        if not response:
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model="No response from agent.",
            )

        embed = {
            "author": {
                "name": config.get("friendly_name", "AI Agent"),
                "icon_url": config.get("icon_url", ""),
            },
            "description": "Agent successfully executed.",
            # "fields": [
            #     {
            #         "name": "Prompt",
            #         "value": (
            #             method_call.arguments["prompt"]
            #             if len(method_call.arguments["prompt"]) < 1024
            #             else method_call.arguments["prompt"][:1021] + "..."
            #         ),
            #         "inline": False,
            #     }
            # ],
            "color": 0x52FF83,  # Green color for success
        }

        if method_call.arguments.get("save_output", False):
            # Save the output as a text file attachment
            file_name = f"{method_call.arguments['agent']}_output.md"
            file_content = response.text.strip()
            file_response = await DiscordSendTextAttachment.run(
                AIMethodCall(
                    method_name="discord.send_text_attachment",
                    arguments={
                        "file_name": file_name,
                        "file_content": file_content,
                    },
                    query=method_call.query,
                    method_config=method_call.method_config,
                )
            )
            response.text = file_response.response_model + "\n\n" + response.text

        query = None
        if response.files:
            query = AIQuery(
                message=response.text,
                source=AIQuerySource.METHOD,
                attachments=response.files,
                discord=(
                    method_call.query.discord
                    if method_call.query and method_call.query.discord
                    else None
                ),
                response_method=(
                    method_call.query.response_method if method_call.query else None
                ),
            )

        responses.extend(
            await method_call.response_method(
                method_call,
                AIMethodResponse(
                    method_name=method_call.method_name,
                    status=AIMethodStatus.SUCCESS,
                    response_model=response.text,
                    response_user=AIResponse(
                        text="",
                        embeds=[embed],
                        source=AIQuerySource.METHOD,
                        files=response.files or [],
                    ),
                    response_model_query=query,
                ),
            )
        )
        return responses

    @staticmethod
    def initialize_provider(config: dict) -> AIProvider:
        """
        Initialize the AI provider based on the configuration.

        Returns:
            AIProvider: An instance of the AI provider.
        """
        provider_name = config["ai"]["provider"]
        provider_class = ProviderRegistry.get_provider(provider_name)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}")
        return provider_class(config["ai"])


class DiscordAddReaction(AIMethod):
    """
    Method to add a reaction to a Discord message.
    """

    name = "discord.add_reaction"
    description = "Adds a reaction to a Discord message (The message the user specifcally sent). Either send a standard emoji or provide a custom emoji ID. Returns: None | Error message"
    arguments = [
        AIMethodParameter(
            name="emoji",
            param_type=str,
            description="The emoji to add as a reaction. Accepts standard emojis or custom emoji names in the format `<:emoji_name:emoji_id>`.",
            required=False,  # Optional, can be provided as a string
        ),
    ]

    @staticmethod
    async def run(method_call: AIMethodCall) -> AIMethodResponse:
        """
        Adds a reaction to a Discord message.

        Args:
            method_call (AIMethodCall): The method call object containing the message ID, emoji, and channel ID.

        Returns:
            AIMethodResponse: The response object indicating success or failure.
        """
        if not method_call.query:
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model=f"Method is missing a query object. This either means you are trying to react to something other than a user message or the dev messed up somehow.",
            )
        if not method_call.query.discord or not method_call.query.discord.message:
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model=f"Provided query does not have a valid Discord message reference. This method can only react to user messages.",
            )

        message = method_call.query.discord.message

        emoji = method_call.arguments.get("emoji")

        logger.info(
            f"Adding reaction to message {message.id} in channel {message.channel.id} with emoji: {emoji}"
        )

        if not emoji:
            # If neither emoji nor emoji_id is provided, we cannot add a reaction
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model="No emoji provided to add reaction.",
            )

        try:
            if emoji:
                await message.add_reaction(emoji)
        except discord.HTTPException as e:
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model=f"Failed to add reaction: {str(e)}",
            )

        # If we reach this point, we have a valid message ID and emoji
        return AIMethodResponse(
            method_name=method_call.method_name,
            status=AIMethodStatus.SUCCESS,
            # response_model=f"Reaction '{emoji}' added to message {message.id} successfully.",
        )


class DiscordSendMessage(AIMethod):
    """
    Method to send a message to a Discord channel. This method is identical to sending plain text, but allows for sending a message in addition to executing a method.
    """

    name = "discord.send_message"
    description = "Sends a message to a Discord channel. This method is identical to sending plain text, but allows for sending a message in addition to executing a method. Returns: None | Error message"
    arguments = [
        AIMethodParameter(
            name="message",
            param_type=str,
            description="The message to send to the Discord channel.",
            required=True,
        ),
    ]

    @staticmethod
    async def run(method_call: AIMethodCall) -> AIMethodResponse:
        """
        Sends a message to a Discord channel.

        Args:
            method_call (AIMethodCall): The method call object containing the message and channel ID.

        Returns:
            AIMethodResponse: The response object indicating success or failure.
        """
        # Create response based on the method call
        return AIMethodResponse(
            method_name=method_call.method_name,
            status=AIMethodStatus.SUCCESS,
            response_user=AIResponse(
                text=method_call.arguments["message"],
                source=AIQuerySource.MODEL,
            ),
        )


class DiscordSendDirectMessage(AIMethod):
    """
    Method to send a direct message to a Discord user.
    """

    name = "discord.send_direct_message"
    description = "Sends a direct message to the Discord user who sent this message. Returns: None | Error message"
    arguments = [
        AIMethodParameter(
            name="message",
            param_type=str,
            description="The message to send in the direct message.",
            required=True,
        ),
    ]

    @staticmethod
    async def run(method_call: AIMethodCall) -> AIMethodResponse:
        """
        Sends a direct message to a Discord user.

        Args:
            method_call (AIMethodCall): The method call object containing the user ID and message.

        Returns:
            AIMethodResponse: The response object indicating success or failure.
        """
        if not method_call.query or not method_call.query.author:
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model="Method is missing a query object or author.",
            )

        user = method_call.query.discord.message.author
        message_content = method_call.arguments.get("message")

        logger.info(f"Sending direct message to user {user.id}")

        try:
            for part in ResponseTools.apply_length_limit(
                message_content, max_length=2000
            ):
                if part:
                    await user.send(part)
        except discord.HTTPException as e:
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model=f"Failed to send direct message: {str(e)}",
            )

        return AIMethodResponse(
            method_name=method_call.method_name,
            status=AIMethodStatus.SUCCESS,
        )


class DiscordSendTextAttachment(AIMethod):
    """
    Method to send a text file as an attachment in a Discord channel.
    """

    name = "discord.send_text_attachment"
    description = "Sends a text file as an attachment in a Discord channel. Returns: Success message | Error message"
    arguments = [
        AIMethodParameter(
            name="file_name",
            param_type=str,
            description="The name of the file to send. This should include the file extension (e.g., 'example.txt').",
            required=True,
        ),
        AIMethodParameter(
            name="file_content",
            param_type=str,
            description="The content of the file to send.",
            required=True,
        ),
    ]

    @staticmethod
    async def run(method_call: AIMethodCall) -> AIMethodResponse:
        """
        Sends a text file as an attachment in a Discord channel.

        Args:
            method_call (AIMethodCall): The method call object containing the file name and content.

        Returns:
            AIMethodResponse: The response object indicating success or failure.
        """
        if not method_call.query or not method_call.query.discord:
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model="Method is missing a query object or Discord references.",
            )

        file_name = method_call.arguments.get("file_name")
        file_content = method_call.arguments.get("file_content")
        if isinstance(file_content, str):
            # Strip any leading/trailing whitespace
            file_content = file_content.strip()
            # Convert string content to bytes
            file_content = BytesIO(file_content.encode("utf-8"))

        if not file_name or not file_content:
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model="File name and content must be provided.",
            )

        channel = method_call.query.discord.channel
        logger.info(f"Sending text attachment '{file_name}' to channel {channel.id}")

        try:
            await channel.send(file=discord.File(fp=file_content, filename=file_name))
        except discord.HTTPException as e:
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model=f"Failed to send text attachment: {str(e)}",
            )

        return AIMethodResponse(
            method_name=method_call.method_name,
            status=AIMethodStatus.SUCCESS,
            response_model=f"Text attachment '{file_name}' sent successfully.",
        )


class SpaceBinPost:
    """
    Method to post a message to SpaceBin.
    """

    name = "spacebin.post"
    description = "Post a plain text message to a local pastebin service, allowing for longer messages to be sent in a single message. Please ask the user before using this method and be sure to leave out sensitive information. Warning: This feature is experimental and may not work as expected. It is recommended to use this method only for non-sensitive information and to inform users that messages may be publicly accessible. Returns: Success | Error message"
    arguments = [
        AIMethodParameter(
            name="message",
            param_type=str,
            description="The message to post to SpaceBin.",
            required=True,
        ),
    ]

    async def run(method_call: AIMethodCall) -> AIMethodResponse:
        """
        Posts a message to SpaceBin.

        Args:
            method_call (AIMethodCall): The method call object containing the message.

        Returns:
            AIMethodResponse: The response object indicating success or failure.
        """
        base_url = method_call.method_config.get("post_url", "https://spaceb.in/")
        logger.info(f"Posting message to SpaceBin at {base_url}")

        url = f"{base_url}{'' if base_url.endswith('/') else '/'}api/"
        message = method_call.arguments.get("message")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"content": message}) as response:
                if response.status != 200:
                    logger.error(f"Failed to post to SpaceBin: {response.status}")
                    return AIMethodResponse(
                        method_name=method_call.method_name,
                        status=AIMethodStatus.FAILED,
                        response_model=f"Failed to post to SpaceBin: {response.status}",
                    )

                data: dict = await response.json()

        id = data.get("payload", {}).get("id")
        if not id:
            logger.error("Failed to get ID from SpaceBin response.")
            return AIMethodResponse(
                method_name=method_call.method_name,
                status=AIMethodStatus.FAILED,
                response_model="Failed to get ID from SpaceBin response.",
            )
        response_url = f"{base_url}{'' if base_url.endswith('/') else '/'}{id}/raw"

        embed = {
            "title": "SpaceBin Posted Successfully",
            "url": response_url,
            "color": 0x52FF83,  # Green color for success
        }
        footer = method_call.method_config.get("footer", {})
        if footer:
            embed["footer"] = {
                "text": footer.get("text", ""),
                **(
                    {"icon_url": footer.get("icon_url")}
                    if footer.get("icon_url")
                    else {}
                ),
            }

        logger.info(f"Message posted to SpaceBin: {response_url}")

        return AIMethodResponse(
            method_name=method_call.method_name,
            status=AIMethodStatus.SUCCESS,
            response_model=f"Message posted to SpaceBin successfully. An embed of this link has been sent in this channel. ({response_url})",
            response_user=AIResponse(
                text="",
                embeds=[embed],
                source=AIQuerySource.METHOD,
            ),
        )


class ThisWillError(AIMethod):
    """
    A debug method that will always error.
    """

    name = "debug.error"
    description = "A debug method that will always error. Returns: None"
    arguments = []

    @staticmethod
    async def run(method_call: AIMethodCall) -> AIMethodResponse:
        """
        Always raises an error.

        Args:
            method_call (AIMethodCall): The method call object.

        Returns:
            AIMethodResponse: The response object indicating failure.
        """
        raise RuntimeError("This is a debug method that always errors.")


AIMethodRegistry.register_method(AgentRunner)
AIMethodRegistry.register_method(DiscordAddReaction)
AIMethodRegistry.register_method(DiscordSendMessage)
AIMethodRegistry.register_method(DiscordSendDirectMessage)
AIMethodRegistry.register_method(DiscordSendTextAttachment)
AIMethodRegistry.register_method(SpaceBinPost)
AIMethodRegistry.register_method(ThisWillError)
