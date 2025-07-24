#! /bin/bash
# Build docker image for Jerry bot
echo "Building Jerry bot Docker image..."
DOCKERFILE="dockerfile"
IMAGE_NAME="ghcr.io/squid1127/jerry-bot:main"
DOCKERCOMPOSE="docker-compose.yml"

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

# Remove the stack if it exists
if docker compose -f "$DOCKERCOMPOSE" ps | grep -q "$IMAGE_NAME"; then
    echo "Removing existing stack..."
    docker compose -f "$DOCKERCOMPOSE" down
    if [ $? -ne 0 ]; then
        echo "Error: Failed to remove existing stack."
        exit 1
    fi
else
    echo "No existing stack found."
fi

# Start the Docker compose services
echo "Starting Jerry bot Docker compose services..."
docker compose -f "$DOCKERCOMPOSE" up
if [ $? -ne 0 ]; then
    echo "Error: Failed to start Docker compose services."
    exit 1
fi