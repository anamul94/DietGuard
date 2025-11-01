#!/bin/bash

# Source backend URL environment
source /opt/dietguard/backend_url.env

# Update Nginx configuration with backend URL
sed -i "s|http://backend-alb-url/|${BACKEND_URL}|g" /etc/nginx/sites-available/dietguard

# Test and reload Nginx
nginx -t && systemctl reload nginx