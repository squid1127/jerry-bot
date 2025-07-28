"""Ultra-simple update method for JerryBot (as a Portainer service)."""

import core
from discord.ext import commands
import aiohttp
import aiofiles
import os
import json


class SimpleUpdate(commands.Cog):
    """A simple update method for JerryBot."""

    def __init__(self, bot: core.Bot):
        self.bot = bot
        
        self.bot.shell.add_command(
            "update",
            cog="SimpleUpdate",
            description="Update JerryBot to the latest version. Uses a portainer webhook URL.",
        )
        
        self.files = self.bot.filebroker.configure_cog(  # Filebroker
            "SimpleUpdate",
            config_dir=True,
        )
        self.files.init()
        self.cache_file = os.path.join(self.files.get_config_dir(), "update.json")

    async def shell_callback(self, command: core.ShellCommand):
        if command.name == "update":
            if command.query:
                # Set the update URL
                async with aiofiles.open(self.cache_file, 'w') as f:
                    await f.write(json.dumps({"url": command.query}))
                await command.log(
                    f"Update URL set to `{command.query}`. Use `update` (no query) to apply the update.",
                )
            else:
                # Read the update URL from the cache file
                if not os.path.exists(self.cache_file):
                    await command.log(
                        "No update URL set. Use `update <url>` to set the update URL.",
                        msg_type="error",
                    )
                    return
                
                async with aiofiles.open(self.cache_file, 'r') as f:
                    data = await f.read()
                
                try:
                    update_data = json.loads(data)
                    url = update_data.get("url")
                except json.JSONDecodeError:
                    await command.log(
                        "Invalid update data. Please set a valid URL using `update <url>`.",
                        msg_type="error",
                    )
                    return

                if not url:
                    await command.log(
                        "No update URL set. Use `update <url>` to set the update URL.",
                        msg_type="error",
                    )
                    return

                # Perform the update
                async with aiohttp.ClientSession() as session:
                    async with session.post(url) as response:
                        if response.status == 200:
                            content = await response.text()
                            # Here you would typically apply the update, e.g., by writing to files
                            await command.log(f"Update triggered from {url}.", msg_type="success")
                        else:
                            await command.log(
                                f"Failed to fetch update from {url}. Status code: {response.status}",
                                msg_type="error",
                            )