#!/bin/bash
set -euo pipefail

echo "Restarting Nginx..."
# Prefer reload, fallback to restart
if ! systemctl reload nginx; then
  systemctl restart nginx
fi
# Verify service is active
systemctl is-active --quiet nginx

echo "Nginx restarted successfully."
