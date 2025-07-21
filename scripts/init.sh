#! /bin/bash

# This script initializes the Jerry bot environment.
echo "Initializing Jerry bot environment..."

VENV_DIR=".venv"
PYTHON_CMD="python3"

# Try different Python commands
if ! command -v python3 &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "Error: Python is not installed or not in PATH"
        exit 1
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment with $PYTHON_CMD..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

# Init Submodules
echo "Initializing submodules..."
git submodule update --init --recursive

# Install python packages
echo "Installing required Python packages..."
source "$VENV_DIR/bin/activate"
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install required Python packages."
    exit 1
fi
echo "Installing core bot packages..."
pip install -r src/core/requirements.txt
echo

# Ensure env file exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    touch .env
    echo "Please configure your .env file with the necessary environment variables. (Refer to readme)"
else
    echo ".env file already exists. Nice!"
fi

echo "Jerry bot environment initialized!"
