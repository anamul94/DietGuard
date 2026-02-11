"""
Seed initial roles.

Run this script to populate the roles table with default roles.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from src.infrastructure.database.database import AsyncSessionLocal
from src.infrastructure.database.auth_models import Role
# Import patient models to register them with SQLAlchemy
from src.infrastructure.database import patient_models  # noqa: F401


async def seed_roles():
    """Seed initial roles"""
    
    roles = [
        {
            "name": "user",
            "description": "Regular user with standard access"
        },
        {
            "name": "admin",
            "description": "Administrator with full access"
        }
    ]
    
    async with AsyncSessionLocal() as session:
        # Check if roles already exist
        result = await session.execute(select(Role))
        existing = result.scalars().all()
        
        if existing:
            print(f"✓ Roles already exist ({len(existing)} roles found)")
            for role in existing:
                print(f"  - {role.name}: {role.description}")
            return
        
        # Create roles
        for role_data in roles:
            role = Role(**role_data)
            session.add(role)
        
        await session.commit()
        print(f"✓ Successfully seeded {len(roles)} roles:")
        for role in roles:
            print(f"  - {role['name']}: {role['description']}")


if __name__ == "__main__":
    print("Seeding roles...")
    asyncio.run(seed_roles())
    print("Done!")
