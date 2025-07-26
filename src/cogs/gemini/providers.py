"""LLM Provider Implementations for JerryGemini"""

# Packages
from abc import ABC, abstractmethod
import logging
import random, mimetypes # Generate file names

# Provider Packages
import google.genai as genai
from google.genai import types as gem_types
from google.genai import errors as gem_errors
from io import BytesIO

# Internal Imports
from .ai_types import (
    AIResponse,
    AIResponseSource,
    AIQuery,
    AIMethodCall,
    AIQuerySource,
    AIAgentQuery,
    QueryAttachment,
    AIAgentResponse,
)
from .constants import ConfigFileDefaults, ConfigDefaults
from .prompts import QueryToTextConverter

# Debug Provider
import yaml


# AI Provider Base Class
class AIProvider(ABC):
    """
    Abstract base class for AI providers. In charge of managing all interactions with the AI model.
    """

    def __init__(self, config: dict):
        """
        Args:
            config (dict): Configuration dictionary for the AI provider.
        """
        self.config = config
        self.id = id
        self.initialize(config)

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Abstract property to provide the name of the AI provider. Must be implemented by subclasses.

        Returns:
            str: The name of the AI provider.
        """
        pass
    
    @property
    @abstractmethod
    def agent_support(self) -> bool:
        """
        Abstract property to indicate if the provider supports agent queries. Must be implemented by subclasses.

        Returns:
            bool: True if the provider supports agent queries, False otherwise.
        """
        pass

    @abstractmethod
    def initialize(self, config: dict):
        """
        Initialize the AI provider with the given configuration. This should configure the model but not start any sessions.

        Args:
            config (dict): Configuration dictionary for the AI provider.
        """
        pass

    @abstractmethod
    def start_chat(self):
        """
        Initlialize a provider-specific chat session. This should prepare the provider for handling chat interactions.
        """
        pass

    @abstractmethod
    async def chat_input(self, query: AIQuery, **kwargs) -> AIResponse:
        """
        Send a chat message to the AI model and receive a response.

        Args:
            query (AIQuery): The query object containing the message and other parameters.
            **kwargs: Additional parameters for the chat request.

        Returns:
            Response: The response from the AI model.
        """
        pass

    @abstractmethod
    async def agent_input(self, query: AIAgentQuery, **kwargs) -> AIAgentResponse:
        """
        Send an agent query to the AI model and receive a response.
        Args:
            query (AIAgentQuery): The agent query object containing the message and other parameters.
            **kwargs: Additional parameters for the agent request.

        Returns:
            AIAgentResponse: The response from the AI model.
        """
        pass

class ProviderRegistry:
    """
    Registry for AI providers. This class manages the available AI providers and their configurations.
    """

    _providers = {}

    @classmethod
    def register_provider(cls, provider_class: type):
        """
        Register a new AI provider.

        Args:
            provider_class (type): Class of the provider to register.
        """
        cls._providers[provider_class.name] = provider_class

    @classmethod
    def get_provider(cls, name: str):
        """
        Get a registered AI provider by name.

        Args:
            name (str): Name of the provider to retrieve.

        Returns:
            The registered AI provider class.
        """
        return cls._providers.get(name)


class DebugProvider(AIProvider):
    """
    Debug AI Provider for testing and development purposes.
    This provider does not perform any actual AI processing.
    """

    name = "debug"
    agent_support = True

    def __init__(self, config: dict):
        """
        Initialize the Debug AI provider with the given configuration.

        Args:
            config (dict): Configuration dictionary for the Debug AI provider.
        """
        self.config = config
        self.logger = logging.getLogger(f"jerry.JerryGemini.providers.debug")
        self.initialize(config)

    def initialize(self, config: dict):
        """
        Initialize the Debug AI provider with the given configuration.
        """
        self.logger.info("DebugProvider initialized with config: %s", config)

    def start_chat(self):
        """
        Start a chat session. This is a no-op for the DebugProvider.
        """
        self.logger.info("DebugProvider chat session started")

    async def chat_input(self, query: AIQuery, **kwargs) -> AIResponse:
        """
        Simulate sending a chat message and return a mock response.

        Args:
            query (AIQuery): The query object containing the message and other parameters.
            **kwargs: Additional parameters for the chat request.

        Returns:
            AIResponse: A mock response from the DebugProvider.
        """
        self.logger.debug("DebugProvider received query: %s", query)

        # Convert the query in an embed for response
        embed = {
            "author": {
                "name": (
                    (
                        query.author.display_name
                        if query.author.display_name
                        else query.author.username
                    )
                    if query.author
                    else "Unknown"
                ),
            },
            "description": f"{query.message}",
            "fields": [
                {
                    "name": "Source",
                    "value": query.source.value,
                    "inline": True,
                },
            ],
            "color": 0x00FF00,  # Green color for debug responses
            "footer": {
                "text": "This is a debug message.",
            },
        }

        return AIResponse(
            text="",
            embeds=[embed],
            source=AIQuerySource.SYSTEM,
        )

    async def agent_input(self, query: AIAgentQuery, **kwargs) -> AIResponse:
        raise NotImplementedError(
            "DebugProvider does not support agent input. Use chat_input instead."
        )


class GeminiProvider(AIProvider):
    """
    Google Gemini AI Provider
    """

    name = "gemini"
    agent_support = True

    def __init__(self, config: dict):
        """
        Initialize the Gemini AI provider with the given configuration.

        Args:
            config (dict): Configuration dictionary for the Gemini AI provider.
        """
        self.config = config
        self.model = None
        self.session = None
        self.logger = logging.getLogger(f"jerry.JerryGemini.providers.gemini")
        self.client = genai.Client(api_key=config.get("api_key"))
        self.initialize(config)

    def generate_functions(self, methods: dict[str, any]) -> list[gem_types.Tool]:
        """Convert AIMethods to Gemini function definitions."""

        TYPES = {
            str: "string",
            int: "integer",
            bool: "boolean",
            list: "array",
        }
        functions = [
            {
                "name": method.name,
                "description": method.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        param.name: {
                            "type": TYPES.get(param.param_type, "string"),
                            "description": param.description,
                            **(
                                {
                                    "items": {
                                        "type": TYPES.get(param.array_subtype, "string")
                                    }
                                }
                                if param.array_subtype
                                else {}
                            ),
                        }
                        for param in method.arguments
                    },
                    "required": [
                        param.name for param in method.arguments if param.required
                    ],
                },
            }
            for method in methods.values()
        ]
        return [gem_types.Tool(function_declarations=[func]) for func in functions]

    def initialize(self, config: dict):
        """
        Initialize the Gemini AI provider with the given configuration.
        """
        config = ConfigFileDefaults.CONFIG_SCHEMA_AI(config)
        self.model = config["model"]
        if not self.model:
            raise ValueError("Model must be specified in the configuration.")

        model_top_p = config.get("top_p", 0.95)
        model_top_k = config.get("model_top_k", 40)
        model_temperature = config.get("model_temperature", 1.0)

        # Hardcoded disable all safety setting
        safety_settings = [
            gem_types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"
            ),
            gem_types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"
            ),
            gem_types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"
            ),
            gem_types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"
            ),
            gem_types.SafetySetting(
                category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE"
            ),
        ]
        prompt = config.get("prompt", ConfigDefaults.PROMPT.value)

        tools = self.generate_functions(config.get("methods", {}))
        self.logger.info(f"Generated {len(tools)} methods for GeminiProvider")
        # self.logger.info(tools)  # Debugging output

        #! These do not work in tandem with function calls
        if len(tools) == 0:
            if (
                config.get("gemini_url_context", False) == True
            ):  # Experimental URL context (configuration)
                tools.append(gem_types.Tool(url_context=gem_types.UrlContext))
                self.logger.warning(
                    "URL context tool is enabled. This is an experimental feature and may not work as expected."
                )
            if (
                config.get("gemini_google_search", False) == True
            ):  # Experimental Google Search (configuration)
                tools.append(gem_types.Tool(google_search=gem_types.GoogleSearch))
                self.logger.warning(
                    "Google search tool is enabled. This is an experimental feature and may not work as expected."
                )
                
        if config.get("gemini_image_generation", False):
            self.logger.warning(
                "Image generation tool is enabled. This is an experimental feature and may not work as expected."
            )
            response_modalities = [
                'IMAGE',
                'TEXT',
            ]
        else:
            response_modalities = None
        
        self.prompt = prompt
        if config.get("disallow_system_instruction", False):
            self.logger.warning(
                "Disallowing system instruction in GeminiProvider. This may affect the model's behavior."
            )
            prompt = None
            self.inject_prompt = True
        else:
            self.inject_prompt = False

        self.config = gem_types.GenerateContentConfig(
            safety_settings=safety_settings,
            temperature=model_temperature,
            top_p=model_top_p,
            top_k=model_top_k,
            system_instruction=prompt,
            tools=tools,
            response_modalities=response_modalities,
        )
        self.agent_config = gem_types.GenerateContentConfig(
            safety_settings=safety_settings,
            temperature=model_temperature,
            top_p=model_top_p,
            top_k=model_top_k,
            tools=tools,
            response_modalities=response_modalities,
        )

    def start_chat(self):
        """
        Start a chat session with the Gemini AI model.
        This method prepares the provider for handling chat interactions.
        """

        self.session = self.client.aio.chats.create(
            model=self.model,
            config=self.config,
        )

    async def file_to_part(self, attachment: QueryAttachment) -> list[gem_types.Part]:
        """
        Convert an attachment to a Gemini Part object.

        Args:
            attachment: The attachment to convert.

        Returns:
            list[gem_types.Part]: A list of Gemini Part objects representing the attachment.
        """
        parts = []
        header = f"**Attachment:** {attachment.filename or attachment.attachment_id} ({attachment.content_type or 'unknown type'})"

        # Text attachments read directly
        if not attachment.content_type:
            header += "\nUnknown content type, skipping file."
        elif attachment.content_type.startswith("text"):
            text = attachment.raw_data.decode("utf-8", errors="replace")
            parts.append(gem_types.Part.from_text(text=text))

        else:
            parts.append(
                gem_types.Part.from_bytes(
                    data=attachment.raw_data,
                    mime_type=attachment.content_type or "application/octet-stream",
                )
            )

        parts.insert(0, gem_types.Part.from_text(text=header))
        return parts

    async def convert_query(self, query: AIQuery) -> list:
        """
        Convert an AIQuery object to a list format suitable for the Gemini API.
        Args:
            query (AIQuery): The AIQuery object to convert.
        Returns:
            list: A list representation of the query.
        """
        parts = QueryToTextConverter.convert(query)

        if query.attachments:
            for attachment in query.attachments:
                parts.extend(await self.file_to_part(attachment))

        return parts

    async def chat_input(self, query: AIQuery, **kwargs) -> AIResponse:
        """
        Send a chat message to the Gemini AI model and receive a response.

        Args:
            query (AIQuery): The query object containing the message and other parameters.
            **kwargs: Additional parameters for the chat request.

        Returns:
            AIResponse: The response from the Gemini AI model.
        """
        if not self.session:
            self.start_chat()
            self.logger.debug("Chat session initialized")

        try:
            parts = await self.convert_query(query)
            if self.inject_prompt:
                parts.insert(
                    0,
                    gem_types.Part.from_text(
                        text=self.prompt or ConfigDefaults.PROMPT.value
                    ),
                )
            response = await self.session.send_message(parts, **kwargs)
        except gem_errors.ClientError as e:

            self.logger.error(f"Error sending message to Gemini: {e}")

            if query.source == AIQuerySource.USER:
                return await self.chat_input(
                    AIQuery(
                        message="ERROR: Failed to process user input: " + str(e),
                        source=AIQuerySource.SYSTEM,
                    )
                )

            return AIResponse(
                text="",
                embeds=[
                    {
                        "title": "Gemini Error",
                        "description": f"An unexpected error occurred. Please try again later.",
                        "color": 0xFF0000,  # Red color for errors
                        "fields": [
                            {
                                "name": "More Info",
                                "value": f"||{e}||",
                                "inline": False,
                            }
                        ],
                    },
                ],
                source=AIResponseSource.SYSTEM,
            )

        # text = response.text or ""
        # function_calls = []
        # if response.candidates[0].content.parts[0].function_call:
        #     function_call = response.candidates[0].content.parts[0].function_call

        #     function_calls = [
        #         AIMethodCall(
        #             name=function_call.name,
        #             arguments=function_call.args or {},
        #         )
        #     ]
        function_calls = []
        for part in response.candidates[0].content.parts:
            if part.text:
                text = part.text
            elif part.function_call:
                text = ""
                function_calls.append(
                    AIMethodCall(
                        method_name=part.function_call.name,
                        query=query,
                        arguments=part.function_call.args or {},
                    )
                )
            else:
                text = ""

        return AIResponse(text=text.strip(), function_calls=function_calls)

    async def agent_input(self, query: AIAgentQuery, **kwargs) -> AIAgentResponse:
        """
        Send an agent query to the Gemini AI model and receive a response.

        Args:
            query (AIAgentQuery): The agent query object containing the message and other parameters.
            **kwargs: Additional parameters for the agent request.

        Returns:
            AIResponse: The response from the Gemini AI model.
        """
        if self.inject_prompt:
            query.prompt = (
                self.prompt + "\n" + query.prompt
            )
        else:
            self.agent_config.system_instruction = query.system_prompt if query.system_prompt else ""
        
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=query.prompt,
            config=self.agent_config
        )
        # Handle image generation
        files = []
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                # Process inline image data
                files.append(
                    QueryAttachment(
                        filename=f"gemini_file_{random.randint(1000, 9999)}{mimetypes.guess_extension(part.inline_data.mime_type) or 'bin'}",
                        content_type=part.inline_data.mime_type,
                        buffered_data=BytesIO(part.inline_data.data),
                        raw_data=part.inline_data.data,
                        discord_use_buffered_data=True,
                        attachment_id=None,  # No ID for inline data
                    )
                )
                
                self.logger.info(
                    f"Received inline image data: {files[-1].filename} ({files[-1].content_type})"
                )
        return AIAgentResponse(text=response.text, files=files)

# Register Providers
ProviderRegistry.register_provider(GeminiProvider)
ProviderRegistry.register_provider(DebugProvider)
