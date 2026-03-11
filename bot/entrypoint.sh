#!/bin/bash
set -e

# Start Xvfb (X Virtual Framebuffer) on display :99
echo "[entrypoint] Starting Xvfb on display :99..."
Xvfb :99 -screen 0 1280x800x24 &
XVFB_PID=$!

# Wait for Xvfb to be ready
sleep 2

# Export DISPLAY environment variable
export DISPLAY=:99

echo "[entrypoint] Xvfb started (PID: $XVFB_PID), DISPLAY=$DISPLAY"

# Execute the main command (bot)
exec "$@"
