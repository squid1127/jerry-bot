#!/usr/bin/env bash
set -Eeuo pipefail

# Take down the docker compose services for Jerry bot
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "Stopping Jerry bot docker compose services..."
COMPOSE_FILE="docker-compose.yml"

trap 'echo "[quit] Error on line ${LINENO}. Aborting." >&2' ERR

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker is not installed or not in PATH" >&2
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    echo "Error: docker compose plugin not available" >&2
    exit 1
fi

if [ ! -f "${COMPOSE_FILE}" ]; then
    echo "Error: compose file '${COMPOSE_FILE}' not found in repo root: ${REPO_ROOT}" >&2
    exit 1
fi

# Bring down services regardless of current state
docker compose -f "${COMPOSE_FILE}" down
echo "Compose services have been stopped."
