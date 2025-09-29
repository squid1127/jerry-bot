"""A simple mqtt integration for JerryBot."""

import asyncio
import json
import logging
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import aiomqtt
from dataclasses import dataclass

from core import Bot

ENV_MAPPING = {
    "MQTT_BROKER": "hostname",
    "MQTT_PORT": "port",
    "MQTT_USERNAME": "username",
    "MQTT_PASSWORD": "password",
}


@dataclass
class MQTTTopicHandler:
    topic: str
    handler: callable


@dataclass(frozen=True, order=True)
class SubscribedMessage:
    """Class to represent a subscription to a message event."""

    name: str  # Added name field to identify the subscription
    author_id: int | None = None
    channel_id: int | None = None
    guild_id: int | None = None


class MQTTCog(commands.Cog):
    """A simple mqtt integration for JerryBot."""

    MQTT_ROOT = "discord/jerry"

    def __init__(self, bot: Bot, from_env: bool = True, creds: dict | None = None):
        self.bot = bot
        self.logger = logging.getLogger("jerry.mqtt")
        self.mqtt_client: aiomqtt.Client | None = None
        self.mqtt_task = None
        self.creds = creds or {"from_env": from_env}
        self.connected = asyncio.Event()
        self.subscribe_handlers = [
            MQTTTopicHandler(f"{self.MQTT_ROOT}/ping", self.handle_ping),
            MQTTTopicHandler(
                f"{self.MQTT_ROOT}/subscribe/message", self.add_message_subscription
            ),
            MQTTTopicHandler(f"{self.MQTT_ROOT}/send", self.send_message),
            MQTTTopicHandler(f"{self.MQTT_ROOT}/command/callback", self.mqtt_command_response),
        ]

        self.subscribed_messages: set[SubscribedMessage] = set()
        self.interactions = {}

    async def cog_load(self):
        """Start the MQTT client."""

        self.mqtt_client = self.create_mqtt_client()
        if not self.mqtt_client:
            self.logger.error("MQTT client not created, cog not loaded")
            return
        self.mqtt_task = asyncio.create_task(self.mqtt_loop())
        await self.connected.wait()
        self.logger.info("MQTT client connected")

    def create_mqtt_client(self) -> aiomqtt.Client | None:
        """Create the MQTT client from credentials or environment variables. Returns None if no credentials are provided."""
        if self.creds and self.creds.get("from_env"):
            found = 0
            for env_var, cred_key in ENV_MAPPING.items():
                value = os.getenv(env_var)
                if value:
                    if cred_key == "port":
                        value = int(value)
                    found += 1
                    self.creds[cred_key] = value
            if found == 0:
                self.logger.error("No MQTT environment variables found")
                return None
        elif not self.creds:
            self.logger.error("No MQTT credentials provided")
            return None
        if "from_env" in self.creds:
            self.creds.pop("from_env")
        return aiomqtt.Client(**self.creds)

    async def mqtt_loop(self):
        """Main MQTT loop."""

        if not self.mqtt_client:
            raise RuntimeError("MQTT client not initialized")

        unknown_exceptions = 0
        while True:
            try:
                await self._main_loop()
            except aiomqtt.MqttError as e:
                self.logger.error(f"MQTT error: {e} - reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                self.logger.error(
                    f"Unexpected error in MQTT loop: {e} - reconnecting in 5 seconds..."
                )
                unknown_exceptions += 1
                await asyncio.sleep(5)
                if unknown_exceptions > 5:
                    self.logger.critical(
                        "Too many unknown exceptions in MQTT loop, stopping."
                    )
                    break

    async def _main_loop(self):
        async with self.mqtt_client as client:
            self.connected.set()

            self.logger.info("MQTT loop started")

            for handler in self.subscribe_handlers:
                await client.subscribe(handler.topic)
                self.logger.info(f"Subscribed to {handler.topic}")

            await client.publish(
                f"{self.MQTT_ROOT}/events/startup",
                '{"msg": "Jerry MQTT client started", "status": "online"}',
            )

            # Subscribe to multiple topics
            async for message in client.messages:
                try:
                    payload = message.payload.decode()
                    topic = str(message.topic)
                    self.logger.info(f"Received MQTT message on {topic}: {payload}")

                    # Handle different topics
                    handler_dict = {h.topic: h.handler for h in self.subscribe_handlers}
                    if topic in handler_dict:
                        await handler_dict[topic](payload)
                    else:
                        self.logger.warning(f"No handler for topic {topic}")

                except Exception as e:
                    self.logger.error(f"Error processing MQTT message: {e}")

    async def publish_message(self, topic: str, payload: str | dict):
        """Utility method to publish messages."""
        if not self.mqtt_client:
            self.logger.error("MQTT client not available")
            return

        if isinstance(payload, dict):
            payload = json.dumps(payload)

        try:
            await self.mqtt_client.publish(topic, payload)
            self.logger.info(f"Published to {topic}: {payload}")
        except Exception as e:
            self.logger.error(f"Failed to publish to {topic}: {e}")

    async def handle_ping(self, payload: str):
        # Add your data handling logic here
        self.logger.info(f"Handling ping: {payload}")

        await self.publish_message(f"{self.MQTT_ROOT}/pong", '{"msg": "Pong!"}')

    async def add_message_subscription(self, payload: str):
        """Add a new message subscription from MQTT."""
        try:
            data = json.loads(payload)
            name = data.get("name")
            if not name:
                await self.publish_message(
                    f"{self.MQTT_ROOT}/subscribe/message/nack",
                    {
                        "msg": "Subscription must have a name",
                        "status": "error",
                        "name": None,
                        "error": "missing_name",
                    },
                )
                self.logger.error("Subscription must have a name")
                return

            # Convert IDs to integers if they're provided as strings, keep as None if not provided
            author_id = int(data["author_id"]) if data.get("author_id") else None
            channel_id = int(data["channel_id"]) if data.get("channel_id") else None
            guild_id = int(data["guild_id"]) if data.get("guild_id") else None

            if not author_id and not channel_id and not guild_id:
                self.logger.error(
                    "At least one of author_id, channel_id, or guild_id must be provided"
                )
                await self.publish_message(
                    f"{self.MQTT_ROOT}/subscribe/message/nack",
                    {
                        "msg": "At least one of author_id, channel_id, or guild_id must be provided",
                        "status": "error",
                        "name": name,
                        "error": "invalid_parameters",
                    },
                )
                return

            sub = SubscribedMessage(
                name=name,
                author_id=author_id,
                channel_id=channel_id,
                guild_id=guild_id,
            )
            self.subscribed_messages.add(sub)
            self.logger.info(f"Added message subscription: {sub}")
            await self.publish_message(
                f"{self.MQTT_ROOT}/subscribe/message/ack",
                {"msg": "Subscription added", "status": "ok", "name": name},
            )
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON payload for message subscription")
            await self.publish_message(
                f"{self.MQTT_ROOT}/subscribe/message/nack",
                {
                    "msg": "Invalid JSON payload",
                    "status": "error",
                    "name": None,
                    "error": "invalid_json",
                },
            )
        except Exception as e:
            self.logger.error(f"Error adding message subscription: {e}")
            await self.publish_message(
                f"{self.MQTT_ROOT}/subscribe/message/nack",
                {"msg": str(e), "status": "error", "name": None},
            )

    async def send_message(self, payload: str):
        """Send a message to a Discord channel from MQTT."""
        try:
            data = json.loads(payload)
            channel_id_raw = data.get("channel_id")
            content = data.get("content", "")
            embeds = data.get("embeds", [])
            typing = data.get("typing", False)
            if not channel_id_raw or not (content or embeds or typing):
                self.logger.error(
                    "send_message requires channel_id and at least one of content, embeds, or typing"
                )
                await self.publish_message(
                    f"{self.MQTT_ROOT}/send_message/nack",
                    {
                        "msg": "channel_id and at least one of content, embeds, or typing required",
                        "status": "error",
                        "channel_id": None,
                    },
                )
                return

            # Convert channel_id to int for Discord API
            channel_id = int(channel_id_raw)
            channel = self.bot.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                self.logger.error(
                    f"Channel {channel_id} not found or is not a text channel"
                )
                return

            embed_objs = []
            for embed_data in embeds:
                embed = discord.Embed.from_dict(embed_data)
                embed_objs.append(embed)

            if typing:
                await channel.typing()
                self.logger.info(f"Typing in channel {channel_id}...")
            if content or embed_objs:
                await channel.send(content=content, embeds=embed_objs)
                self.logger.info(f"Sent message to channel {channel_id}: {content}")
            await self.publish_message(
                f"{self.MQTT_ROOT}/send_message/ack",
                {"msg": "Message sent", "status": "ok", "channel_id": str(channel_id)},
            )
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON payload for send_message")
            await self.publish_message(
                f"{self.MQTT_ROOT}/send_message/nack",
                {"msg": "Invalid JSON payload", "status": "error", "channel_id": None},
            )
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            await self.publish_message(
                f"{self.MQTT_ROOT}/send_message/nack",
                {
                    "msg": str(e),
                    "status": "error",
                    "channel_id": str(channel_id) if "channel_id" in locals() else None,
                },
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for messages and publish them to MQTT."""
        if message.author == self.bot.user:
            return  # Ignore messages from the bot itself
        if not self.mqtt_client:
            return  # MQTT client not initialized

        payload = {
            "author": {
                "id": str(message.author.id),
                "name": str(message.author),
            },
            "content": message.content,
            "channel": {
                "id": str(message.channel.id),
                "name": str(message.channel),
                "dm": isinstance(message.channel, discord.DMChannel),
            },
            "guild": {
                "id": str(message.guild.id) if message.guild else None,
                "name": str(message.guild) if message.guild else None,
            },
            "message_id": str(message.id),
            "timestamp": message.created_at.isoformat(),
        }

        # Determine if messages are on subscribed channels
        for sub in self.subscribed_messages:
            if (
                (not sub.author_id or message.author.id == sub.author_id)
                and (not sub.channel_id or message.channel.id == sub.channel_id)
                and (
                    not sub.guild_id
                    or (message.guild and message.guild.id == sub.guild_id)
                )
            ):
                self.logger.info(
                    f"MQTT: Message from {message.author} in {message.channel} matches subscription {sub.name}"
                )
                # This subscription matches the message
                await self.publish_message(
                    f"{self.MQTT_ROOT}/events/on_message/{sub.name}", payload
                )

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(
            f"MQTT Cog connected as {self.bot.user} (ID: {self.bot.user.id})"
        )
        if not self.mqtt_client:
            self.logger.error("MQTT client not yet initialized")

        if self.mqtt_client and not self.connected.is_set():
            await self.publish_message(
                f"{self.MQTT_ROOT}/events/startup",
                '{"msg": "Bot reached on_ready state", "status": "bot_ready"}',
            )

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if not self.mqtt_client:
            return  # MQTT client not initialized
        if before.status != after.status:
            payload = {
                "user": {
                    "id": str(after.id),
                    "name": str(after),
                },
                "before": str(before.status),
                "after": str(after.status),
                "timestamp": discord.utils.utcnow().isoformat(),
            }
            await self.publish_message(
                f"{self.MQTT_ROOT}/events/on_presence_update", payload
            )
            self.logger.info(
                f"Published presence update for {after} from {before.status} to {after.status}"
            )

    @app_commands.command(name="mqtt", description="Send a request to MQTT")
    @app_commands.describe(
        cmd = "The command to send to MQTT"
    )
    async def mqtt_command(self, interaction: discord.Interaction, cmd: str):
        """A simple command to test MQTT."""
        self.interactions[interaction.id] = interaction
        if not self.mqtt_client:
            await interaction.response.send_message(
                "MQTT client not initialized", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=False)
        await self.publish_message(
            f"{self.MQTT_ROOT}/command",
            {
                "user": str(interaction.user),
                "command": cmd,
                "interaction_id": str(interaction.id),
            },
        )

    async def mqtt_command_response(self, payload:str):
        """Handle a response from MQTT for a command. Similar syntax to send_message."""
        try:
            data = json.loads(payload)
            interaction_id_raw = data.get("interaction_id")
            content = data.get("content", "")
            embeds = data.get("embeds", [])
            if not interaction_id_raw or not (content or embeds):
                self.logger.error(
                    "mqtt_command_response requires interaction_id and at least one of content or embeds"
                )
                return

            # Convert interaction_id to int for Discord API
            interaction_id = int(interaction_id_raw)
            interaction = self.interactions.get(interaction_id)
            if not interaction:
                self.logger.error(
                    f"Interaction {interaction_id} not found"
                )
                return

            embed_objs = []
            for embed_data in embeds:
                embed = discord.Embed.from_dict(embed_data)
                embed_objs.append(embed)
            if content or embed_objs:
                await interaction.followup.send(content=content, embeds=embed_objs)
                self.logger.info(f"Sent message to interaction {interaction_id}: {content}")
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON payload for mqtt_command_response")
        except Exception as e:
            self.logger.error(f"Error sending command response: {e}")
            
    async def cog_status(self) -> str:
        return "🟢" if self.connected.is_set() else "🔴"