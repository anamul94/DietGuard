import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

class Base(DeclarativeBase):
    pass

# Database configuration
# Use DATABASE_URL if provided, otherwise construct from individual variables
DATABASE_URL = os.getenv('DATABASE_URL') or (
    f"postgresql+asyncpg://"
    f"{os.getenv('POSTGRES_USER', 'dietguard')}:"
    f"{os.getenv('POSTGRES_PASSWORD', 'dietguard123')}@"
    f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
    f"{os.getenv('POSTGRES_PORT', '5432')}/"
    f"{os.getenv('POSTGRES_DB', 'dietguard')}"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()