"""
Add package_id column to subscriptions table via raw SQL.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.infrastructure.database.database import engine


async def add_column():
    """Add package_id column"""
    
    async with engine.begin() as conn:
        try:
            # Add column
            await conn.execute(text("""
                ALTER TABLE subscriptions 
                ADD COLUMN package_id UUID
            """))
            print("✓ Added package_id column")
        except Exception as e:
            if "already exists" in str(e):
                print("✓ package_id column already exists")
            else:
                raise
        
        try:
            # Add foreign key
            await conn.execute(text("""
                ALTER TABLE subscriptions
                ADD CONSTRAINT fk_subscriptions_package_id
                FOREIGN KEY (package_id) REFERENCES packages(id)
            """))
            print("✓ Added foreign key constraint")
        except Exception as e:
            if "already exists" in str(e):
                print("✓ Foreign key already exists")
            else:
                raise
        
        try:
            # Add index
            await conn.execute(text("""
                CREATE INDEX ix_subscriptions_package_id 
                ON subscriptions(package_id)
            """))
            print("✓ Added index")
        except Exception as e:
            if "already exists" in str(e):
                print("✓ Index already exists")
            else:
                raise


if __name__ == "__main__":
    print("Adding package_id column to subscriptions...")
    asyncio.run(add_column())
    print("Done!")
