import json
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from .database import AsyncSessionLocal
from .models import ReportData, NutritionData

class PostgresClient:
    def __init__(self):
        pass
    
    async def save_report_data(self, user_id: str, data: dict, expiration_hours: int = 24):
        async with AsyncSessionLocal() as session:
            # Delete existing data for user
            await session.execute(delete(ReportData).where(ReportData.user_id == user_id))
            
            # Create new record
            expires_at = datetime.utcnow() + timedelta(hours=expiration_hours)
            report = ReportData(
                user_id=user_id,
                data=json.dumps(data),
                expires_at=expires_at
            )
            session.add(report)
            await session.commit()
    
    async def get_report_data(self, user_id: str):
        async with AsyncSessionLocal() as session:
            # Clean expired records
            await session.execute(delete(ReportData).where(ReportData.expires_at < datetime.utcnow()))
            await session.commit()
            
            # Get data
            result = await session.execute(
                select(ReportData).where(ReportData.user_id == user_id)
            )
            report = result.scalar_one_or_none()
            
            if report and report.expires_at > datetime.utcnow():
                return {"data": json.loads(report.data)}
            return None
    
    async def save_nutrition_data(self, user_id: str, data: dict, expiration_hours: int = 24):
        async with AsyncSessionLocal() as session:
            # Delete existing data for user
            await session.execute(delete(NutritionData).where(NutritionData.user_id == user_id))
            
            # Create new record
            expires_at = datetime.utcnow() + timedelta(hours=expiration_hours)
            nutrition = NutritionData(
                user_id=user_id,
                data=json.dumps(data),
                expires_at=expires_at
            )
            session.add(nutrition)
            await session.commit()
    
    async def get_nutrition_data(self, user_id: str):
        async with AsyncSessionLocal() as session:
            # Clean expired records
            await session.execute(delete(NutritionData).where(NutritionData.expires_at < datetime.utcnow()))
            await session.commit()
            
            # Get data
            result = await session.execute(
                select(NutritionData).where(NutritionData.user_id == user_id)
            )
            nutrition = result.scalar_one_or_none()
            
            if nutrition and nutrition.expires_at > datetime.utcnow():
                return {"data": json.loads(nutrition.data)}
            return None
    
    async def delete_report_data(self, user_id: str):
        async with AsyncSessionLocal() as session:
            result = await session.execute(delete(ReportData).where(ReportData.user_id == user_id))
            await session.commit()
            return result.rowcount > 0