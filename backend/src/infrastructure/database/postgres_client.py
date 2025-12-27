import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from .database import AsyncSessionLocal
from .models import ReportData, NutritionData
from ..utils.logger import logger

class PostgresClient:
    def __init__(self):
        pass
    
    async def save_report_data(self, user_id: str, data: dict):
        try:
            logger.info("Saving report data", user_id=user_id)
            async with AsyncSessionLocal() as session:
                # Delete existing data for user
                await session.execute(delete(ReportData).where(ReportData.user_id == user_id))
                
                # Create new record (no expiration)
                report = ReportData(
                    user_id=user_id,
                    data=json.dumps(data),
                    expires_at=None
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
                # Get data (no expiration check)
                result = await session.execute(
                    select(ReportData).where(ReportData.user_id == user_id)
                )
                report = result.scalar_one_or_none()
                
                if report:
                    logger.info("Report data retrieved successfully", user_id=user_id)
                    return {"data": json.loads(report.data)}
                logger.debug("No report data found", user_id=user_id)
                return None
        except Exception as e:
            logger.error("Failed to retrieve report data", user_id=user_id, error=str(e), exception_type=type(e).__name__)
            raise
    
    async def save_nutrition_data(self, user_id: str, data: dict, meal_time=None, meal_date=None):
        try:
            logger.info("Saving nutrition data", user_id=user_id, 
                       meal_time=str(meal_time) if meal_time else None,
                       meal_date=str(meal_date) if meal_date else None)
            async with AsyncSessionLocal() as session:
                # Create new record (append, don't delete existing)
                nutrition = NutritionData(
                    user_id=user_id,
                    data=json.dumps(data),
                    expires_at=None,
                    meal_time=meal_time,
                    meal_date=meal_date
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
                # Get most recent nutrition data (ordered by created_at descending)
                result = await session.execute(
                    select(NutritionData)
                    .where(NutritionData.user_id == user_id)
                    .order_by(NutritionData.created_at.desc())
                )
                nutrition = result.scalars().first()
                
                if nutrition:
                    logger.info("Nutrition data retrieved successfully", user_id=user_id)
                    return {"data": json.loads(nutrition.data)}
                logger.debug("No nutrition data found", user_id=user_id)
                return None
        except Exception as e:
            logger.error("Failed to retrieve nutrition data", user_id=user_id, error=str(e), exception_type=type(e).__name__)
            raise
    
    async def get_nutrition_data_paginated(
        self, 
        user_id: str, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 10
    ):
        """
        Get paginated nutrition data with optional date filtering.
        
        Args:
            user_id: User ID to filter by
            start_date: Optional start date for filtering (inclusive)
            end_date: Optional end date for filtering (inclusive)
            page: Page number (1-indexed)
            page_size: Number of items per page
            
        Returns:
            Dict with items, total_count, page, page_size, total_pages
        """
        try:
            logger.debug("Retrieving paginated nutrition data", 
                        user_id=user_id, 
                        start_date=start_date, 
                        end_date=end_date,
                        page=page,
                        page_size=page_size)
            
            async with AsyncSessionLocal() as session:
                # Build base query
                query = select(NutritionData).where(NutritionData.user_id == user_id)
                
                # Add date filters if provided (filter by meal_date, not created_at)
                if start_date:
                    # Convert datetime to date for comparison with meal_date
                    query = query.where(NutritionData.meal_date >= start_date.date())
                if end_date:
                    # Convert datetime to date for comparison with meal_date
                    query = query.where(NutritionData.meal_date <= end_date.date())
                
                # Order by meal_date and meal_time descending (newest first)
                # Fall back to created_at for records without meal_date
                query = query.order_by(
                    NutritionData.meal_date.desc().nulls_last(),
                    NutritionData.meal_time.desc().nulls_last(),
                    NutritionData.created_at.desc()
                )
                
                # Get total count
                from sqlalchemy import func as sql_func
                count_query = select(sql_func.count()).select_from(query.subquery())
                total_count_result = await session.execute(count_query)
                total_count = total_count_result.scalar()
                
                # Calculate pagination
                offset = (page - 1) * page_size
                total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
                
                # Apply pagination
                query = query.offset(offset).limit(page_size)
                
                # Execute query
                result = await session.execute(query)
                nutrition_records = result.scalars().all()
                
                # Parse and format results
                items = []
                for record in nutrition_records:
                    items.append({
                        "id": record.id,
                        "created_at": record.created_at.isoformat(),
                        "meal_date": record.meal_date.isoformat() if record.meal_date else None,
                        "meal_time": record.meal_time.isoformat() if record.meal_time else None,
                        "data": json.loads(record.data)
                    })
                
                logger.info("Paginated nutrition data retrieved successfully", 
                           user_id=user_id, 
                           total_count=total_count,
                           page=page,
                           items_returned=len(items))
                
                return {
                    "items": items,
                    "total_count": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages
                }
                
        except Exception as e:
            logger.error("Failed to retrieve paginated nutrition data", 
                        user_id=user_id, 
                        error=str(e), 
                        exception_type=type(e).__name__)
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