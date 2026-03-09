# Use Python Alpine as base image
FROM python:3.13-alpine

# Set working directory
WORKDIR /app

# Install system dependencies required for the bot
# - git: for installing squid-core from GitHub
# - gcc, musl-dev: for building Python packages
# - libffi-dev: for cryptography and discord.py
# - opus-dev: for voice support
# - ffmpeg: for audio processing / voice support
# - sqlite-dev: for database support
# Install and configure poetry w/o a virtual environment
RUN apk add --no-cache \
    git \
    gcc \
    musl-dev \
    libffi-dev \
    opus-dev \
    ffmpeg \
    sqlite-dev \
    && pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false

# Copy dependency files first for better layer caching
COPY pyproject.toml poetry.lock* ./

# Install Python dependencies
RUN poetry install --no-root --no-interaction --no-ansi

# Copy the rest of the application
COPY . .

# Install the project itself
RUN poetry install --only-root --no-interaction --no-ansi

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "run.py"]
