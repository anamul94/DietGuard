#!/bin/bash
set -e

# Update system packages
apt-get update -y

# Install Python 3.11 if not present
if ! command -v python3.11 &> /dev/null; then
    apt-get install -y python3.11 python3.11-pip python3.11-venv curl unzip
fi

# Install uv package manager
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install AWS CLI if not present
if ! command -v aws &> /dev/null; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    ./aws/install
    rm -rf awscliv2.zip aws/
fi

# Create application directory
mkdir -p /opt/dietguard
chown ubuntu:ubuntu /opt/dietguard

echo "Dependencies installed successfully"