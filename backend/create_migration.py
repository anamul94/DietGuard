#!/usr/bin/env python3
"""
Script to create database migration with a custom message.
Usage: uv run python create_migration.py "Your migration message"
"""
import subprocess
import sys


def create_migration(message: str):
    try:
        result = subprocess.run([
            "uv", "run", "alembic", "revision", "--autogenerate",
            "-m", message
        ], check=True, capture_output=True, text=True)
        
        print("✅ Migration created successfully!")
        print(result.stdout)
        
    except subprocess.CalledProcessError as e:
        print("❌ Failed to create migration:")
        print(e.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python create_migration.py \"Your migration message\"")
        sys.exit(1)
    
    message = sys.argv[1]
    create_migration(message)
