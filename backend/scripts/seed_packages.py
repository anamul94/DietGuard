"""
Seed initial subscription packages.

Run this script to populate the subscription_packages table with default packages.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from src.infrastructure.database.database import AsyncSessionLocal
from src.infrastructure.database.auth_models import Package


async def seed_packages():
    """Seed initial subscription packages"""
    
    packages = [
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
    
    async with AsyncSessionLocal() as session:
        # Check if packages already exist
        result = await session.execute(select(Package))
        existing = result.scalars().all()
        
        if existing:
            print(f"✓ Packages already exist ({len(existing)} packages found)")
            for pkg in existing:
                print(f"  - {pkg.name}: ${pkg.price}/{pkg.billing_period}")
            return
        
        # Create packages
        for pkg_data in packages:
            package = Package(**pkg_data)
            session.add(package)
        
        await session.commit()
        print(f"✓ Successfully seeded {len(packages)} subscription packages:")
        for pkg in packages:
            print(f"  - {pkg['name']}: ${pkg['price']}/{pkg['billing_period']} - {pkg['daily_upload_limit']} uploads/day")


if __name__ == "__main__":
    print("Seeding subscription packages...")
    asyncio.run(seed_packages())
    print("Done!")
