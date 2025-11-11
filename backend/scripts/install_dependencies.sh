#!/bin/bash
set -e

APP_DIR="/opt/dietguard"
cd "$APP_DIR"

echo "Current directory: $(pwd)"

# Resolve AWS CLI and region for SSM access
if ! command -v aws >/dev/null 2>&1; then
    echo "ERROR: aws CLI not found. Install AWS CLI v2 on the instance."
    exit 1
fi

# Prefer provided region, fallback to ap-south-1
REGION="${AWS_REGION:-ap-south-1}"
PARAM_PREFIX="/foodapp/backend"

echo "Using AWS region: $REGION"

fetch_param() {
  local name="$1"
  aws ssm get-parameter \
    --name "$name" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text \
    --region "$REGION" 2>/dev/null || true
}

echo "Fetching parameters from SSM Parameter Store..."

# Fetch each parameter with fallback to any pre-set env var
AWS_ACCESS_KEY_ID_VAL=$(fetch_param "$PARAM_PREFIX/AWS_ACCESS_KEY_ID");        AWS_ACCESS_KEY_ID_VAL=${AWS_ACCESS_KEY_ID_VAL:-${AWS_ACCESS_KEY_ID:-}}
AWS_SECRET_ACCESS_KEY_VAL=$(fetch_param "$PARAM_PREFIX/AWS_SECRET_ACCESS_KEY");AWS_SECRET_ACCESS_KEY_VAL=${AWS_SECRET_ACCESS_KEY_VAL:-${AWS_SECRET_ACCESS_KEY:-}}
AWS_REGION_VAL=$(fetch_param "$PARAM_PREFIX/AWS_REGION");                      AWS_REGION_VAL=${AWS_REGION_VAL:-${AWS_REGION:-$REGION}}

INFERENCE_PROFILE_ARN_VAL=$(fetch_param "$PARAM_PREFIX/INFERENCE_PROFILE_ARN");INFERENCE_PROFILE_ARN_VAL=${INFERENCE_PROFILE_ARN_VAL:-${INFERENCE_PROFILE_ARN:-}}
INFERENCE_PROFILE_ID_VAL=$(fetch_param "$PARAM_PREFIX/INFERENCE_PROFILE_ID");  INFERENCE_PROFILE_ID_VAL=${INFERENCE_PROFILE_ID_VAL:-${INFERENCE_PROFILE_ID:-}}

POSTGRES_HOST_VAL=$(fetch_param "$PARAM_PREFIX/POSTGRES_HOST");                POSTGRES_HOST_VAL=${POSTGRES_HOST_VAL:-${POSTGRES_HOST:-}}
POSTGRES_PORT_VAL=$(fetch_param "$PARAM_PREFIX/POSTGRES_PORT");                POSTGRES_PORT_VAL=${POSTGRES_PORT_VAL:-${POSTGRES_PORT:-}}
POSTGRES_USER_VAL=$(fetch_param "$PARAM_PREFIX/POSTGRES_USER");                POSTGRES_USER_VAL=${POSTGRES_USER_VAL:-${POSTGRES_USER:-}}
POSTGRES_PASSWORD_VAL=$(fetch_param "$PARAM_PREFIX/POSTGRES_PASSWORD");        POSTGRES_PASSWORD_VAL=${POSTGRES_PASSWORD_VAL:-${POSTGRES_PASSWORD:-}}
POSTGRES_DB_VAL=$(fetch_param "$PARAM_PREFIX/POSTGRES_DB");                    POSTGRES_DB_VAL=${POSTGRES_DB_VAL:-${POSTGRES_DB:-}}

