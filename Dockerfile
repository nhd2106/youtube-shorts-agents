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

# Copy requirements first
COPY requirements.txt .

# Install all dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Verify installations
RUN python -c "import numpy; print(f'numpy version: {numpy.__version__}')"
RUN python -c "import moviepy.editor; print('moviepy successfully installed')"
RUN python -c "import deepfilternet; print('deepfilternet successfully installed')"

# Copy the application code and templates
COPY . .
COPY templates /app/templates

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
