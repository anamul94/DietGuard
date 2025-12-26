
import asyncio
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database.database import AsyncSessionLocal
from src.application.services.auth_service import AuthService
from src.infrastructure.auth.jwt import create_access_token

async def get_token():
    async with AsyncSessionLocal() as session:
        email = f"debug_{int(time.time())}@example.com"
        password = "TestPassword123!"
        
        # Signup
        try:
            user_data = await AuthService.signup(
                db=session,
                email=email,
                password=password,
                first_name="Debug",
                last_name="User",
                age=30,
                gender="male",
                weight=70.0,
                height=175.0
            )
            user = user_data["user"]
            
            # Generate token (simulating login)
            # We can use the user object directly or login
            token_data = await AuthService.login(session, email, password)
            print(f"TOKEN: {token_data['access_token']}")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(get_token())
