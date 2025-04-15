#!/usr/bin/env node

/**
 * This is a wrapper script for the YouTube Shorts Agent sidecar.
 * It uses the system's Node.js instead of the bundled one.
 */

const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");

// Get the directory where this script is located
const scriptDir = __dirname;

// Parse command line arguments
const args = process.argv.slice(2);
let port = 3000;

// Look for port argument
const portArg = args.find((arg) => arg.startsWith("--port="));
if (portArg) {
  port = parseInt(portArg.split("=")[1], 10);
}

console.log(`Starting YouTube Shorts Agent sidecar on port ${port}...`);

// Check if the dist directory exists in the parent directory
const distDir = path.join(scriptDir, "..", "..", "dist");
if (!fs.existsSync(distDir)) {
  console.error(`Error: dist directory not found at ${distDir}`);
  process.exit(1);
}

// Set up environment variables
process.env.NODE_PATH = path.join(scriptDir, "node_modules");
process.env.PATH = `${process.env.PATH}:${scriptDir}`;

// Start the server using the system's Node.js
const appPath = path.join(distDir, "app.js");
if (!fs.existsSync(appPath)) {
  console.error(`Error: app.js not found at ${appPath}`);
  process.exit(1);
}

console.log(`Using app.js at: ${appPath}`);
console.log(`Using node_modules at: ${process.env.NODE_PATH}`);

// Launch the server process
const serverProcess = spawn("node", [appPath, `--port=${port}`], {
  cwd: scriptDir,
  stdio: "inherit",
  env: {
    ...process.env,
    PORT: port.toString(),
  },
});

// Handle process events
serverProcess.on("error", (err) => {
  console.error(`Failed to start server process: ${err.message}`);
  process.exit(1);
});

serverProcess.on("close", (code) => {
  console.log(`Server process exited with code ${code}`);
  process.exit(code);
});

// Handle termination signals
process.on("SIGINT", () => {
  console.log("Received SIGINT, shutting down server...");
  serverProcess.kill("SIGINT");
});

process.on("SIGTERM", () => {
  console.log("Received SIGTERM, shutting down server...");
  serverProcess.kill("SIGTERM");
});
