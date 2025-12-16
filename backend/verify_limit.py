import asyncio
import httpx
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

DATABASE_URL = "postgresql+asyncpg://dietguard:password@localhost/dietguard"

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Signup
        print("1. Signing up...")
        timestamp = int(datetime.now().timestamp())
        email = f"limit_{timestamp}@test.com"
        try:
            resp = await client.post("http://localhost:8000/api/v1/auth/signup", json={
                "email": email,
                "password": "testpassword",
                "firstName": "Limit",
                "lastName": "Test"
            })
            resp.raise_for_status()
            data = resp.json()
            token = data["access_token"]
            user_id = data["user"]["id"]
            print(f"   User created: {user_id}")
        except Exception as e:
            print(f"   Signup failed: {e}")
            if hasattr(e, "response"):
                print(e.response.text)
            return

        # 2. Downgrade to free
        print("2. Downgrading to free tier...")
        engine = create_async_engine(DATABASE_URL)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            await session.execute(text(
                "UPDATE subscriptions SET plan_type = 'free', end_date = NULL WHERE user_id = :uid"
            ), {"uid": user_id})
            
            # 3. Simulate existing usage (2 uploads)
            print("3. Simulating 2 existing uploads...")
            today = datetime.now(timezone.utc).date()
            today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
            
            await session.execute(text("""
                INSERT INTO upload_limits (id, user_id, date, upload_count, created_at, updated_at)
                VALUES (gen_random_uuid(), :uid, :date, 2, now(), now())
            """), {"uid": user_id, "date": today_start})
            await session.commit()
            
        # 4. Attempt upload (Should fail)
        print("4. Attempting 3rd upload (should be blocked)...")
        # dummy file
        with open("dummy.jpg", "wb") as f:
            f.write(os.urandom(100))
            
        files = {"files": ("dummy.jpg", open("dummy.jpg", "rb"), "image/jpeg")}
        form_data = {"meal_time": "lunch"}
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            resp = await client.post(
                "http://localhost:8000/upload_food/", 
                headers=headers, 
                data=form_data, 
                files=files
            )
            
            print(f"   Response Code: {resp.status_code}")
            print(f"   Response Body: {resp.text}")
            
            if resp.status_code == 429:
                print("✅ SUCCESS: Upload blocked with 429 Too Many Requests")
            else:
                print("❌ FAILURE: Upload was not blocked correctly")
                
        except Exception as e:
            print(f"   Upload request failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
