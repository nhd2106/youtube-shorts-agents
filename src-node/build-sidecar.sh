#!/bin/bash
set -e

# Build script for creating a sidecar executable for macOS ARM

echo "Building YouTube Shorts Agent sidecar for macOS ARM..."

# Ensure bin directory exists
mkdir -p bin

# Clean previous builds
rm -rf bin/youtube-shorts-agent-macos-arm64 bin/sidecar-macos

# Build TypeScript
echo "Compiling TypeScript..."
npm run build

# Package with pkg
echo "Packaging application..."
npm run pkg:macos-arm

# Create directory structure for the sidecar
echo "Creating sidecar directory structure..."
mkdir -p bin/sidecar-macos/node_modules

# Copy native modules and other external dependencies that need to be bundled separately
echo "Copying external dependencies..."

# List of external dependencies to copy
EXTERNALS=(
  "@ffmpeg-installer/ffmpeg"
  "fluent-ffmpeg"
  "sharp"
  "node-whisper"
  "nodejs-whisper"
  "whisper-node"
  "axios"
  "@google-cloud/text-to-speech"
  "googleapis"
  "groq-sdk"
  "openai"
  "together-ai"
  "edge-tts"
  "@andresaya/edge-tts"
  "microsoft-cognitiveservices-speech-sdk"
)

# Copy each external dependency
for module in "${EXTERNALS[@]}"; do
  # Handle scoped packages (those starting with @)
  if [[ $module == @* ]]; then
    # Extract scope and package name
    scope=$(echo $module | cut -d'/' -f1)
    package=$(echo $module | cut -d'/' -f2)
    
    if [ -d "node_modules/$scope/$package" ]; then
      mkdir -p "bin/sidecar-macos/node_modules/$scope"
      cp -R "node_modules/$scope/$package" "bin/sidecar-macos/node_modules/$scope/"
      echo "Copied $module"
    fi
  else
    if [ -d "node_modules/$module" ]; then
      mkdir -p "bin/sidecar-macos/node_modules/$module"
      cp -R "node_modules/$module" "bin/sidecar-macos/node_modules/"
      echo "Copied $module"
    fi
  fi
done

# Copy package.json to ensure dependencies are properly recognized
echo "Copying package.json..."
cp package.json bin/sidecar-macos/

# Copy the executable
echo "Copying executable..."
cp bin/youtube-shorts-agent-macos-arm64 bin/sidecar-macos/

# Copy assets and templates
echo "Copying assets and templates..."
if [ -d "assets" ]; then
  mkdir -p bin/sidecar-macos/assets
  cp -R assets bin/sidecar-macos/
fi

if [ -d "templates" ]; then
  mkdir -p bin/sidecar-macos/templates
  cp -R templates bin/sidecar-macos/
fi

# Create a contents directory
mkdir -p bin/sidecar-macos/contents

# Create a Node.js wrapper script
echo "Creating Node.js wrapper script..."
mkdir -p bin/sidecar-macos
cat > bin/sidecar-macos/run-sidecar.js << 'EOL'
#!/usr/bin/env node

/**
 * This is a wrapper script for the YouTube Shorts Agent sidecar.
 * It helps with module resolution and environment setup.
 */

const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

// Get the directory where this script is located
const scriptDir = __dirname;

// Parse command line arguments
const args = process.argv.slice(2);
let port = 3000;

// Look for port argument
const portArg = args.find(arg => arg.startsWith('--port='));
if (portArg) {
  port = parseInt(portArg.split('=')[1], 10);
}

console.log(`Starting YouTube Shorts Agent sidecar on port ${port}...`);

// Set up environment variables
process.env.NODE_PATH = path.join(scriptDir, 'node_modules');
process.env.PATH = `${process.env.PATH}:${scriptDir}`;

// Check if the executable exists
const executablePath = path.join(scriptDir, 'youtube-shorts-agent-macos-arm64');
if (!fs.existsSync(executablePath)) {
  console.error(`Error: Executable not found at ${executablePath}`);
  process.exit(1);
}

// Launch the sidecar process
const sidecarProcess = spawn(executablePath, [`--port=${port}`], {
  cwd: scriptDir,
  stdio: 'inherit',
  env: {
    ...process.env,
    NODE_PATH: path.join(scriptDir, 'node_modules'),
  }
});

// Handle process events
sidecarProcess.on('error', (err) => {
  console.error(`Failed to start sidecar process: ${err.message}`);
  process.exit(1);
});

sidecarProcess.on('close', (code) => {
  console.log(`Sidecar process exited with code ${code}`);
  process.exit(code);
});

// Handle termination signals
process.on('SIGINT', () => {
  console.log('Received SIGINT, shutting down sidecar...');
  sidecarProcess.kill('SIGINT');
});

process.on('SIGTERM', () => {
  console.log('Received SIGTERM, shutting down sidecar...');
  sidecarProcess.kill('SIGTERM');
});
EOL

# Make the wrapper script executable
chmod +x bin/sidecar-macos/run-sidecar.js

# Create a simple README
cat > bin/sidecar-macos/README.md << EOL
# YouTube Shorts Agent Sidecar

This is a packaged version of the YouTube Shorts Agent for use as a sidecar in a Tauri application.

## Usage

The executable can be run directly or launched by the Tauri application.

### Using the Node.js wrapper script (recommended):

\`\`\`
cd sidecar-macos
node run-sidecar.js --port=3000
\`\`\`

### Using the executable directly:

\`\`\`
cd sidecar-macos
./youtube-shorts-agent-macos-arm64 --port=3000
\`\`\`

## Directory Structure

- \`youtube-shorts-agent-macos-arm64\`: The main executable
- \`run-sidecar.js\`: Node.js wrapper script for running the sidecar
- \`node_modules/\`: External dependencies that couldn't be bundled
- \`assets/\`: Static assets
- \`templates/\`: HTML templates
- \`contents/\`: Directory for generated content
- \`package.json\`: Package information for dependency resolution
EOL

# Create a simple startup script
cat > bin/sidecar-macos/start.sh << EOL
#!/bin/bash
# Start the YouTube Shorts Agent sidecar
# Usage: ./start.sh [port]

PORT=\${1:-3000}
echo "Starting YouTube Shorts Agent on port \$PORT..."
node run-sidecar.js --port=\$PORT
EOL

# Make the startup script executable
chmod +x bin/sidecar-macos/start.sh

echo "Creating a zip archive..."
cd bin
zip -r youtube-shorts-agent-sidecar-macos-arm.zip sidecar-macos

echo "Build complete! Sidecar is available at:"
echo "  - bin/sidecar-macos/youtube-shorts-agent-macos-arm64 (executable)"
echo "  - bin/sidecar-macos/run-sidecar.js (Node.js wrapper script)"
echo "  - bin/sidecar-macos/start.sh (startup script)"
echo "  - bin/youtube-shorts-agent-sidecar-macos-arm.zip (packaged sidecar)" 