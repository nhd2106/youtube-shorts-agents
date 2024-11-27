FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libsndfile1 \
    libespeak-ng1 \
    espeak-ng \
    python3-pip \
    python3-dev \
    pkg-config \
    libcairo2-dev \
    libgirepository1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    imagemagick \
    git \
    && rm -rf /var/lib/apt/lists/*

# Configure ImageMagick policy
COPY policy.xml /etc/ImageMagick-6/policy.xml

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies in stages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p generated contents/video contents/thumbnail contents/temp

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=5000
ENV PYTHONPATH=/app
ENV IMAGEMAGICK_BINARY=/usr/bin/convert

# Set permissions for generated content directories
RUN chmod -R 777 generated contents

# Expose the port
EXPOSE ${PORT}

# Run the application
CMD ["python", "app.py"]
