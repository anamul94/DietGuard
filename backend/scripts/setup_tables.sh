#!/bin/bash
set -euo pipefail

APP_DIR="/opt/dietguard"
echo "Setting up database tables..."

# Ensure uv is on PATH
export PATH="$HOME/.local/bin:/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:$PATH"

cd "$APP_DIR"
echo "Working directory: $(pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv not found on PATH. Install uv first."
  exit 1
fi

echo "Running Alembic migrations (upgrade head)..."
set +e
UV_OUT=$(uv run alembic upgrade head 2>&1)
STATUS=$?
set -e

if [ $STATUS -ne 0 ]; then
  echo "Alembic migration failed. Output:" >&2
  echo "$UV_OUT" >&2
  echo "Falling back to creating tables via SQLAlchemy metadata..."
  uv run python setup_database.py
else
  echo "Migrations applied successfully."
fi

echo "Database setup complete."

