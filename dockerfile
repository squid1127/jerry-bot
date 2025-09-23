# Use the official Python image from the Docker Hub
FROM python:alpine

# Set the working directory in the container
WORKDIR /app

# Install Alpine build dependencies
RUN apk add --no-cache \
    build-base \
    gcc g++ make musl-dev \
    libffi-dev openssl-dev pkgconfig \
    libsodium-dev \
    jpeg-dev zlib-dev libpng-dev libwebp-dev tiff-dev freetype-dev \
    libheif-dev \
    file-dev libmagic \
    opus-dev ffmpeg \
    linux-headers
# So yeah i made that with chatgpt there's probably some unnecessary stuff in there
    
# Copy only the requirements files first to leverage Docker cache
COPY ./src/core/requirements.txt ./src/core/requirements.txt
COPY requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r ./src/core/requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run app.py when the container launches
CMD ["python", "src/app.py"]