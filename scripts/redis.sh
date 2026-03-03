#!/bin/bash

# Simple script to run ephemeral Redis server with docker
docker run --rm -d -p 6379:6379 redis:latest