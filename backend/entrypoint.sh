#!/bin/bash
set -e

# 1. Start the internal Docker Daemon in the background
echo "🐳 Starting Docker Daemon..."
dockerd > /var/log/dockerd.log 2>&1 &

# 2. Wait for the Docker Socket to be created (CRITICAL)
# Python needs this file /var/run/docker.sock to connect
echo "⏳ Waiting for Docker to start..."
while [ ! -S /var/run/docker.sock ]; do
  sleep 1
done

# 3. Double check with a command
echo "✅ Docker is UP! Socket found."
docker version

# 4. Start the FastAPI Server
echo "🚀 Starting 0Pirate Backend..."
exec uvicorn server:app --host 0.0.0.0 --port 8080