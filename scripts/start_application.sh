#!/bin/bash
# Start the backend application service
sudo systemctl daemon-reload
sudo systemctl start dietguard-backend
sudo systemctl enable dietguard-backend

# Wait for application to start
sleep 10

# Verify application is running
if ! curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "Application health check failed"
    exit 1
fi

echo "Application started successfully"