CLAUDE_3_7_PROFILE_ARN_VAL=$(fetch_param "$PARAM_PREFIX/CLAUDE_3_7_PROFILE_ARN");CLAUDE_3_7_PROFILE_ARN_VAL=${CLAUDE_3_7_PROFILE_ARN_VAL:-${CLAUDE_3_7_PROFILE_ARN:-}}
CLAUDE_3_7_PROFILE_ID_VAL=$(fetch_param "$PARAM_PREFIX/CLAUDE_3_7_PROFILE_ID");  CLAUDE_3_7_PROFILE_ID_VAL=${CLAUDE_3_7_PROFILE_ID_VAL:-${CLAUDE_3_7_PROFILE_ID:-}}
CLAUDE_4_PROFILE_ARN_VAL=$(fetch_param "$PARAM_PREFIX/CLAUDE_4_PROFILE_ARN");    CLAUDE_4_PROFILE_ARN_VAL=${CLAUDE_4_PROFILE_ARN_VAL:-${CLAUDE_4_PROFILE_ARN:-}}
CLAUDE_4_PROFILE_ID_VAL=$(fetch_param "$PARAM_PREFIX/CLAUDE_4_PROFILE_ID");      CLAUDE_4_PROFILE_ID_VAL=${CLAUDE_4_PROFILE_ID_VAL:-${CLAUDE_4_PROFILE_ID:-}}
NOVA_PRO_PROFILE_ARN_VAL=$(fetch_param "$PARAM_PREFIX/NOVA_PRO_PROFILE_ARN");    NOVA_PRO_PROFILE_ARN_VAL=${NOVA_PRO_PROFILE_ARN_VAL:-${NOVA_PRO_PROFILE_ARN:-}}
NOVA_PRO_INFERENCE_PROFILE_ID_VAL=$(fetch_param "$PARAM_PREFIX/NOVA_PRO_INFERENCE_PROFILE_ID"); NOVA_PRO_INFERENCE_PROFILE_ID_VAL=${NOVA_PRO_INFERENCE_PROFILE_ID_VAL:-${NOVA_PRO_INFERENCE_PROFILE_ID:-}}

# Create .env with fetched values
echo "Writing .env file..."
cat > .env << EOF
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID_VAL}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY_VAL}
AWS_REGION=${AWS_REGION_VAL}
INFERENCE_PROFILE_ARN=${INFERENCE_PROFILE_ARN_VAL}
INFERENCE_PROFILE_ID=${INFERENCE_PROFILE_ID_VAL}
POSTGRES_HOST=${POSTGRES_HOST_VAL}
POSTGRES_PORT=${POSTGRES_PORT_VAL}
POSTGRES_USER=${POSTGRES_USER_VAL}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD_VAL}
POSTGRES_DB=${POSTGRES_DB_VAL}
CLAUDE_3_7_PROFILE_ARN=${CLAUDE_3_7_PROFILE_ARN_VAL}
CLAUDE_3_7_PROFILE_ID=${CLAUDE_3_7_PROFILE_ID_VAL}
CLAUDE_4_PROFILE_ARN=${CLAUDE_4_PROFILE_ARN_VAL}
CLAUDE_4_PROFILE_ID=${CLAUDE_4_PROFILE_ID_VAL}
NOVA_PRO_PROFILE_ARN=${NOVA_PRO_PROFILE_ARN_VAL}
NOVA_PRO_INFERENCE_PROFILE_ID=${NOVA_PRO_INFERENCE_PROFILE_ID_VAL}
EOF

chmod 600 .env || true
echo "✓ .env created from SSM parameters"

# Check if pyproject.toml exists
if [ ! -f "pyproject.toml" ]; then
    echo "ERROR: pyproject.toml not found in $APP_DIR"
    exit 1
fi

# Ensure uv is discoverable on PATH (covers typical locations)
export PATH="$HOME/.local/bin:/home/ubuntu/.local/bin:$HOME/.cargo/bin:/home/ubuntu/.cargo/bin:/usr/local/bin:/usr/bin:$PATH"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv not found. Please install uv first."
    exit 1
fi

# Log uv path and version for diagnostics
echo "Using uv at: $(command -v uv)"
uv --version
# Sync dependencies from uv.lock
echo "Syncing dependencies with uv..."
uv sync --frozen

echo "✓ Dependencies installed successfully"
