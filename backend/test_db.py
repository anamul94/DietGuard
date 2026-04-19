import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.application.services.token_usage_service import TokenUsageService
from src.infrastructure.database.auth_models import User
import src.presentation.api.routes  # To trigger model loads maybe?
# or just import the actual models directly if we know where they are
try:
    from src.infrastructure.database.health_models import PatientPII
except ImportError:
    pass
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def test():
    async with async_session() as db:
        try:
            res = await TokenUsageService.get_daily_token_stats(db, days=30)
            print(res)
        except Exception as e:
            import traceback
            traceback.print_exc()

asyncio.run(test())
