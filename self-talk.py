"""Random test to see how jerry will react when speaking to himself"""

# Discord
import discord, asyncio

# Google Gemini client
import google.generativeai as gemini
import google.api_core.exceptions as gemini_selling

# Core
import core

# Main Jerry bot
import jerry

# Environment variables
import os
from dotenv import load_dotenv

# Logs
import logging
logger = logging.getLogger("jerry-st")

# Jerry
class JerryST(core.Bot):
    """
    Jerry bot for self-talk.
    """
    
    def __init__(self, token: str, shell_channel: int, gemini_token: str, gemini_channel: int):
        super().__init__(token, "JerryST", shell_channel)
        
        self.gemini_token = gemini_token
        self.gemini_channel = gemini_channel
    
        gemini.configure(api_key=self.gemini_token)
        self.model = gemini.GenerativeModel(
            "gemini-1.5-flash",
            generation_config=gemini.types.GenerationConfig(
                top_p=0.95,
                top_k=40,
                temperature=1,
            ),
            safety_settings={
                "HARASSMENT": "BLOCK_NONE",
                "HATE": "BLOCK_NONE",
                "SEXUAL": "BLOCK_NONE",
                "DANGEROUS": "BLOCK_NONE",
            },
        )
        
        self.chat = self.model.start_chat()
        
    PROMPT = "You are a discord chatbot named jerry. You are a red octopus. You are there to help out members of the server. You are a friendly and helpful bot. \n\n A member as sent a message to the channel:\n" 
        
    async def on_message(self, message: discord.Message):
        if message.channel.id == self.gemini_channel:
            logger.info(f"JerryST received message: {message.content}")
            async with message.channel.typing():
                while True:
                    try:
                        # response = await self.chat.send_message_async(f'{self.PROMPT}"""{message.content}"""') # Prompts are for losers
                        response = await self.chat.send_message_async(message.content)
                        message = await message.channel.send(response.text)
                    except gemini_selling.ResourceExhausted:
                        logger.error("Gemini API rate limit reached.")
                        await asyncio.sleep(60)
                        continue
                    except Exception as e:  
                        logger.error(f"Error in JerryST: {e}")
                        await message.channel.send(f"Error: {e}")
                    break

            
        
        
if __name__ == "__main__":
    # Load the environment variables
    load_dotenv()
    
    # Start the Jerry bot
    jerry = JerryST(
        token=os.getenv("JERRY_TOKEN"),
        shell_channel=int(os.getenv("JERRY_SHELL")),
        gemini_token=os.getenv("JERRY_GEMINI_TOKEN"),
        gemini_channel=int(os.getenv("JERRY_GEMINI_CHANNEL")),
    )
    jerry.run()