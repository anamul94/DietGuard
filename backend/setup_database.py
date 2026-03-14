#!/usr/bin/env python3
"""
Create the current SQLAlchemy tables for local development.

Prefer Alembic migrations for normal setup. This file exists as a fallback for
fresh dev environments and intentionally imports all active model modules before
calling Base.metadata.create_all().
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy.ext.asyncio import create_async_engine

from src.infrastructure.database import auth_models, health_models, patient_models  # noqa: F401
from src.infrastructure.database.database import Base, DATABASE_URL


async def create_tables() -> None:
    try:
        engine = create_async_engine(DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
        print("Database tables created successfully.")
    except Exception as exc:
        print(f"Failed to create tables: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    asyncio.run(create_tables())
