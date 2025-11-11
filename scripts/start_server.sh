#!/bin/bash
set -e

# Get environment variables from AWS Systems Manager Parameter Store
# export AWS_ACCESS_KEY_ID=$(aws ssm get-parameter --name "/dietguard/aws/access-key-id" --with-decryption --query 'Parameter.Value' --output text)
# export AWS_SECRET_ACCESS_KEY=$(aws ssm get-parameter --name "/dietguard/aws/secret-access-key" --with-decryption --query 'Parameter.Value' --output text)
# export AWS_REGION=$(aws ssm get-parameter --name "/dietguard/aws/region" --query 'Parameter.Value' --output text)
# export POSTGRES_HOST=$(aws ssm get-parameter --name "/dietguard/postgres/host" --query 'Parameter.Value' --output text)
# export POSTGRES_PORT=$(aws ssm get-parameter --name "/dietguard/postgres/port" --query 'Parameter.Value' --output text)
# export POSTGRES_USER=$(aws ssm get-parameter --name "/dietguard/postgres/user" --query 'Parameter.Value' --output text)
# export POSTGRES_PASSWORD=$(aws ssm get-parameter --name "/dietguard/postgres/password" --with-decryption --query 'Parameter.Value' --output text)
# export POSTGRES_DB=$(aws ssm get-parameter --name "/dietguard/postgres/db" --query 'Parameter.Value' --output text)
# export LANGFUSE_PUBLIC_KEY=$(aws ssm get-parameter --name "/dietguard/langfuse/public-key" --query 'Parameter.Value' --output text)
# export LANGFUSE_SECRET_KEY=$(aws ssm get-parameter --name "/dietguard/langfuse/secret-key" --with-decryption --query 'Parameter.Value' --output text)
# export LANGFUSE_HOST=$(aws ssm get-parameter --name "/dietguard/langfuse/host" --query 'Parameter.Value' --output text)

# Change to application directory
cd /opt/dietguard/backend

# Install dependencies using uv
export PATH="$HOME/.cargo/bin:$PATH"
uv sync

# Stop existing process if running
pkill -f "uvicorn main:app" || true

# Start the application in background
nohup uv run uvicorn main:app --host 0.0.0.0 --port 8080 > /var/log/dietguard.log 2>&1 &

# Save PID for later use
echo $! > /var/run/dietguard.pid

echo "DietGuard backend started successfully"