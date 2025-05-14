# Use the official Python image from the Docker Hub
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Install build dependencies and ffmpeg, then clean up
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    python3-dev \
    libffi-dev \
    libheif-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements files first to leverage Docker cache
COPY ./core/requirements.txt ./core/requirements.txt
COPY requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r ./core/requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run app.py when the container launches
CMD ["python", "app.py"]