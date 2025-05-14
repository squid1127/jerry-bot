# Use the official Python image from the Docker Hub
FROM python:alpine

# Set the working directory in the container
WORKDIR /app

# Install Alpine build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    libheif-dev \
    python3-dev \
    build-base \
    pkgconfig \
    cargo

# Copy only the requirements files first to leverage Docker cache
COPY ./core/requirements.txt ./core/requirements.txt
COPY requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r ./core/requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run app.py when the container launches
CMD ["python", "app.py"]