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
    zlib1g-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Configure ImageMagick policy
COPY policy.xml /etc/ImageMagick-6/policy.xml

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install core dependencies first
RUN pip install --no-cache-dir \
    numpy==1.21.0 \
    decorator==4.4.2 \
    imageio==2.31.1 \
    imageio-ffmpeg==0.4.8 \
    proglog==0.1.10 \
    tqdm==4.65.0 \
    requests==2.31.0

# Install moviepy separately
RUN pip install --no-cache-dir moviepy==1.0.3

# Copy requirements and install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and templates
COPY . .
COPY templates /app/templates

# Create necessary directories
RUN mkdir -p generated contents/video contents/thumbnail contents/temp

# Verify moviepy installation
RUN python -c "from moviepy.editor import *; print('MoviePy successfully installed')"

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
