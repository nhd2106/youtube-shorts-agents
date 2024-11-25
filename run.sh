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

# Set Flask environment variables
export FLASK_APP=app.py
export FLASK_ENV=development  # Use 'production' in production environment

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

# Run the Flask application
echo "Running Flask server..."
echo
python3 app.py

# Deactivate virtual environment if it was activated
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi 