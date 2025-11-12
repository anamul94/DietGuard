#!/bin/bash
# Stop temporary health service
set -e
echo "Stopping temporary health service..."
sudo systemctl stop temp-health || true
sudo systemctl disable temp-health || true
sudo rm -f /etc/systemd/system/temp-health.service
sudo systemctl daemon-reload

# Create application service
sudo tee /etc/systemd/system/dietguard-backend.service > /dev/null <<EOF
[Unit]
Description=DietGuard Backend Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/dietguard
Environment=PORT=8080
# Ensure Python logs are unbuffered so they reach journald immediately
Environment=PYTHONUNBUFFERED=1
# Load environment variables from .env generated during AfterInstall
EnvironmentFile=/opt/dietguard/.env
# Run using the project virtualenv's uvicorn to ensure dependencies are available
ExecStart=/opt/dietguard/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080
StandardOutput=append:/var/log/dietguard-backend.log
StandardError=append:/var/log/dietguard-backend.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Start the backend application service
sudo systemctl daemon-reload
sudo systemctl enable dietguard-backend
sudo systemctl start dietguard-backend

# Wait for application to start
sleep 20

# Verify application is running
for i in {1..10}; do
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        echo "Application started successfully"
        exit 0
    fi
    echo "Waiting for application to start... attempt $i"
    sleep 5
done

echo "Application failed to start, restarting temp service"
# Print service status and recent logs to help diagnose
echo "---- dietguard-backend status ----"
sudo systemctl status dietguard-backend --no-pager || true
echo "---- last 200 dietguard-backend logs ----"
sudo journalctl -u dietguard-backend -n 200 --no-pager || true
sudo systemctl start temp-health
exit 1
