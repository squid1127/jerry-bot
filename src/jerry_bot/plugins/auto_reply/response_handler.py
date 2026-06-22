"""Response handler for auto-reply rules."""

import random
import regex as re
from typing import Any, Callable, Awaitable

import discord
import yaml
from squid_core import Plugin
from squid_core.components.cli import CLIManager, EmbedLevel

from .jinja_manager import JinjaManager
from .models.db import AutoReplyRuleData
from .models.enums import ResponseMethod, ResponseType


class ResponseHandler:
    """Handles sending responses for auto-reply rules."""

    def __init__(
        self,
        plugin: Plugin,
        jinja_manager: JinjaManager,
        cli_manager: CLIManager | None = None,
    ):
        self.plugin = plugin
        self.jinja_manager = jinja_manager
        self.cli_manager = cli_manager
        self.response_map: dict[ResponseType, Callable[..., Awaitable[str | None]]] = (
            self._initialize_response_map()
        )
        self.method_map: dict[ResponseMethod, Callable[..., Awaitable[None]]] = (
            self._initialize_method_map()
        )

    def _initialize_response_map(
        self,
    ) -> dict[ResponseType, Callable[..., Awaitable[str | None]]]:
        return {
            ResponseType.PLAIN: self._get_plain_response,
            ResponseType.TEMPLATE: self._get_template_response,
            ResponseType.RANDOM_YAML: self._get_random_response,
        }

    def _initialize_method_map(
        self,
    ) -> dict[ResponseMethod, Callable[..., Awaitable[None]]]:
        return {
            ResponseMethod.REPLY: self._method_reply,
            ResponseMethod.SEND_MESSAGE: self._method_send_message,
            ResponseMethod.SEND_AND_DELETE: self._method_send_and_delete,
            ResponseMethod.DM: self._method_dm,
            ResponseMethod.REPLY_ORIGINAL: self._method_reply_original,
            ResponseMethod.LOG: self._method_log,
            ResponseMethod.REACTION: self._method_react,
            ResponseMethod.REACT_ORIGINAL: self._method_react_original,
        }

    async def send_response(self, message: discord.Message, rule: AutoReplyRuleData):
        """Send a response based on the rule's response type."""
        response_content = None
        handler = self.response_map.get(rule.response_type, self._send_unknown_response)
        try:
            response_content = await handler(message, rule)
        except discord.HTTPException as e:
            self.plugin.logger.warning(
                f"Failed to send response for rule {rule.db_id}: {e}"
            )
        except Exception as e:
            self.plugin.logger.error(
                f"Unexpected error in send_response for rule {rule.db_id}: {e}",
                exc_info=True,
            )

        if not (response_content and str(response_content).strip()):
            return

        method_handler = self.method_map.get(rule.response_method, self._method_reply)
        await method_handler(message, response_content)

    # This needs to exist since the response_map expects a coroutine
    async def _get_plain_response(
        self, _: discord.Message, rule: AutoReplyRuleData
    ) -> str:
        return rule.response_payload

    async def _get_template_response(
        self, message: discord.Message, rule: AutoReplyRuleData
    ) -> str | None:
        try:
            response_rendered = await self.jinja_manager.render(
                rule.response_payload,
                content=message.content,
                author=message.author,
                message=message,
                channel=message.channel,
                guild=message.guild,
                bot=self.plugin.framework.bot,
                trigger=rule.trigger,
                match=rule.search(message.content or "") or (),
            )
            if not response_rendered:
                self.plugin.logger.debug(f"Rule {rule.db_id} rendered empty response")
                return None

            if len(response_rendered) > 2000:
                self.plugin.logger.debug(
                    f"Rule {rule.db_id} response truncated (length: {len(response_rendered)})"
                )
                response_rendered = response_rendered[:1997] + "..."
            return response_rendered
        except Exception as e:
            self.plugin.logger.error(
                f"Template rendering error for rule {rule.db_id}: {e}", exc_info=True
            )
            await self._send_error_embed(
                message,
                "Template Error",
                "Failed to render the template. Please check the rule configuration.",
                "If you are a bot admin, check the logs for details.",
            )
            return None

    async def _get_random_response(
        self, message: discord.Message, rule: AutoReplyRuleData
    ) -> str | None:
        try:
            response = self._choose_random(rule.response_payload)
            return response
        except ValueError as e:
            self.plugin.logger.error(
                f"Random response error for rule {rule.db_id}: {e}"
            )
            await self._method_log(
                message,
                f"Error in random response for rule {rule.db_id}: {e}",
            )
            return None

    async def _send_unknown_response(
        self, message: discord.Message, rule: AutoReplyRuleData
    ):
        self.plugin.logger.error(
            f"Rule {rule.db_id} has unknown response type: {rule.response_type}"
        )
        await self._method_log(
            message,
            f"Unknown response type for rule {rule.db_id}: {rule.response_type}",
        )

    async def _send_error_embed(
        self,
        message: discord.Message,
        title: str,
        description: str,
        footer: str | None = None,
    ):
        embed = discord.Embed(title=title, description=description)
        if footer:
            embed.set_footer(text=footer)
        await message.reply(embed=embed)

    def _choose_random(self, response_payload: str) -> str:
        """Choose a random response from a newline-separated list."""
        try:
            responses = yaml.safe_load(response_payload)
            if isinstance(responses, list) and responses:
                return str(random.choice(responses))
            raise ValueError("Response payload is not a valid list.")
        except yaml.YAMLError as e:
            self.plugin.logger.error(f"Error parsing response payload as YAML: {e}")
            raise ValueError("Invalid YAML format.") from e
        
    def _split_emojis(self, content: str) -> list[str]:
        """Split a string into a list of emojis."""
        return re.split(r"\s+", content)

    async def _method_reply(self, message: discord.Message, content: str):
        await message.reply(content)

    async def _method_send_message(self, message: discord.Message, content: str):
        await message.channel.send(content)

    async def _method_send_and_delete(self, message: discord.Message, content: str):
        await message.channel.send(content)
        await message.delete()

    async def _method_dm(self, message: discord.Message, content: str):
        await message.author.send(content)

    async def _method_reply_original(self, message: discord.Message, content: str):
        if message.reference and message.reference.message_id:
            original_message = await message.channel.fetch_message(
                message.reference.message_id
            )
            await original_message.reply(content)

    async def _method_log(self, message: discord.Message, content: str):
        self.plugin.logger.info(f"Auto-reply log for message {message.id}: {content}")
        if self.cli_manager is not None:
            await self.cli_manager.notify(
                title=f"Auto-Reply Log: <#{message.channel.id}>",
                description=content,
                level=EmbedLevel.INFO,
                plugin=self.plugin.name,
            )

    async def _method_react(self, message: discord.Message, content: str):
        try:
            for emoji_str in self._split_emojis(content):
                emoji = discord.PartialEmoji.from_str(emoji_str)
                await message.add_reaction(emoji)
        except discord.HTTPException as e:
            if e.code == 10014:  # Unknown Emoji
                self.plugin.logger.warning(
                    f"Failed to add reaction for rule: Invalid emoji in '{content}' - {e}"
                )
            else:
                raise

    async def _method_react_original(self, message: discord.Message, content: str):
        if message.reference and message.reference.message_id:
            original_message = await message.channel.fetch_message(
                message.reference.message_id
            )
            for emoji_str in self._split_emojis(content):
                emoji = discord.PartialEmoji.from_str(emoji_str)
                try:
                    await original_message.add_reaction(emoji)
                except discord.HTTPException as e:
                    if e.code == 10014:  # Unknown Emoji
                        self.plugin.logger.warning(
                            f"Failed to add reaction for rule: Invalid emoji in '{content}' - {e}"
                        )
                    else:
                        raise
