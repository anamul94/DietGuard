#!/bin/bash
set -euo pipefail

echo "Cleaning up old deployment files..."
mkdir -p /usr/share/nginx/html
# Include dotfiles and ignore empty glob
shopt -s dotglob nullglob
rm -rf /usr/share/nginx/html/*
echo "Cleanup complete."
