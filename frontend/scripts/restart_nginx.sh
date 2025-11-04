#!/bin/bash
set -e

echo "Restarting Nginx..."
systemctl restart nginx
systemctl status nginx --no-pager
echo "Nginx restarted successfully."
