#!/bin/bash
# scripts/stop_application.sh

echo "Stopping DietGuard application..."

# Stop the application service if it exists
if systemctl list-unit-files | grep -q dietguard-backend.service; then
    echo "Stopping dietguard-backend service..."
    sudo systemctl stop dietguard-backend
else
    echo "dietguard-backend service not found (normal for first deployment)"
fi

# Stop temporary health service
if systemctl list-unit-files | grep -q temp-health.service; then
    echo "Stopping temporary health service..."
    sudo systemctl stop temp-health
fi

# Kill any processes using port 8080
echo "Cleaning up processes on port 8080..."
sudo pkill -f "python.*8080" || true
sudo pkill -f "node.*8080" || true
sudo pkill -f "temp_health.py" || true

# Wait for cleanup
sleep 5

echo "Application stop completed successfully"