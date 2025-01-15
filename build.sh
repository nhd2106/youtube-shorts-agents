#!/bin/bash

# Install OpenSSL if not already installed
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

if ! brew list openssl &> /dev/null; then
    echo "Installing OpenSSL..."
    brew install openssl@3
fi

# Clean previous builds
rm -rf build dist

# Create virtual environment if it doesn't exist
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install base requirements first
pip install numpy
pip install Pillow
pip install flask flask-cors python-dotenv

# Install PyInstaller and additional dependencies
pip install pyinstaller
pip install cryptography
pip install pyOpenSSL

# Install remaining requirements (excluding problematic packages)
pip install -r <(grep -v "torch\|openai-whisper" requirements.txt)

# Set OpenSSL environment variables
export LDFLAGS="-L/opt/homebrew/opt/openssl@3/lib"
export CPPFLAGS="-I/opt/homebrew/opt/openssl@3/include"
export PKG_CONFIG_PATH="/opt/homebrew/opt/openssl@3/lib/pkgconfig"
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/openssl@3/lib:$DYLD_LIBRARY_PATH"

# Create necessary directories
mkdir -p templates static

# Create a minimal .env file if it doesn't exist
if [ ! -f .env ]; then
    touch .env
fi

# Build the application
echo "Building for Apple Silicon..."
pyinstaller app.spec --clean

# Rename for Tauri sidecar compatibility
if [ -f "dist/youtube-shorts-agent" ]; then
    mv "dist/youtube-shorts-agent" "dist/youtube-shorts-agent-aarch64-apple-darwin"
    echo "Build complete! The executable is at: dist/youtube-shorts-agent-aarch64-apple-darwin"
else
    echo "Error: Build failed or executable not found"
    exit 1
fi