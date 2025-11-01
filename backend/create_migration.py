#!/usr/bin/env python3
"""
Script to create initial database migration
"""
import subprocess
import sys

def create_migration():
    try:
        # Create initial migration
        result = subprocess.run([
            "uv", "run", "alembic", "revision", "--autogenerate", 
            "-m", "Create initial tables"
        ], check=True, capture_output=True, text=True)
        
        print("✅ Migration created successfully!")
        print(result.stdout)
        
    except subprocess.CalledProcessError as e:
        print("❌ Failed to create migration:")
        print(e.stderr)
        sys.exit(1)

if __name__ == "__main__":
    create_migration()