#!/bin/bash

# Simple script to run both the Redis server and the bot

# Check if Redis is already running
if ! pgrep -x "redis-server" > /dev/null
then
    echo "Starting Redis server..."

    docker run --rm -d -p 6379:6379 redis:latest
    # Wait for Redis to start
    sleep 5
else
    echo "Redis server is already running."
fi

echo "Starting the bot..."
# Run the bot
poetry run python run.py
