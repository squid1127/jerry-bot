#!/usr/bin/env bash
set -Eeuo pipefail

# This script initializes the Bot environment.
echo "Initializing bot environment..."

trap 'echo "[init] Error on line ${LINENO}. Aborting." >&2' ERR

# Resolve repo root (script dir is scripts/)
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

VENV_DIR=".venv"
PYTHON_CMD="python3"

# Check prerequisites
if ! command -v git >/dev/null 2>&1; then
    echo "Error: git is not installed or not in PATH" >&2
    exit 1
fi

# Pick a Python
if ! command -v python3 >/dev/null 2>&1; then
    if command -v python >/dev/null 2>&1; then
        PYTHON_CMD="python"
    else
        echo "Error: Python is not installed or not in PATH" >&2
        exit 1
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "${VENV_DIR}" ]; then
    echo "Creating virtual environment with ${PYTHON_CMD}..."
    "${PYTHON_CMD}" -m venv "${VENV_DIR}"
    echo "Virtual environment created."
else
    echo "Virtual environment already exists at ${VENV_DIR}."
fi

# Activate venv
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# Upgrade packaging tools
python -m pip install --upgrade pip setuptools wheel >/dev/null

# Initialize submodules if present
if [ -f .gitmodules ]; then
    echo "Initializing git submodules..."
    git submodule update --init --recursive
else
    echo "No submodules configured (.gitmodules not found). Skipping."
fi

# Install Python packages (top-level)
if [ -f requirements.txt ]; then
    echo "Installing required Python packages from requirements.txt..."
    python -m pip install -r requirements.txt
else
    echo "requirements.txt not found. Skipping top-level dependencies."
fi

# Install core bot packages
if [ -f src/core/requirements.txt ]; then
    echo "Installing core bot packages from src/core/requirements.txt..."
    python -m pip install -r src/core/requirements.txt
else
    echo "Core requirements file not found at src/core/requirements.txt. Skipping."
fi

# Ensure env file exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env <<'EOF'
# Populate required environment variables here. See README.md for details.
EOF
    echo "Created .env. Please configure it with the necessary values."
else
    echo ".env file already exists."
fi

echo "Bot environment initialized successfully."
