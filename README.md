# jerry-bot

Jerry-bot -- a (not so) simple Discord bot, featuring a variety of random features, including an AI chatbot, auto-reply system, and more.

## Legacy Branch

This branch contains a deprecated version jerry-bot that used squid-core's legacy architecture. It is no longer maintained and may not work with the latest version of Discord.py or other dependencies. Please refer to the `main` branch for the latest version of jerry-bot.

## Disclaimer

Jerry bot is designed for personal use by squid1127 and is not intended for public use. ~~If you would like to use Jerry bot, please contact squid1127.~~ Why is this repo public? No clue ¯\\_(ツ)_/¯ That being said, this repo is licensed under the MIT License, so feel free to steal my code :)

As you may be able to tell by the sheer number of deprecated features, this bot is a work in progress and is not guaranteed to be stable or functional. Use at your own risk!

## Features

- **AutoReply**: Automatically respond to predetermined responses with corresponding arguments such as "Nuh uh" → "Yuh uh"
- **JerryGemini**: Google Gemini AI Chatbot with multichannel support, conversation memory, and file processing capabilities
- **Bot Shell**: Manage the bot with a CLI in a dedicated channel
- **Stickers**: Send stickers from various sticker packs (stored in directories with MongoDB indexing)
- **Memory Management**: Advanced caching and data persistence using Redis and MongoDB

## Installation

If you still want to try out Jerry bot, you can set him up as a docker container. Docker Image: `ghcr.io/squid1127/jerry-bot:main` (No releases yet).

The bot requires multiple database services for optimal functionality:

- **Redis**: For caching and temporary storage (required for most features)
- **MongoDB**: For document storage, conversation history, and sticker indexing (required for AI features)

Note: PostgreSQL is now deprecated and has been removed in favor of Redis and MongoDB for memory management.

### Volumes

- `/config`: Configuration & cache files
- `/communal`: Shared resources such as stickers and other assets (deprecated)

### Environment Variables

**Core Bot Configuration:**

- `JERRY_TOKEN`: Discord bot token
- `JERRY_SHELL`: Channel ID for the bot shell

**Database Configuration:**

- `REDIS_URL`: Redis connection URL (format: `redis://localhost:6379`)
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_USERNAME`, `REDIS_PASSWORD`: Alternative Redis connection parameters
- `MONGO_URL`: MongoDB connection URL (format: `mongodb://localhost:27017/jerry-bot`)

**Deprecated Variables (Unused in the latest version):**

- `JERRY_GEMINI_TOKEN`: Google Gemini API token~~ (Now configured via config files)
- `JERRY_GEMINI_CHANNEL`: Channel ID for the Gemini AI Chatbot~~ (Now supports multiple channels)
- `POSTGRES_CONNECTION`: PostgreSQL connection string (deprecated)
- `POSTGRES_PASSWORD`: PostgreSQL password (if needed)
- `POSTGRES_POOL`: PostgreSQL pool size (Number of concurrent connections)

### Configuration

Jerry bot cogs are configured via YAML files located in the `/config/config` directory (confusing? Not sure why I didn't name it data). Each cog has its own configuration file, which can be edited to customize the bot's behavior.

For more information on how to configure each cog, refer to [`config.md`](config.md).

Note: This will probably change in the future, probably to a more database-driven configuration system.
