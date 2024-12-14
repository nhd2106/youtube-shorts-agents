# Use Python 3.9 slim base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libsndfile1 \
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
    libsndfile1-dev \
    libportaudio2 \
    portaudio19-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Configure ImageMagick policy if the file exists
COPY policy.xml /etc/ImageMagick-6/policy.xml

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install core Python dependencies
RUN pip install --no-cache-dir \
    "numpy>=1.22.0,<2.0.0" \
    decorator>=4.4.2 \
    imageio>=2.9.0 \
    imageio-ffmpeg>=0.4.5 \
    tqdm>=4.64.1 \
    requests>=2.31.0 \
    Pillow>=9.5.0 \
    proglog>=0.1.10 \
    moviepy==1.0.3

# Install audio processing dependencies
RUN pip install --no-cache-dir \
    soundfile>=0.12.1 \
    librosa>=0.10.1

# Verify key installations
RUN python -c "import moviepy; print('MoviePy version:', moviepy.__version__)" && \
    python -c "import soundfile as sf; print('soundfile successfully installed')"

# Install application-specific dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
COPY templates /app/templates

# Create necessary directories with appropriate permissions
RUN mkdir -p \
    generated \
    contents/video \
    contents/thumbnail \
    contents/temp && \
    chmod -R 777 generated contents

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=5123 \
    PYTHONPATH=/app \
    IMAGEMAGICK_BINARY=/usr/bin/convert \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    PYTHONDOWNWRITEBUFFERSIZE=65536 \
    PYTHONMALLOC=debug

# Expose port
EXPOSE 5123

# Install gunicorn
RUN pip install --no-cache-dir gunicorn

# Add a script to run gunicorn with memory-optimized settings
RUN echo '#!/bin/bash\n\
exec gunicorn \
    --bind 0.0.0.0:5123 \
    --workers 2 \
    --threads 1 \
    --timeout 300 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    --log-level info \
    app:app' > /app/start.sh && \
    chmod +x /app/start.sh

# Set the default command to run the application
CMD ["/app/start.sh"]
