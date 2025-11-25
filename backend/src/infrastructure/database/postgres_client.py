import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from .database import AsyncSessionLocal
from .models import ReportData, NutritionData
from ..utils.logger import logger

class PostgresClient:
    def __init__(self):
        pass
    
    async def save_report_data(self, user_id: str, data: dict, expiration_hours: int = 24):
        try:
            logger.info("Saving report data", user_id=user_id, expiration_hours=expiration_hours)
            async with AsyncSessionLocal() as session:
                # Delete existing data for user
                await session.execute(delete(ReportData).where(ReportData.user_id == user_id))
                
                # Create new record
                expires_at = datetime.now(timezone.utc) + timedelta(hours=expiration_hours)
                report = ReportData(
                    user_id=user_id,
                    data=json.dumps(data),
                    expires_at=expires_at
                )
                session.add(report)
                await session.commit()
                logger.info("Report data saved successfully", user_id=user_id)
        except Exception as e:
            logger.error("Failed to save report data", user_id=user_id, error=str(e), exception_type=type(e).__name__)
            raise
    
    async def get_report_data(self, user_id: str):
        try:
            logger.debug("Retrieving report data", user_id=user_id)
            async with AsyncSessionLocal() as session:
                # Clean expired records
                deleted_count = await session.execute(delete(ReportData).where(ReportData.expires_at < datetime.now(timezone.utc)))
                if deleted_count.rowcount > 0:
                    logger.debug("Cleaned expired report records", count=deleted_count.rowcount)
                await session.commit()
                
                # Get data
                result = await session.execute(
                    select(ReportData).where(ReportData.user_id == user_id)
                )
                report = result.scalar_one_or_none()
                
                if report and report.expires_at > datetime.now(timezone.utc):
                    logger.info("Report data retrieved successfully", user_id=user_id)
                    return {"data": json.loads(report.data)}
                logger.debug("No report data found or data expired", user_id=user_id)
                return None
        except Exception as e:
            logger.error("Failed to retrieve report data", user_id=user_id, error=str(e), exception_type=type(e).__name__)
            raise
    
    async def save_nutrition_data(self, user_id: str, data: dict, expiration_hours: int = 24):
        try:
            logger.info("Saving nutrition data", user_id=user_id, expiration_hours=expiration_hours)
            async with AsyncSessionLocal() as session:
                # Delete existing data for user
                await session.execute(delete(NutritionData).where(NutritionData.user_id == user_id))
                
                # Create new record
                expires_at = datetime.now(timezone.utc) + timedelta(hours=expiration_hours)
                nutrition = NutritionData(
                    user_id=user_id,
                    data=json.dumps(data),
                    expires_at=expires_at
                )
                session.add(nutrition)
                await session.commit()
                logger.info("Nutrition data saved successfully", user_id=user_id)
        except Exception as e:
            logger.error("Failed to save nutrition data", user_id=user_id, error=str(e), exception_type=type(e).__name__)
            raise
    
    async def get_nutrition_data(self, user_id: str):
        try:
            logger.debug("Retrieving nutrition data", user_id=user_id)
            async with AsyncSessionLocal() as session:
                # Clean expired records
                deleted_count = await session.execute(delete(NutritionData).where(NutritionData.expires_at < datetime.now(timezone.utc)))
                if deleted_count.rowcount > 0:
                    logger.debug("Cleaned expired nutrition records", count=deleted_count.rowcount)
                await session.commit()
                
                # Get data
                result = await session.execute(
                    select(NutritionData).where(NutritionData.user_id == user_id)
                )
                nutrition = result.scalar_one_or_none()
                
                if nutrition and nutrition.expires_at > datetime.now(timezone.utc):
                    logger.info("Nutrition data retrieved successfully", user_id=user_id)
                    return {"data": json.loads(nutrition.data)}
                logger.debug("No nutrition data found or data expired", user_id=user_id)
                return None
        except Exception as e:
            logger.error("Failed to retrieve nutrition data", user_id=user_id, error=str(e), exception_type=type(e).__name__)
            raise
    
    async def delete_report_data(self, user_id: str):
        try:
            logger.info("Deleting report data", user_id=user_id)
            async with AsyncSessionLocal() as session:
                result = await session.execute(delete(ReportData).where(ReportData.user_id == user_id))
                await session.commit()
                deleted = result.rowcount > 0
                if deleted:
                    logger.info("Report data deleted successfully", user_id=user_id)
                else:
                    logger.debug("No report data found to delete", user_id=user_id)
                return deleted
        except Exception as e:
            logger.error("Failed to delete report data", user_id=user_id, error=str(e), exception_type=type(e).__name__)
            raise
    
    async def health_check(self):
        """Check database connectivity"""
        try:
            logger.debug("Database health check started")
            async with AsyncSessionLocal() as session:
                await session.execute(select(1))
                logger.info("Database health check passed")
                return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e), exception_type=type(e).__name__)
            raise