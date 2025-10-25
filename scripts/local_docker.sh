#!/bin/bash

# This script runs the Jerry Bot in a local Docker container for development purposes.

# Build the Docker image
docker build -t jerry:latest .

# Attempt to take down docker compose if it's already running
docker-compose -f docker-compose.yml down

# Run the docker compose for local development
docker-compose -f docker-compose.yml up -d