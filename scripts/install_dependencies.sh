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
export PATH="$HOME/.cargo/bin:/home/ubuntu/.cargo/bin:/root/.cargo/bin:$PATH"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv not found. Please install uv first."
    exit 1
fi

UV_VERSION=$(uv --version)
echo "Using uv version: $UV_VERSION"

# Sync dependencies from uv.lock (respects lock file)
echo "Syncing dependencies with uv..."
uv sync --frozen

echo "✓ Dependencies installed successfully"