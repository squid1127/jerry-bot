"""Provides a way to generate system and message prompts for plain text AI models."""

from .constants import ConfigDefaults
from .ai_types import AIQuery, AIQuerySource


class SystemPromptGenerator:
    """
    Generates system prompts for the AI model based on the configuration.
    """

    @classmethod
    def generate_system_prompt(
        cls, config: dict, instance_id: int, agents: bool = False
    ) -> str:
        """
        Generate a system prompt based on the configuration.

        Args:
            config (dict): The full configuration dictionary.
            instance_id (int): The ID of the instance.
            agents (bool): Whether to include agent information in the prompt.
        Returns:
            str: The generated system prompt.
        """

        def choose_best(
            key: str, global_config: dict, instance_config: dict, constant: str
        ) -> str:
            """Choose the best value for a given key from global and instance configurations."""
            if key in instance_config and instance_config[key] is not None:
                return instance_config[key]
            elif key in global_config and global_config[key] is not None:
                return global_config[key]
            else:
                return constant

        global_config: dict = config["global"]
        instance_config: dict = config["instances"][instance_id]
        global_prompt_config: dict = global_config.get("prompt", {})
        instance_prompt_config: dict = instance_config.get("prompt", {})

        # Return only instance-extra prompt
        if not instance_prompt_config.get("default", True):
            return instance_prompt_config.get("extra", "").strip()

        # Return global-extra prompt and instance-extra prompt if global prompt is not default
        elif not global_prompt_config.get("default", True):
            return (
                global_prompt_config.get("extra", "")
                + "\n\n"
                + instance_prompt_config.get("extra", "")
            ).strip()

        # Generate agent information if agents are enabled
        agent_info = ""
        if agents:
            agent_info = ConfigDefaults.AGENT_INTRODUCTION.value
            for name, agent in config["agents"].items():
                agent_info += f"\n\n**{name}**: {agent['description']}"
                if "image_output" in agent and agent["image_output"]:
                    agent_info += "-> (can generate images)"
                else:
                    agent_info += "-> (text-only)"
                agent_info += f"\n -> **Friendly Name**: {agent.get('friendly_name', name)}"

        # Use base prompt and append instance and global extra prompts
        extra = ""
        if global_prompt_config.get("extra"):
            extra += global_prompt_config["extra"] + "\n\n"
        if instance_prompt_config.get("extra"):
            extra += instance_prompt_config["extra"] + "\n\n"

        extra = (
            (extra.strip() + "\n\n" + agent_info.strip()) if agents else extra.strip()
        )

        # Generate the system prompt
        system_prompt = ConfigDefaults.PROMPT.value.format(
            ai_emoji=choose_best(
                "personal_emoji",
                global_prompt_config,
                instance_prompt_config,
                ConfigDefaults.AI_EMOJI.value,
            ),
            ai_name=choose_best(
                "name",
                global_prompt_config,
                instance_prompt_config,
                ConfigDefaults.AI_NAME.value,
            ),
            instance_id=str(instance_id),
            extra=extra,
        )

        return system_prompt.strip()


class QueryToTextConverter:
    """
    Converts AIQuery objects to text prompts for the AI model.
    """

    @staticmethod
    def convert_embeds(embeds: list[dict]) -> str:
        """
        Convert a list of embed dictionaries to text prompts.
        """
        embed_text = "**Embed Content**\n"
        for embed in embeds:
            embed_text += f"# {embed.get('title', 'No Title')}\n"
            if embed.get("author", {}).get("name"):
                embed_text += f" - Author: {embed['author']['name']} {f'({embed['author'].get('url', 'No URL')})' if embed['author'].get('url') else ''}\n"
            if embed.get("url"):
                embed_text += f" - URL: {embed['url']}\n"
            if embed.get("description"):
                embed_text += f"{embed['description']}\n"
            if embed.get("fields"):
                embed_text += "Fields:\n"
                for field in embed["fields"]:
                    embed_text += f" - {field.get('name', 'No Name')}: {field.get('value', 'No Value')}\n"
            if embed.get("footer", {}).get("text"):
                embed_text += f"Footer: {embed['footer']['text']}\n"
            embed_text += "[End Embedded Content]\n\n"
        return embed_text.strip()

    @staticmethod
    def convert(query: AIQuery) -> list[str]:
        """
        Convert an AIQuery object to a list of text parts.

        Args:
            query (AIQuery): The AIQuery object to convert.

        Returns:
            list[str]: A list of text prompts derived from the AIQuery.
        """
        parts = []

        if query.source == AIQuerySource.USER:
            if query.reaction:
                metadata = "**Reaction to Message**\n"
                metadata += f" - Reaction: {query.reaction}\n"
            elif query.is_reply and query.reply:
                metadata = (
                    f"**Replying to Message from {query.reply.author.display_name}**\n"
                )
                metadata += f" - Original Message: \n [Start of Original Message]\n"
                metadata += f"{query.reply.message}\n"
                if query.reply.embeds:
                    embed_text = QueryToTextConverter.convert_embeds(query.reply.embeds)
                    if embed_text:
                        metadata += f"{embed_text}\n"
                metadata += "[End of Original Message]\n"
            else:
                metadata = "**Message Sent**\n"
            metadata += f"Author:\n"
            metadata += f" - Name: {query.author.display_name}\n"
            metadata += f" - Mention: {query.author.mention}\n"
            parts.append(metadata)

            if query.message:
                parts.append(query.message)

        elif query.source == AIQuerySource.SYSTEM:
            payload = "**System Message**\n"
            payload += query.message
            parts.append(payload)

        elif query.source == AIQuerySource.METHOD:
            payload = "**Response from Function Call**\n"
            if query.message:
                payload += query.message + "\n"
            parts.append(payload)

        if query.embeds:
            embed_text = QueryToTextConverter.convert_embeds(query.embeds)
            if embed_text:
                parts.append(embed_text)

        return parts


class ResponseTools:
    """
    Provides tools for processing AI responses.
    """

    @staticmethod
    def apply_length_limit(response: str, max_length: int = 2000) -> list[str]:
        """
        Apply a length limit to the response text.

        Args:
            response (str): The response text from the AI model.
            max_length (int): The maximum length of each part of the response.

        Returns:
            list[str]: A list of response parts, each within the specified length limit.
        """

        # Split the input message into paragraphs based on newline
        paragraphs = response.split("\n")
        result = []
        current_segment = ""

        # Ensure paragraphs do not initially exceed the character limit
        new_paragraphs = []
        for para in paragraphs:
            if len(para) > max_length:
                # Split into segments that are exactly the character limit (or less)
                for i in range(0, len(para), max_length):
                    new_paragraphs.append(para[i : i + max_length])
            else:
                new_paragraphs.append(para)

        # Join paragraphs into segments that are less than the character limit
        for para in new_paragraphs:
            # Check if adding the next paragraph exceeds the character limit
            if (
                len(current_segment) + len(para) + (1 if current_segment else 0)
                <= max_length
            ):
                # If it doesn't, add the paragraph to the current segment
                if current_segment:
                    current_segment += "\n" + para
                else:
                    current_segment = para
            else:
                # If it does exceed, save the current segment and start a new one
                result.append(current_segment)
                current_segment = para

        # Append any remaining part of the message
        if current_segment:
            result.append(current_segment)

        return result
