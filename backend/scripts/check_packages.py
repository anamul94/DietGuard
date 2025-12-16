"""
Check and insert package data.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from src.infrastructure.database.database import AsyncSessionLocal, engine
from src.infrastructure.database.auth_models import Package


async def check_and_insert_packages():
    """Check packages table and insert if empty"""
    
    async with AsyncSessionLocal() as session:
        # Check packages table
        result = await session.execute(select(Package))
        packages = result.scalars().all()
        
        if packages:
            print(f"✓ Found {len(packages)} packages in 'packages' table:")
            for pkg in packages:
                print(f"  - {pkg.name}: ${pkg.price}/{pkg.billing_period} - {pkg.daily_upload_limit} uploads/day")
        else:
            print("⚠ No packages found in 'packages' table. Inserting...")
            
            packages_data = [
                {
                    "name": "Free",
                    "price": 0.00,
                    "billing_period": "free",
                    "daily_upload_limit": 2,
                    "daily_nutrition_limit": 2,
                    "features": {
                        "food_analysis": True,
                        "nutrition_advice": True,
                        "priority_support": False,
                        "advanced_analytics": False
                    },
                    "is_active": True
                },
                {
                    "name": "Monthly",
                    "price": 10.00,
                    "billing_period": "monthly",
                    "daily_upload_limit": 20,
                    "daily_nutrition_limit": 20,
                    "features": {
                        "food_analysis": True,
                        "nutrition_advice": True,
                        "priority_support": True,
                        "advanced_analytics": True
                    },
                    "is_active": True
                },
                {
                    "name": "Yearly",
                    "price": 100.00,
                    "billing_period": "yearly",
                    "daily_upload_limit": 20,
                    "daily_nutrition_limit": 20,
                    "features": {
                        "food_analysis": True,
                        "nutrition_advice": True,
                        "priority_support": True,
                        "advanced_analytics": True,
                        "annual_discount": True
                    },
                    "is_active": True
                }
            ]
            
            for pkg_data in packages_data:
                package = Package(**pkg_data)
                session.add(package)
            
            await session.commit()
            print(f"✓ Inserted {len(packages_data)} packages")
    
    # Check if subscription_packages table exists
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'subscription_packages'
            )
        """))
        exists = result.scalar()
        
        if exists:
            print("\n⚠ Found old 'subscription_packages' table")
            print("  This table is deprecated. Using 'packages' table instead.")
        else:
            print("\n✓ No 'subscription_packages' table found (correct)")


if __name__ == "__main__":
    print("Checking package data...\n")
    asyncio.run(check_and_insert_packages())
    print("\nDone!")
