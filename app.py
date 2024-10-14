from jerry import Jerry # Jerry bot
from downreport import DownReport # DownReport bot

# environment variables
from dotenv import load_dotenv
import os

print("[Runner] Running Jerry Bot")

# Load the environment variables
print("[Runner] Loading environment variables")
load_dotenv()

channel = int(os.getenv("BOT_SHELL"))
token = os.getenv("BOT_TOKEN")

jerry = Jerry(discord_token=token, gemini_token=os.getenv("GEMINI_TOKEN"), shell_channel=channel)

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