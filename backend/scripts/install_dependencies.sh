#!/bin/bash
set -e

APP_DIR="/opt/dietguard"
cd "$APP_DIR"

echo "Current directory: $(pwd)"

# Check if pyproject.toml exists
if [ ! -f "pyproject.toml" ]; then
    echo "ERROR: pyproject.toml not found in $APP_DIR"
    exit 1
fi

echo "Found pyproject.toml"

# Add uv to PATH
export PATH="/home/ubuntu/.local/bin:/home/ubuntu/.cargo/bin:/usr/local/bin:$PATH"

UV_VERSION=$(uv --version)
echo "Using uv version: $UV_VERSION"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv not found. Please install uv first."
    exit 1
fi



# Sync dependencies from uv.lock (respects lock file)
echo "Syncing dependencies with uv..."
uv sync --frozen

echo "✓ Dependencies installed successfully"