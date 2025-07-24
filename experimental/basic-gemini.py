"""Upmost basic Gemini-Discord bot implementation."""

import discord
from discord.ext import commands
import google.generativeai as gemini
import google.api_core.exceptions as gemini_selling
from google.ai.generativelanguage_v1beta.types import content as gemini_content

TOOLS = [
    gemini.protos.FunctionDeclaration(
        name="reaction",
        description="React to the message sent by the user. Use the emoji as the argument. DO NOT OVERUSE. Be sure to also send the message the normal way (Unless you want to and the user sent a reaction). Multiple reactions can be added by using multiple commands.",
        parameters=gemini_content.Schema(
            type=gemini_content.Type.OBJECT,
            properties={
                "emoji": gemini_content.Schema(
                    type=gemini_content.Type.STRING,
                ),
            },
        ),
    ),
]


class GeminiDiscordBot(commands.Bot):
    """A Discord bot that interacts with the Gemini AI model."""

    def __init__(
        self,
        model_name: str,
        channel_id: int,
        model_instruction: str = "You are a helpful assistant placed in a Discord server. Answer questions and assist users to the best of your ability.",
    ):
        """
        Initialize the bot with the given token and model name.

        Args:
            model_name (str): The name of the Gemini model to use.
            channel_id (int): The ID of the channel to listen to.
            model_instruction (str): Instruction/prompt for the model (default: "You are a helpful assistant...").
        """
        intents = discord.Intents.default()
        intents.messages = True  # Enable message intents
        intents.guilds = True  # Enable guild intents
        intents.message_content = True

        super().__init__(
            intents=intents,
            command_prefix="!",
        )  # Should probably be more restrictive in production

        self.model = gemini.GenerativeModel(
            model_name, system_instruction=model_instruction, tools=TOOLS
        )
        self.chat = None
        self.channel_id = channel_id

    async def on_message(self, message: discord.Message):
        """Handle incoming messages."""
        if message.author == self.user:
            return

        if message.channel.id != self.channel_id:
            return
        
        if not message.content:
            return
        else:
            content = message.content.strip()
            if not content:
                return

        async with message.channel.typing():
            if not self.chat:
                self.chat = self.model.start_chat()

            response = await self.chat.send_message_async(content)

        for part in response.parts:
            if part.text:
                await message.channel.send(part.text)
        if part.function_call:
            name = part.function_call.name
            args = dict(part.function_call.args)
            if name == "reaction":
                emoji = args.get("emoji")
                if emoji:
                    await message.add_reaction(emoji)
                else:
                    await message.channel.send(
                        "No emoji provided for reaction."
                    )


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    TOKEN = os.getenv("DISCORD_TOKEN")
    MODEL_NAME = os.getenv(
        "GEMINI_MODEL_NAME"
    )  # Model name should be a string (e.g., "gemini-2.0-flash")
    CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL"))  # Channel ID should be an integer
    GEMINI_API_KEY = os.getenv(
        "GEMINI_API_KEY"
    )  # Ensure you have set this in your .env file

    PROMPT = "You are a helpful assistant placed in a Discord server. Answer questions and assist users to the best of your ability. Your name is Jerry"

    gemini.configure(api_key=GEMINI_API_KEY)

    bot = GeminiDiscordBot(MODEL_NAME, CHANNEL_ID, model_instruction=PROMPT)
    bot.run(TOKEN)
