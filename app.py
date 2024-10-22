"""
Jerry Application Runner
=========================
This script is the main entry point for the Jerry bot. It loads the environment variables and starts the bot.

Environment Variables
---------------------
- JERRY_TOKEN: The Discord bot token for Jerry
- JERRY_GEMINI_TOKEN: The Gemini API token for Jerry
- JERRY_GEMINI_CHANNEL: The channel ID for the Gemini channel
- JERRY_SHELL: The channel ID for the shell channel
- POSTGRES_CONNECTION: The PostgreSQL connection string for the database
- POSTGRES_PASSWORD: The PostgreSQL password for the database
- POSTGRES_POOL: The PostgreSQL pool size for the database

"""

from jerry import Jerry # Jerry bot
from downreport import DownReport # DownReport bot

# environment variables
from dotenv import load_dotenv
import os

print("[Runner] Running Jerry Bot")

# Load the environment variables
print("[Runner] Loading environment variables")
load_dotenv()

channel = int(os.getenv("JERRY_SHELL"))
token = os.getenv("JERRY_TOKEN")

gemini_token = os.getenv("JERRY_GEMINI_TOKEN")
gemini_channel = int(os.getenv("JERRY_GEMINI_CHANNEL"))

jerry = Jerry(discord_token=token, gemini_token=gemini_token, gemini_channel=gemini_channel, shell_channel=channel)
postgres_pool = os.getenv("POSTGRES_POOL") if os.getenv("POSTGRES_POOL") else 20
jerry.add_db(os.getenv("POSTGRES_CONNECTION"), os.getenv("POSTGRES_PASSWORD"), int(postgres_pool))

# Start the Jerry bot
print("[Runner] Running Jerry Bot")
try:
    jerry.run()
except KeyboardInterrupt:
    print("[Runner] Bot stopped by host")
    DownReport(token=token, report_channel=channel).report("Jerry Bot stopped by keyboard interrupt, proceeding with shutdown", title="Jerry Bot Stop", msg_type="warn", cog="DownReport")
    #break
except ConnectionError as e:
    print(f"[Runner] Bot stopped by connection error {e}")
    if e.args[0] == "Database failed after multiple attempts":
        DownReport(token=token, report_channel=channel).report(f"Jerry Bot has failed to connect to the database after multiple attempts; Attempting a restart.", title="Jerry Bot Database Connection Error", msg_type="error", cog="DownReport")
    else:
        DownReport(token=token, report_channel=channel).report(f"Jerry Bot has crashed due to: {e}; Attempting a restart.", title="Jerry Bot Crashed", msg_type="error", cog="DownReport")
except Exception as e:
    print(f"[Runner] Bot crashed {e}")
    DownReport(token=token, report_channel=channel).report(f"Jerry Bot has crashed due to: {e}; Attempting a restart.", title="Jerry Bot Crashed", msg_type="error", cog="DownReport")