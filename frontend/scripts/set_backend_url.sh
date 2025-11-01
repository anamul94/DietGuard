#!/bin/bash

# Create directory and environment file for backend URL
mkdir -p /opt/dietguard
echo "BACKEND_URL=${BACKEND_URL}" > /opt/dietguard/backend_url.env