import asyncio
import discord
from discord.ext import commands


class ShellCore:
    """
    Core shell functionality for the bot. Contains methods for sending messages in the shell channel, as well as attributes for the bot, channel, interactive mode, and name
    """

    def __init__(self, bot: commands.Bot, channel_id: int, name: str):
        self.bot = bot

        self.channel_id = channel_id
        self.interactive_mode = None
        self.name = name
        
        self.commands = []
        
        self.presets = {
            "CogNoCommandError": {
                "title": "Command Error",
                "msg_type": "error",
                "description": "Command not found in cog. How the ~~~~ did this happen?",
            },
        }

    # Start the shell
    async def start(self):
        """Start the shell (find the channel and start logging)"""
        try:
            self.channel = self.bot.get_channel(self.channel_id)
            print("[Core.Shell] Shell channel found!")
            print("[Core.Shell] Starting logging...")
            await asyncio.sleep(1)
            await self.log(
                f"{self.name.title()} has successfully started.",
                title="Bot Started",
                msg_type="success",
                cog="Shell",
            )
        except:
            print("[Core.Shell] Shell channel not found!")
            return
        
    def add_command(self, command: str, cog: str, description: str):
        self.commands.append(ShellCommandEntry(command, cog, description))

    async def create_embed(
        self,
        message: str=None,
        title: str = None,
        msg_type: str = "info",
        cog: str = None,
        preset: str = None,
    ):
        if preset:
            title = self.presets[preset]["title"]
            msg_type = self.presets[preset]["msg_type"]
            message = self.presets[preset]["description"]
        try:
            message
            title
        except:
            raise ValueError("Message or title must be provided")
        if msg_type == "error" or msg_type == "fatal_error":
            color = discord.Color.red()
        elif msg_type == "success":
            color = discord.Color.green()
        elif msg_type == "warning":
            color = discord.Color.orange()
        else:
            color = discord.Color.blurple()
        embed = discord.Embed(
            title=f"[{msg_type.upper()}] {title}",
            description=message,
            color=color,
        )
        embed.set_author(name=cog)
        embed.set_footer(text=f"Powered by {self.name.title()} Bot")
        return embed

    # Send a log message
    async def log(
        self,
        message: str=None,
        title: str = None,
        msg_type: str = "info",
        cog: str = None,
        plain_text: str = None,
        preset: str = None,
        edit: discord.Message = None,
    ):  
        embed = await self.create_embed(
            message=message,
            title=title,
            msg_type=msg_type,
            cog=cog,
            preset=preset,
        )
        
        if edit:
            msg_object = await edit.edit(
                content=(
                    plain_text
                    if plain_text
                    else ("@everyone" if msg_type == "fatal_error" else "")
                ),
                embed=embed,
            )
            return msg_object
        
        msg_object = await self.channel.send(
            (
                plain_text
                if plain_text
                else ("@everyone" if msg_type == "fatal_error" else "")
            ),
            embed=embed,
        )
        return msg_object

class ShellCommand:
    """
    A class to represent a shell command. Contains methods for sending messages in the shell channel, as well as attributes for the command name, cog, and shell
    """

    def __init__(
        self,
        name: str,
        cog: str,
        shell: ShellCore,
        channel: discord.TextChannel = None,
        query: str = None,
        message: discord.Message = None
    ):
        self.name = name
        self.cog = cog
        self.core = shell
        self.query = query
        self.message = message
        if channel:
            self.channel = channel
        else:
            self.channel = self.core.channel
            
    def __call__(self):
        return (self.name, self.query)

    async def log(
        self,
        description: str= None,
        title: str= None,
        fields: list = None,
        footer: str = None,
        msg_type: str = "info",
        preset: str = None,
        edit: discord.Message = None,
    ):
        """
        Logs a message by creating and sending an embed to the specified channel.
        Args:
            description (str): The description text for the embed.
            title (str): The title of the embed.
            fields (list, optional): A list of dictionaries representing fields to add to the embed. 
                                     Each dictionary should have 'name' and 'value' keys, and optionally an 'inline' key.
            footer (str, optional): The footer text for the embed.
            msg_type (str, optional): The type of message, which determines the embed color. Defaults to "info".
            edit (discord.Message, optional): An existing message to edit with the new embed. If None, a new message is sent.
        Returns:
            discord.Message: The message object that was sent or edited.
        """
        embed = await self.core.create_embed(description, title, msg_type, self.cog, preset=preset)
        if fields:
            for field in fields:
                embed.add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", False),
                )
        if footer:
            embed.set_footer(text=footer)
        if edit:
            msg_object = await edit.edit(embed=embed)
        else:
            msg_object = await self.channel.send(embed=embed)
        return msg_object
    


class ShellCommandEntry:
    """
    A class to represent a shell command entry for command parsing. Contains attributes for the command, cog, and description
    """

    def __init__(self, command: str, cog: str, description: str):
        self.command = command
        self.cog = cog
        self.description = description

    def __str__(self):
        return f"`{self.command}` - {self.description}"


