#!/usr/bin/env python3
"""
Script to set up database tables
"""
import subprocess
import sys
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from src.infrastructure.database.database import DATABASE_URL, Base

async def create_tables():
    """Create database tables using SQLAlchemy"""
    try:
        engine = create_async_engine(DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
        print("✅ Database tables created successfully!")
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        sys.exit(1)

def run_migrations():
    """Run Alembic migrations"""
    try:
        result = subprocess.run([
            "uv", "run", "alembic", "upgrade", "head"
        ], check=True, capture_output=True, text=True)
        
        print("✅ Migrations applied successfully!")
        print(result.stdout)
        
    except subprocess.CalledProcessError as e:
        print("❌ Failed to run migrations:")
        print(e.stderr)
        sys.exit(1)

if __name__ == "__main__":
    print("Setting up database...")
    
    # Method 1: Create tables directly
    asyncio.run(create_tables())
    
    # Method 2: Use migrations (optional)
    # run_migrations()