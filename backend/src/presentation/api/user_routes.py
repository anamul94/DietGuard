from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from ...infrastructure.database.database import get_db
from ...infrastructure.database.auth_models import User
from ...infrastructure.auth.dependencies import get_current_active_user
from ...application.services.auth_service import AuthService
from ...application.services.subscription_service import SubscriptionService
from ...application.services.audit_service import AuditService
from ...infrastructure.utils.logger import logger

router = APIRouter(tags=["Users"])

# Response Models
class UserProfile(BaseModel):
    id: str
    email: str
    firstName: str
    lastName: str
    age: Optional[int]
    gender: Optional[str]
    isActive: bool
    createdAt: str

class UsageStats(BaseModel):
    plan_type: str
    status: str
    uploads_today: int
    remaining_uploads: int
    max_daily_uploads: Optional[int] = None

class MessageResponse(BaseModel):
    message: str

@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user's profile information.
    
    Requires authentication.
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "firstName": current_user.first_name,
        "lastName": current_user.last_name,
        "age": current_user.age,
        "gender": current_user.gender,
        "isActive": current_user.is_active,
        "createdAt": current_user.created_at.isoformat()
    }

@router.get("/me/usage", response_model=UsageStats)
async def get_usage_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's upload usage statistics.
    
    Shows:
    - Current subscription plan (free/paid)
    - Uploads used today
    - Remaining uploads (for free tier)
    
    Requires authentication.
    """
    stats = await SubscriptionService.get_usage_stats(db, current_user)
    return stats

@router.delete("/me", response_model=MessageResponse)
async def delete_own_account(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete own user account (soft delete for GDPR compliance).
    
    This will:
    - Mark account as deleted
    - Deactivate account
    - Preserve data for audit purposes
    
    Requires authentication.
    """
    try:
        await AuthService.delete_user_account(db, current_user)
        
        # Log account deletion
        await AuditService.log_data_modification(
            db=db,
            action="delete",
            user_id=str(current_user.id),
            resource="user_account",
            resource_id=str(current_user.id),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        return {"message": "Account deleted successfully"}
    
    except Exception as e:
        logger.error("Account deletion failed", user_id=str(current_user.id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )

@router.put("/me", response_model=UserProfile)
async def update_profile(
    request: Request,
    update_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user's profile.
    
    Allowed fields:
    - firstName
    - lastName
    - age
    - gender
    
    Requires authentication.
    """
    # Update allowed fields
    allowed_fields = {"firstName", "lastName", "age", "gender"}
    changes = {}
    
    for field, value in update_data.items():
        if field in allowed_fields and value is not None:
            db_field = field[0].lower() + field[1:] if field[0].isupper() else field
            db_field = db_field.replace("firstName", "first_name").replace("lastName", "last_name")
            setattr(current_user, db_field, value)
            changes[field] = value
    
    await db.commit()
    await db.refresh(current_user)
    
    # Log profile update
    await AuditService.log_data_modification(
        db=db,
        action="update",
        user_id=str(current_user.id),
        resource="user_profile",
        resource_id=str(current_user.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        changes=changes
    )
    
    logger.info("User profile updated", user_id=str(current_user.id), changes=changes)
    
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "firstName": current_user.first_name,
        "lastName": current_user.last_name,
        "age": current_user.age,
        "gender": current_user.gender,
        "isActive": current_user.is_active,
        "createdAt": current_user.created_at.isoformat()
    }
