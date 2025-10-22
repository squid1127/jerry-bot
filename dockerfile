# Use Python Alpine as base image
FROM python:3.13-alpine

# Set working directory
WORKDIR /app

# Install system dependencies required for the bot
# - git: for installing squid-core from GitHub
# - gcc, musl-dev: for building Python packages
# - libffi-dev: for cryptography and discord.py
# - opus-dev: for voice support
# - ffmpeg: for audio processing (yt-dlp, spotdl)
# - sqlite-dev: for database support
RUN apk add --no-cache \
    git \
    gcc \
    musl-dev \
    libffi-dev \
    opus-dev \
    ffmpeg \
    sqlite-dev

# Install Poetry
RUN pip install --no-cache-dir poetry

# Configure Poetry to not create virtual environments (not needed in container)
RUN poetry config virtualenvs.create false

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
