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
    libsndfile1-dev \
    libportaudio2 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Configure ImageMagick policy
COPY policy.xml /etc/ImageMagick-6/policy.xml

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install core dependencies first
RUN pip install --no-cache-dir "numpy>=1.22.0,<2.0.0" && \
    pip install --no-cache-dir decorator>=4.4.2 imageio>=2.9.0 imageio-ffmpeg>=0.4.5 && \
    pip install --no-cache-dir tqdm>=4.64.1 requests>=2.31.0 Pillow>=9.5.0 proglog>=0.1.10 && \
    pip install --no-cache-dir moviepy==1.0.3 && \
    rm -rf /root/.cache/pip/*

# Install audio processing dependencies
RUN pip install --no-cache-dir  librosa>=0.10.1 && \
    rm -rf /root/.cache/pip/*

# Verify installations
RUN python -c "import moviepy; from moviepy.editor import VideoFileClip; print('MoviePy version:', moviepy.__version__)"
RUN python -c "import soundfile as sf; print('soundfile successfully installed')"

# Copy requirements and install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip/*

# Copy the application code and templates
COPY . .
COPY templates /app/templates

# Create necessary directories
RUN mkdir -p generated contents/video contents/thumbnail contents/temp

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=5123
ENV PYTHONPATH=/app
ENV IMAGEMAGICK_BINARY=/usr/bin/convert
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
# Memory optimization
ENV PYTHONDOWNWRITEBUFFERSIZE=65536
ENV PYTHONMALLOC=debug

# Set permissions for generated content directories
RUN chmod -R 777 generated contents

# Expose port (TCP only is sufficient)
EXPOSE 5123

# Install gunicorn
RUN pip install --no-cache-dir gunicorn

# Create a script to run gunicorn with memory limits
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

# Run the application with memory-optimized settings
CMD ["/app/start.sh"]
