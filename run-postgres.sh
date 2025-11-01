#!/bin/bash

# Run PostgreSQL in Docker with custom user and database
docker run -d \
  --name dietguard-postgres \
  -e POSTGRES_USER=dietguard \
  -e POSTGRES_PASSWORD=dietguard123 \
  -e POSTGRES_DB=dietguard \
  -p 5432:5436 \
  -v dietguard_postgres_data:/var/lib/postgresql/data \
  postgres:15-alpine

echo "PostgreSQL container started!"
echo "Connection details:"
echo "Host: localhost"
echo "Port: 5432"
echo "Database: dietguard"
echo "User: dietguard"
echo "Password: dietguard123"