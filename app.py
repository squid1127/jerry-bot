"""
Jerry Application Runner
=========================
This script is the main entry point for the Jerry bot. It loads the environment variables and starts the bot.

Environment Variables
---------------------
- JERRY_TOKEN: The Discord bot token for Jerry
- JERRY_SHELL: The channel ID for the shell channel
- POSTGRES_CONNECTION: The PostgreSQL connection string for the database
- POSTGRES_PASSWORD: The PostgreSQL password for the database
- POSTGRES_POOL: The PostgreSQL pool size for the database

"""

from jerry import Jerry # Jerry bot

# environment variables
from dotenv import load_dotenv
import os
import logging

# Configure logging
logger = logging.getLogger("runner")

logger.info("Running Jerry Bot")

# Load the environment variables
logger.info("Loading environment variables")
load_dotenv()

logger.info(f" Environment Variables Loaded (Hashed: {Jerry.hash_config(None, os.environ)})")

channel = int(os.getenv("JERRY_SHELL"))
token = os.getenv("JERRY_TOKEN")

logger.info(f"Channel: {channel} | Token: {token}")

jerry = Jerry(discord_token=token, shell_channel=channel)
postgres_pool = os.getenv("POSTGRES_POOL") if os.getenv("POSTGRES_POOL") else 20
jerry.add_db(os.getenv("POSTGRES_CONNECTION"), os.getenv("POSTGRES_PASSWORD"), int(postgres_pool))

# Start the Jerry bot
logger.info("Running Jerry Bot")
jerry.run()