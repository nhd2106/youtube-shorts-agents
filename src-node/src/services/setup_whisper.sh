#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if Python 3.11 is installed
PYTHON_PATH="/opt/homebrew/opt/python@3.11/bin/python3.11"
if [ ! -f "$PYTHON_PATH" ]; then
    echo "Python 3.11 is not installed. Please install it with: brew install python@3.11"
    exit 1
fi

# Check if pip3 is installed
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is not installed. Please install pip3 first."
    exit 1
fi

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "ffmpeg is not installed. Please install ffmpeg first."
    exit 1
fi

echo "Installing Python dependencies..."

# Remove existing virtual environment if it exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    rm -rf "$SCRIPT_DIR/venv"
fi

# Create and activate virtual environment with Python 3.11
"$PYTHON_PATH" -m venv "$SCRIPT_DIR/venv"
source "$SCRIPT_DIR/venv/bin/activate"

# Ensure the site-packages directory exists with correct permissions
SITE_PACKAGES="$SCRIPT_DIR/venv/lib/python3.11/site-packages"
mkdir -p "$SITE_PACKAGES"
chmod 755 "$SITE_PACKAGES"

# Upgrade pip
pip3 install --upgrade pip

# Install dependencies from requirements.txt
pip3 install -r "$SCRIPT_DIR/requirements.txt"

# Make the Python script executable
chmod +x "$SCRIPT_DIR/whisper_transcribe.py"

echo "Setup completed successfully!"
echo "Virtual environment created at: $SCRIPT_DIR/venv" 