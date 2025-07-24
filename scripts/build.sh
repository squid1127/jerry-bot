#! /bin/bash
# Build docker image for Jerry bot
echo "Building Jerry bot Docker image..."
DOCKERFILE="dockerfile"
IMAGE_NAME="ghcr.io/squid1127/jerry-bot:main"

# Check if Dockerfile exists
if [ ! -f "$DOCKERFILE" ]; then
    echo "Error: Dockerfile not found!"
    exit 1
fi

# Build the Docker image
docker build -t "$IMAGE_NAME" -f "$DOCKERFILE" .
if [ $? -ne 0 ]; then
    echo "Error: Failed to build Docker image."
    exit 1
fi