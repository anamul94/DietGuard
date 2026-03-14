#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

export PATH="$HOME/.local/bin:/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:$PATH"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

echo "Setting up database tables..."
echo "Working directory: $APP_DIR"

cd "$APP_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv not found on PATH. Install uv first." >&2
  exit 1
fi

echo "Running Alembic migrations..."
if uv run alembic upgrade head; then
  echo "Migrations applied successfully."
else
  echo "Alembic migration failed. Falling back to SQLAlchemy table creation..." >&2
  uv run python setup_database.py
fi

echo "Database setup complete."
