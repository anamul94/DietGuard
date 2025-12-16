from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime, date, timezone
from typing import Optional, Dict, Any

from ...infrastructure.database.auth_models import User, Subscription, UploadLimit
from ...infrastructure.utils.logger import logger
from ...infrastructure.config.settings import settings

class SubscriptionService:
    """Service for subscription and upload limit management"""
    
    @staticmethod
    async def get_active_subscription(db: AsyncSession, user_id: str) -> Optional[Subscription]:
        """
        Get user's active subscription.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Active subscription or None
        """
        result = await db.execute(
            select(Subscription).where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.status == "active"
                )
            ).order_by(Subscription.created_at.desc())
        )
        subscription = result.scalar_one_or_none()
        
        # Check if paid trial has expired
        if subscription and subscription.plan_type == "paid" and subscription.end_date:
            if subscription.end_date < datetime.now(timezone.utc):
                # Trial expired, convert to free tier
                subscription.plan_type = "free"
                subscription.end_date = None
                await db.commit()
                logger.info("Trial expired, converted to free tier", user_id=str(user_id))
        
        return subscription
    
    @staticmethod
    async def check_upload_limit(db: AsyncSession, user: User) -> Dict[str, Any]:
        """
        Check if user can upload based on their subscription and daily limits.
        
        Args:
            db: Database session
            user: User object
            
        Returns:
            Dict with can_upload, remaining_uploads, plan_type
            
        Raises:
            ValueError: If limit exceeded
        """
        # Get active subscription
        subscription = await SubscriptionService.get_active_subscription(db, user.id)
        
        if not subscription:
            raise ValueError("No active subscription found")
        
        # Paid users have unlimited uploads
        if subscription.plan_type == "paid":
            return {
                "can_upload": True,
                "remaining_uploads": -1,  # -1 indicates unlimited
                "plan_type": "paid"
            }
        
        # Free users: check daily limit
        today = datetime.now(timezone.utc).date()
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        
        # Get or create today's upload limit record
        result = await db.execute(
            select(UploadLimit).where(
                and_(
                    UploadLimit.user_id == user.id,
                    func.date(UploadLimit.date) == today
                )
            )
        )
        upload_limit = result.scalar_one_or_none()
        
        if not upload_limit:
            upload_limit = UploadLimit(
                user_id=user.id,
                date=today_start,
                upload_count=0,
                nutrition_analysis_count=0
            )
            db.add(upload_limit)
            await db.flush()
        
        # Check limit
        max_uploads = settings.FREE_TIER_DAILY_UPLOAD_LIMIT
        remaining = max_uploads - upload_limit.upload_count
        
        if upload_limit.upload_count >= max_uploads:
            logger.warning(
                "Upload limit exceeded",
                user_id=str(user.id),
                current_count=upload_limit.upload_count,
                max_uploads=max_uploads
            )
            raise ValueError(f"Daily upload limit exceeded. Free tier allows {max_uploads} uploads per day.")
        
        return {
            "can_upload": True,
            "remaining_uploads": remaining,
            "plan_type": "free",
            "current_count": upload_limit.upload_count,
            "max_uploads": max_uploads
        }
    
    @staticmethod
    async def increment_upload_count(db: AsyncSession, user: User) -> None:
        """
        Increment user's upload count for today.
        
        Args:
            db: Database session
            user: User object
        """
        today = datetime.now(timezone.utc).date()
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        
        # Get or create today's upload limit record
        result = await db.execute(
            select(UploadLimit).where(
                and_(
                    UploadLimit.user_id == user.id,
                    func.date(UploadLimit.date) == today
                )
            )
        )
        upload_limit = result.scalar_one_or_none()
        
        if not upload_limit:
            upload_limit = UploadLimit(
                user_id=user.id,
                date=today_start,
                upload_count=1,
                nutrition_analysis_count=0
            )
            db.add(upload_limit)
        else:
            upload_limit.upload_count += 1
            upload_limit.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        logger.info(
            "Upload count incremented",
            user_id=str(user.id),
            new_count=upload_limit.upload_count
        )
    
    @staticmethod
    async def check_nutrition_limit(db: AsyncSession, user: User) -> Dict[str, Any]:
        """
        Check if user can request nutrition analysis based on their subscription and daily limits.
        
        Args:
            db: Database session
            user: User object
            
        Returns:
            Dict with can_analyze, remaining_analyses, plan_type
            
        Raises:
            ValueError: If limit exceeded
        """
        # Get active subscription
        subscription = await SubscriptionService.get_active_subscription(db, user.id)
        
        if not subscription:
            raise ValueError("No active subscription found")
        
        # Paid users have unlimited nutrition analyses
        if subscription.plan_type == "paid":
            return {
                "can_analyze": True,
                "remaining_analyses": -1,  # -1 indicates unlimited
                "plan_type": "paid"
            }
        
        # Free users: check daily limit
        today = datetime.now(timezone.utc).date()
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        
        # Get or create today's upload limit record
        result = await db.execute(
            select(UploadLimit).where(
                and_(
                    UploadLimit.user_id == user.id,
                    func.date(UploadLimit.date) == today
                )
            )
        )
        upload_limit = result.scalar_one_or_none()
        
        if not upload_limit:
            upload_limit = UploadLimit(
                user_id=user.id,
                date=today_start,
                upload_count=0,
                nutrition_analysis_count=0
            )
            db.add(upload_limit)
            await db.flush()
        
        # Check limit (2 nutrition analyses per day for free users)
        max_analyses = settings.FREE_TIER_DAILY_UPLOAD_LIMIT  # Reuse same limit: 2
        remaining = max_analyses - upload_limit.nutrition_analysis_count
        
        if upload_limit.nutrition_analysis_count >= max_analyses:
            logger.warning(
                "Nutrition analysis limit exceeded",
                user_id=str(user.id),
                current_count=upload_limit.nutrition_analysis_count,
                max_analyses=max_analyses
            )
            raise ValueError(f"Daily nutrition analysis limit exceeded. Free tier allows {max_analyses} analyses per day.")
        
        return {
            "can_analyze": True,
            "remaining_analyses": remaining,
            "plan_type": "free",
            "current_count": upload_limit.nutrition_analysis_count,
            "max_analyses": max_analyses
        }
    
    @staticmethod
    async def increment_nutrition_count(db: AsyncSession, user: User) -> None:
        """
        Increment user's nutrition analysis count for today.
        
        Args:
            db: Database session
            user: User object
        """
        today = datetime.now(timezone.utc).date()
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        
        # Get or create today's upload limit record
        result = await db.execute(
            select(UploadLimit).where(
                and_(
                    UploadLimit.user_id == user.id,
                    func.date(UploadLimit.date) == today
                )
            )
        )
        upload_limit = result.scalar_one_or_none()
        
        if not upload_limit:
            upload_limit = UploadLimit(
                user_id=user.id,
                date=today_start,
                upload_count=0,
                nutrition_analysis_count=1
            )
            db.add(upload_limit)
        else:
            upload_limit.nutrition_analysis_count += 1
            upload_limit.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        logger.info(
            "Nutrition analysis count incremented",
            user_id=str(user.id),
            new_count=upload_limit.nutrition_analysis_count
        )
    
    @staticmethod
    async def get_usage_stats(db: AsyncSession, user: User) -> Dict[str, Any]:
        """
        Get user's usage statistics.
        
        Args:
            db: Database session
            user: User object
            
        Returns:
            Dict with usage stats
        """
        subscription = await SubscriptionService.get_active_subscription(db, user.id)
        
        if not subscription:
            return {
                "plan_type": "none",
                "status": "inactive",
                "uploads_today": 0,
                "remaining_uploads": 0
            }
        
        # Get today's usage
        today = datetime.now(timezone.utc).date()
        result = await db.execute(
            select(UploadLimit).where(
                and_(
                    UploadLimit.user_id == user.id,
                    func.date(UploadLimit.date) == today
                )
            )
        )
        upload_limit = result.scalar_one_or_none()
        
        uploads_today = upload_limit.upload_count if upload_limit else 0
        nutrition_analyses_today = upload_limit.nutrition_analysis_count if upload_limit else 0
        
        if subscription.plan_type == "paid":
            response = {
                "plan_type": "paid",
                "status": subscription.status,
                "uploads_today": uploads_today,
                "remaining_uploads": -1,  # Unlimited
                "nutrition_analyses_today": nutrition_analyses_today,
                "remaining_analyses": -1  # Unlimited
            }
            
            # Add trial info if end_date exists
            if subscription.end_date:
                days_remaining = (subscription.end_date - datetime.now(timezone.utc)).days
                response["trial_days_remaining"] = max(0, days_remaining)
                response["trial_end_date"] = subscription.end_date.isoformat()
                response["is_trial"] = True
            else:
                response["is_trial"] = False
            
            return response
        else:
            max_uploads = settings.FREE_TIER_DAILY_UPLOAD_LIMIT
            return {
                "plan_type": "free",
                "status": subscription.status,
                "uploads_today": uploads_today,
                "remaining_uploads": max(0, max_uploads - uploads_today),
                "max_daily_uploads": max_uploads,
                "nutrition_analyses_today": nutrition_analyses_today,
                "remaining_analyses": max(0, max_uploads - nutrition_analyses_today),
                "max_daily_analyses": max_uploads,
                "is_trial": False
            }
    
    @staticmethod
    async def upgrade_to_paid(db: AsyncSession, user: User) -> Subscription:
        """
        Upgrade user to paid subscription.
        
        Args:
            db: Database session
            user: User object
            
        Returns:
            New subscription
        """
        # Deactivate current subscription
        current_sub = await SubscriptionService.get_active_subscription(db, user.id)
        if current_sub:
            current_sub.status = "inactive"
            current_sub.end_date = datetime.now(timezone.utc)
        
        # Create new paid subscription
        new_sub = Subscription(
            user_id=user.id,
            plan_type="paid",
            status="active"
        )
        db.add(new_sub)
        await db.commit()
        await db.refresh(new_sub)
        
        logger.info("User upgraded to paid subscription", user_id=str(user.id))
        
        return new_sub
