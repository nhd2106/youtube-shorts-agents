FROM python:3.9-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create directories for generated content
RUN mkdir -p generated

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=5123

# Expose the port
EXPOSE ${PORT}

# Run the application
CMD ["python", "app.py"]
