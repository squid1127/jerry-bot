# Use the official Python image from the Docker Hub
FROM python:3.12.1-slim

# Set the working directory in the container
WORKDIR /app

# Copy only the requirements files first to leverage Docker cache
COPY ./core/requirements.txt ./core/requirements.txt
COPY requirements.txt requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r ./core/requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Install ffmpeg and clean up apt cache to reduce image size
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Run app.py when the container launches
CMD ["python", "app.py"]