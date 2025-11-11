#!/bin/bash
set -e

# Stop the application process
if [ -f /var/run/dietguard.pid ]; then
    PID=$(cat /var/run/dietguard.pid)
    kill $PID || true
    rm -f /var/run/dietguard.pid
fi

# Kill any remaining uvicorn processes
pkill -f "uvicorn main:app" || true

echo "DietGuard backend stopped successfully"