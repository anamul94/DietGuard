"""
Test signup with 7-day trial.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database.database import AsyncSessionLocal
from src.application.services.auth_service import AuthService


async def test_signup():
    """Test signup creates user with 7-day paid trial"""
    
    async with AsyncSessionLocal() as session:
        # Test signup
        result = await AuthService.signup(
            db=session,
            email=f"testuser_{asyncio.get_event_loop().time()}@example.com",
            password="TestPassword123!",
            first_name="Test",
            last_name="User",
            age=25,
            gender="male",
            weight=70.0,
            height=175.0
        )
        
        print("✓ Signup successful!")
        print(f"\nUser Info:")
        print(f"  Email: {result['user']['email']}")
        print(f"  Name: {result['user']['first_name']} {result['user']['last_name']}")
        print(f"\nSubscription Info:")
        print(f"  Type: {result['user']['subscription']['type']}")
        print(f"  Status: {result['user']['subscription']['status']}")
        print(f"  Is Paid: {result['user']['subscription']['is_paid']}")
        print(f"  Trial Ends: {result['user']['subscription'].get('trial_ends_at', 'N/A')}")
        print(f"  Package: {result['user']['subscription']['package']['name']}")
        print(f"  Daily Upload Limit: {result['user']['subscription']['package']['daily_upload_limit']}")
        print(f"  Daily Nutrition Limit: {result['user']['subscription']['package']['daily_nutrition_limit']}")


if __name__ == "__main__":
    print("Testing signup with 7-day trial...\n")
    asyncio.run(test_signup())
    print("\n✓ Test complete!")
