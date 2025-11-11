#!/bin/bash
set -e

APP_DIR="/opt/dietguard"
cd "$APP_DIR"

echo "Current directory: $(pwd)"

# Create .env file from AWS Systems Manager parameters
echo "Creating .env file from environment variables..."
cat > .env << EOF
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
AWS_REGION=${AWS_REGION}
INFERENCE_PROFILE_ARN=${INFERENCE_PROFILE_ARN}
INFERENCE_PROFILE_ID=${INFERENCE_PROFILE_ID}
POSTGRES_HOST=${POSTGRES_HOST}
POSTGRES_PORT=${POSTGRES_PORT}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}
CLAUDE_3_7_PROFILE_ARN=${CLAUDE_3_7_PROFILE_ARN}
CLAUDE_3_7_PROFILE_ID=${CLAUDE_3_7_PROFILE_ID}
CLAUDE_4_PROFILE_ARN=${CLAUDE_4_PROFILE_ARN}
CLAUDE_4_PROFILE_ID=${CLAUDE_4_PROFILE_ID}
NOVA_PRO_PROFILE_ARN=${NOVA_PRO_PROFILE_ARN}
NOVA_PRO_INFERENCE_PROFILE_ID=${NOVA_PRO_INFERENCE_PROFILE_ID}
EOF

echo "✓ Environment file created"

# Check if pyproject.toml exists
if [ ! -f "pyproject.toml" ]; then
    echo "ERROR: pyproject.toml not found in $APP_DIR"
    exit 1
fi

# Add uv to PATH
export PATH="/home/ubuntu/.local/bin:/home/ubuntu/.cargo/bin:/usr/local/bin:$PATH"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv not found. Please install uv first."
    exit 1
fi

# Sync dependencies from uv.lock
echo "Syncing dependencies with uv..."
uv sync --frozen

echo "✓ Dependencies installed successfully"