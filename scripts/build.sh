#!/usr/bin/env bash
set -Eeuo pipefail

# Build docker image and run docker compose for Bot
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "Building bot Docker image..."
DOCKERFILE="dockerfile"
IMAGE_NAME="ghcr.io/squid1127/jerry-bot:main"
COMPOSE_FILE="docker-compose.yml"

trap 'echo "[build] Error on line ${LINENO}. Aborting." >&2' ERR

# Check prerequisites
if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker is not installed or not in PATH" >&2
    exit 1
fi

# Compose is bundled as `docker compose` with recent Docker versions
if ! docker compose version >/dev/null 2>&1; then
    echo "Error: docker compose plugin not available" >&2
    exit 1
fi

# Check if Dockerfile exists
if [ ! -f "${DOCKERFILE}" ]; then
    echo "Error: Dockerfile '${DOCKERFILE}' not found!" >&2
    exit 1
fi

# Build the Docker image
docker build -t "${IMAGE_NAME}" -f "${DOCKERFILE}" .

# Bring down any existing stack for this compose file
if [ -f "${COMPOSE_FILE}" ]; then
    echo "Bringing down any existing compose stack..."
    docker compose -f "${COMPOSE_FILE}" down || true
else
    echo "Warning: compose file '${COMPOSE_FILE}' not found; skipping compose down/up."
fi

# Start the Docker compose services (foreground)
if [ -f "${COMPOSE_FILE}" ]; then
    echo "Starting bot services with docker compose..."
    docker compose -f "${COMPOSE_FILE}" up
fi