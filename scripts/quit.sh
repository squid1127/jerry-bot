#! /bin/bash
# Take down the docker compose services for Jerry bot
echo "Building Jerry bot Docker image..."
DOCKERCOMPOSE_FILE="docker-compose.yml"


# Check if Dockerfile exists
if [ ! -f "$DOCKERFILE" ]; then
    echo "Error: Dockerfile not found!"
    exit 1
fi

# Remove the stack if it exists
if docker compose -f "$DOCKERCOMPOSE_FILE" ps | grep -q "$NAME"; then
    echo "Removing existing stack..."
    docker compose -f "$DOCKERCOMPOSE_FILE" down
    if [ $? -ne 0 ]; then
        echo "Error: Failed to remove existing stack."
        exit 1
    fi
else
    echo "No existing stack found."
fi
