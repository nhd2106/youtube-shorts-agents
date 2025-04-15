#!/bin/bash
# Start the YouTube Shorts Agent sidecar
# Usage: ./start.sh [port]

PORT=${1:-3000}
echo "Starting YouTube Shorts Agent on port $PORT..."
node run-with-system-node.js --port=$PORT 