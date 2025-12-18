#!/bin/bash

# Fix PostgreSQL authentication issue
# This script removes the old volume and recreates the database with correct credentials

echo "🔧 Fixing PostgreSQL authentication issue..."
echo ""
echo "This will:"
echo "  1. Stop all containers"
echo "  2. Remove the postgres volume (⚠️  deletes all data)"
echo "  3. Restart with fresh database"
echo ""
read -p "Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Cancelled"
    exit 1
fi

echo ""
echo "Step 1: Stopping containers..."
docker compose down

echo ""
echo "Step 2: Removing postgres volume..."
docker volume rm dietguard_postgres_data 2>/dev/null || echo "Volume already removed or doesn't exist"

echo ""
echo "Step 3: Starting fresh..."
docker compose up -d

echo ""
echo "Step 4: Waiting for database to be ready..."
sleep 10

echo ""
echo "Step 5: Running migrations..."
docker compose exec backend uv run alembic upgrade head

echo ""
echo "Step 6: Seeding packages..."
docker compose exec backend uv run python scripts/seed_packages.py

echo ""
echo "✅ Done! Database recreated with correct credentials."
echo ""
echo "Services:"
echo "  Backend: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
