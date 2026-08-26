#!/bin/bash

# Simple script to run both the Redis server and the bot

# Check if Redis is already running in podman
if [ -z "$(podman ps --filter "name=redis-server" --filter "status=running" -q)" ]
then
    echo "Starting Redis server..."

    podman run --name redis-server --rm -d -p 6379:6379 docker.io/library/redis:latest
    # Wait for Redis to start
    sleep 5
else
    echo "Redis server is already running."
fi

echo "Starting the bot..."
# Run the bot
poetry run python run.py
