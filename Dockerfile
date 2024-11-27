FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages in stages to optimize caching
COPY requirements.txt .

# Install dependencies with pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create directories for generated content
RUN mkdir -p generated

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Expose the port
EXPOSE ${PORT}

# Run the application
CMD ["python", "app.py"]
