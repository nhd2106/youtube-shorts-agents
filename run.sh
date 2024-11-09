#!/bin/bash

# Clear the terminal
clear

# Print banner
echo "=== YouTube Shorts Content Generator ==="
echo "Starting up..."
echo

# Set encoding environment variables
export PYTHONIOENCODING=utf-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Run the Python script
echo "Running content generator..."
echo
python3 main.py

# Deactivate virtual environment if it was activated
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi 