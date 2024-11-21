# jerry-bot

Jerry-bot -- The bot designed specifically for LBUSD Drone Soccer Discord and other of squid1127's personal servers.

## Disclaimer

Jerry bot is designed for personal use by squid1127 and is not intended for public use. If you would like to use Jerry bot, please contact squid1127. Why is this repo public? No clue ¯\\_(ツ)_/¯

## Features

- AutoReply: Automatically respond to predetermined responses with corresponding arguments such as "Nuh uh" → "Yuh uh"
- JerryGemini: Google Gemini AI Chatbot, in a specific channel
- Bot Shell: Manage the bot with a CLI in a dedicated channel
- CubbScratchStudiosStickerPack: Send stickers from the CubbScratchStudios sticker pack (Stored in a directory and documented in postgreSQL)

## Installation

If you still want to try out Jerry bot, you can set him up as a docker container. Docker Image: `ghcr.io/squid1127/jerry-bot:main` (No releases yet) You will also need to set up a PostgreSQL database for Jerry bot to store data.

### Environment Variables

- `JERRY_TOKEN`: Discord bot token
- `JERRY_SHELL`: Channel ID for the bot shell
- `JERRY_GEMINI_TOKEN`: Google Gemini API token
- `JERRY_GEMINI_CHANNEL`: Channel ID for the Gemini AI Chatbot
- `POSTGRES_CONNECTION`: PostgreSQL connection string
- `POSTGRES_PASSWORD`: PostgreSQL password (if needed)
- `POSTGRES_POOL`: PostgreSQL pool size (Number of concurrent connections)
