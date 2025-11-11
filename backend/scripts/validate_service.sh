#!/bin/bash
set -e

# Wait for service to start
sleep 30

# Check if process is running
if ! pgrep -f "uvicorn main:app" > /dev/null; then
    echo "ERROR: DietGuard backend process is not running"
    exit 1
fi

# Check health endpoint
for i in {1..10}; do
    if curl -f http://localhost:8080/health; then
        echo "Health check passed"
        exit 0
    fi
    echo "Health check attempt $i failed, retrying in 10 seconds..."
    sleep 10
done

echo "ERROR: Health check failed after 10 attempts"
exit 1