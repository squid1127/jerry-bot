"""AI Provider management for JerryGemini."""

# Packages
import logging
import traceback
from abc import ABC, abstractmethod

# squid core
import core

# Internal Imports
from .constants import ConfigFileDefaults, ConfigDefaults
from .ai_types import AIMethodCall, AIResponse, AIQuery, AIQuerySource, AIMethodStatus
from .providers import AIProvider, ProviderRegistry
from .methods import AIMethod, AIMethodRegistry

# Logging
logger = logging.getLogger("jerry.JerryGemini.ai")


# Primary Chat Handling Class
class ChatInstance:
    """
    Generic chat instance class for handling chat sessions. Relies on the AIProvider to interact with the AI model.
    """

    def __init__(self, config: dict, id: int):
        """
        Args:
            config (dict): Configuration dictionary for the chat instance.
            id (int): Unique identifier for the chat instance, typically the channel ID.
        """

        self.channel_id = id
        self.config = config
        self.initialize_provider()
        self.logger = logging.getLogger(f"jerry.JerryGemini.chat.{self.channel_id}")

    def initialize_provider(self):
        """
        Initialize the AI provider based on the configuration.

        Returns:
            AIProvider: An instance of the AI provider.
        """
        provider_name = self.config["ai"]["provider"]
        provider_class = ProviderRegistry.get_provider(provider_name)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}")
        self.provider: AIProvider = provider_class(self.config["ai"])

    async def do_response(self, query: AIQuery, response: AIResponse) -> None:
        """
        Handle the response from the AI model and send it to the appropriate Discord channel.

        Args:
            query (AIQuery): The query object containing the message and other parameters.
            response (AIResponse): The response from the AI model.
        """
        self.logger.debug(f"Processing response: {response}")
        self.logger.info(f"Response from {response.source.value} to {query.source.value}: {response.text}")
        if not query.response_method:
            self.logger.warning("No response method defined for query, skipping response handling.")
            return

        # Call the response method with the query and response
        await query.response_method(discord_objects=query.discord, response=response)

    async def do_method(
        self, method_call: AIMethodCall, query: AIQuery
    ) -> list[AIResponse]:
        """
        Execute a method call and return the response.

        Args:
            method_call (AIMethodCall): The method call to execute.

        Returns:
            list[AIResponse]: The response from the AI model.
        """
        self.logger.debug(f"Executing method call: {method_call}")
        method = AIMethodRegistry.get_method(method_call.method_name)
        method_config = self.config["methods_config"].get(method_call.method_name, {})
        method_call.method_config = method_config
        if not method:
            raise ValueError(f"Method not found: {method_call.method_name}")

        try:
            response = await method.run(method_call)
            if response.response_model or response.response_model_query:
                if response.response_user:
                    await self.do_response(query, response.response_user)
                if response.response_model_query:
                    model_response = await self.chat_input(
                        response.response_model_query
                    )
                else:
                    model_response = await self.chat_input(
                        AIQuery(
                            message=response.response_model,
                            discord=(
                                method_call.query.discord if method_call.query else None
                            ),
                            response_method=query.response_method,
                            source=AIQuerySource.METHOD,
                        )
                    )
                if response.response_user:
                    model_response.insert(0, response.response_user)
                return [model_response]

            self.logger.info(f"Method {method.name} executed successfully")
            if response.response_user:
                await self.do_response(query, response.response_user)
                return [response.response_user]
            return [
                AIResponse(
                    text="", source=AIQuerySource.METHOD, method_call=method_call
                )
            ]

        except Exception as e:
            self.logger.error(f"Error executing method {method.name}: {e}")
            self.logger.error(traceback.format_exc())

            ai_responses = await self.chat_input( 
                AIQuery(
                    message=f"Error executing method {method.name}: {e}",
                    discord=(
                        method_call.query.discord if method_call.query else None
                    ),
                    response_method=query.response_method,
                    source=AIQuerySource.METHOD,
                )
            )
            return ai_responses

    async def chat_input(self, query: AIQuery, **kwargs) -> list[AIResponse]:
        """
        Send a chat message to the AI model and receive a response.

        Args:
            query (AIQuery): The query object containing the message and other parameters.
            **kwargs: Additional parameters for the chat request.

        Returns:
            list[AIResponse]: The response from the AI model.
        """
        self.logger.debug(f"Sending query: {query}")
        response = await self.provider.chat_input(query, **kwargs)
        self.logger.debug(f"Received response: {response}")

        await self.do_response(query, response)

        if response.function_calls and len(response.function_calls) > 0:
            responses: list[AIResponse] = []
            self.logger.info(
                f"Processing {len(response.function_calls)} function calls"
            )
            for call in response.function_calls:
                try:
                    method_response = await self.do_method(call, query)
                    if method_response:
                        responses.extend(method_response)
                except Exception as e:
                    self.logger.error(
                        f"Error processing function call {call.method_name}: {e}"
                    )

            responses.insert(0, response)
            return responses
        return [response]