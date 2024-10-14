from jerry import Jerry # Jerry bot
from downreport import DownReport # DownReport bot

# environment variables
from dotenv import load_dotenv
import os

print("[Runner] Running Jerry Bot")

# Load the environment variables
print("[Runner] Loading environment variables")
load_dotenv()
token = os.getenv("BOT_TOKEN")
db_creds = [
    # {
    #     "name": "Dev Database (Docker)",
    #     "host": "mysql",
    #     "user": os.getenv("MYSQL_USER"),
    #     "password": os.getenv("MYSQL_PASSWORD"),
    #     "db": os.getenv("MYSQL_DATABASE"),
    # },
    {
        "name": "Dev Database (localhost)",
        "host": "localhost",
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "db": os.getenv("MYSQL_DATABASE"),
    },
    {
        "name": "Dev Database (127.0.0.1)",
        "host": "127.0.0.1",
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "db": os.getenv("MYSQL_DATABASE"),
    },
]
channel = int(os.getenv("BOT_SHELL"))

jerry = Jerry(token=token, db_creds=db_creds, shell=channel, gemini_token=os.getenv("GEMINI_TOKEN"))

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