#!/usr/bin/env bash
# Setting up the development environment for squid-core

# Check if poetry is installed
if ! command -v poetry &> /dev/null
then
    echo "Poetry could not be found. Please install Poetry first."
    exit 1
fi

# Install with poetry
poetry install