class ShellHandler(commands.Cog):
    def __init__(self, bot: commands.Bot, core: ShellCore):
        self.bot = bot
        self.core = core

        # Ingreated commands
        self.core.add_command("status", "ShellHandler", "Check the status of the bot")
        self.core.add_command("help", "ShellHandler", "Show this help message")
        self.core.add_command("count", "ShellHandler", "A random command that counts up to a number")
        
        # Debug commands
        self.core.add_command("debug-nocog", "NotACog", "A command inside a non-existent cog")
        self.core.add_command("debug-nocommand", "ShellHandler", "A command that does not exist in the cog")
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Start the shell"""
        await self.core.start()
        print("[Core.ShellHandler] Shell started!")

    # Shell command Listener
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for shell commands in the shell channel"""
        if message.author == self.bot.user:
            return
        if message.channel.id == self.core.channel_id:
            if message.content.startswith(f"{self.core.name.lower()}"):
                result = await self.execute_command(message)

    # Shell command parser
    async def execute_command(self, message: discord.Message) -> str:
        try:
            self.core.channel
        except AttributeError:
            print("[Core.ShellHandler] Shell channel not found!")
            return

        # Check if command is empty
        try:
            command = message.content.split(" ")[1].lower()
        except IndexError:
            command = "help"

        # Find the command in the command list
        commandEntry = None
        for cmd in self.core.commands:
            if cmd.command == command:
                commandEntry: ShellCommandEntry = cmd
                break

        # Check if the command is found
        if not commandEntry:
            await self.core.log(
                f"Command `{command}` not found, use `{self.core.name.lower()} help` to see available commands.",
                title="Command Not Found",
                msg_type="error",
                cog="Shell",
            )
            return

        commandClass = ShellCommand(
            name=commandEntry.command,
            cog=commandEntry.cog,
            shell=self.core,
            query=" ".join(message.content.split(" ")[2:]),
            message=message,
        )

        # Execute the command
        try:
            await self.bot.cogs[commandEntry.cog].shell_callback(commandClass)
        except KeyError:
            await self.core.log(
                f"Command `{command}` is registered, but its cog ({commandEntry.cog}) cannot be found.",
                title="Command Error",
                msg_type="error",
                cog="Shell",
            )
        except AttributeError:
            await self.core.log(
                f"Command `{command}` is registered, but the cog `{commandEntry.cog}` does not have a shell implementation.",
                title="Command Error",
                msg_type="error",
                cog="Shell",
            )
        except Exception as e:
            await self.core.log(
                f"An unknown error occurred while executing command `{command}`: {e}",
                title="Command Error",
                msg_type="error",
                cog="Shell",
            )
        return

    async def shell_callback(self, command: ShellCommand):
        if command.name == "status":
            # Run cog_check on all cogs
            edit = await command.log(   
                f"{self.bot.user.name.title()} is currently online and operational.\n\nChecking cogs...",
                title="Bot Status",
                msg_type="info",
            )
            fields = []
            for cog in self.bot.cogs:
                try:
                    check = await self.bot.cogs[cog].cog_status()
                    fields.append({"name": cog, "value": check})
                except AttributeError:
                    fields.append({"name": cog, "value": "Status unknown"})

            await command.log(
                f"{self.bot.user.name.title()} is currently online and operational.",
                title="Bot Status",
                fields=fields,
                msg_type="success",
                edit=edit,
            )
            return
        elif command.name == "help":
            # Show help message
            fields = [
                {
                    "name":"Running Commands",
                    "value": f"To run a command, type `{self.core.name.lower()} <command>` in the shell channel (this channel)."
                },
                {
                    "name":"Commands",
                    "value": "- " + "\n- ".join([str(cmd) for cmd in self.core.commands])
                }
            ]
            edit = await command.log(
                f"Use this shell to manage bot and view logs",
                title="Help",
                msg_type="info",
                fields=fields,
            )
            return
        elif command.name == "count":
            # Count to a number
            try:
                count = int(command.query[0])
            except:
                await command.log(
                    f"Please provide a number to count to.",
                    title="Count Error",
                    msg_type="error",
                )
                return
            edit = await command.log(
                f"0/{count}",
                title="Counting",
                msg_type="info",
            )
            for i in range(count):
                edit = await command.log(
                    f"{i+1}/{count}",
                    title="Counting",
                    msg_type="info",
                    edit=edit,
                )
                if edit.reactions:
                    edit = await command.log(
                        f"Counting stopped at {i+1}/{count}",
                        title="Counting",
                        msg_type="info",
                        edit=edit,
                    )
                    break

            return
        
        await command.log(preset="CogNoCommandError")

    async def cog_status(self):
        return f"Running\nChannel: {self.core.channel.mention}\nInteractive Mode: {self.core.interactive_mode}"