from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ...infrastructure.database.database import get_db
from ...infrastructure.database.auth_models import User, AuditLog, Role, UserRole
from ...infrastructure.auth.dependencies import require_admin
from ...infrastructure.scheduler.jobs import daily_summary_job, weekly_plan_refresh_job
from ...infrastructure.utils.logger import logger
from ...application.services.token_usage_service import TokenUsageService

router = APIRouter(tags=["Admin"])

# Response Models
class UserListItem(BaseModel):
    id: str
    email: str
    isActive: bool
    createdAt: str
    roles: List[str]

class AuditLogItem(BaseModel):
    id: str
    user_id: Optional[str]
    action: str
    resource: Optional[str]
    ip_address: Optional[str]
    created_at: str

class UpdateRoleRequest(BaseModel):
    role_name: str

@router.get("/users", response_model=list)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    List all users (admin only).
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    
    Requires admin role.
    """
    result = await db.execute(
        select(User)
        .where(User.deleted_at == None)
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    users = result.scalars().all()
    
    # Get roles for each user
    user_list = []
    for user in users:
        roles_result = await db.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
        )
        roles = [r for r in roles_result.scalars().all()]
        
        user_list.append({
            "id": str(user.id),
            "email": user.email,
            "isActive": user.is_active,
            "createdAt": user.created_at.isoformat(),
            "roles": roles
        })
    
    logger.info("Admin listed users", admin_id=str(current_user.id), count=len(user_list))
    
    return user_list

@router.get("/audit-logs", response_model=list)
async def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    action: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get audit logs (admin only).
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **action**: Filter by action type (optional)
    
    Requires admin role.
    """
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    
    if action:
        query = query.where(AuditLog.action == action)
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    logger.info("Admin viewed audit logs", admin_id=str(current_user.id), count=len(logs))
    
    return [
        {
            "id": str(log.id),
            "user_id": str(log.user_id) if log.user_id else None,
            "action": log.action,
            "resource": log.resource,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
            "extra_data": log.extra_data
        }
        for log in logs
    ]

@router.put("/users/{user_id}/role", response_model=dict)
async def update_user_role(
    user_id: str,
    role_data: UpdateRoleRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user's role (admin only).
    
    - **user_id**: User ID to update
    - **role_name**: New role name ('user' or 'admin')
    
    Requires admin role.
    """
    # Get user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get role
    role_result = await db.execute(select(Role).where(Role.name == role_data.role_name))
    role = role_result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{role_data.role_name}' not found"
        )
    
    # Remove existing roles
    await db.execute(select(UserRole).where(UserRole.user_id == user.id))
    from sqlalchemy import delete
    await db.execute(delete(UserRole).where(UserRole.user_id == user.id))
    
    # Add new role
    user_role = UserRole(user_id=user.id, role_id=role.id)
    db.add(user_role)
    await db.commit()
    
    logger.info(
        "Admin updated user role",
        admin_id=str(current_user.id),
        user_id=user_id,
        new_role=role_data.role_name
    )
    
    return {
        "message": f"User role updated to '{role_data.role_name}'",
        "user_id": user_id,
        "new_role": role_data.role_name
    }


@router.post("/jobs/run-daily-summaries", response_model=dict)
async def trigger_daily_summaries(current_user: User = Depends(require_admin)):
    """Manually trigger the daily summary job (admin only). Useful for testing."""
    logger.info("Admin manually triggered daily_summary_job", admin_id=str(current_user.id))
    await daily_summary_job()
    return {"message": "daily_summary_job completed"}


@router.post("/jobs/run-weekly-plan-refresh", response_model=dict)
async def trigger_weekly_plan_refresh(current_user: User = Depends(require_admin)):
    """Manually trigger the weekly plan refresh job (admin only). Useful for testing."""
    logger.info("Admin manually triggered weekly_plan_refresh_job", admin_id=str(current_user.id))
    await weekly_plan_refresh_job()
    return {"message": "weekly_plan_refresh_job completed"}

@router.get("/token-stats/daily", response_model=list)
async def get_daily_token_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get daily token usage statistics (admin only).
    
    - **days**: Number of days to look back (default 30)
    
    Requires admin role.
    """
    stats = await TokenUsageService.get_daily_token_stats(db, days=days)
    logger.info("Admin viewed daily token stats", admin_id=str(current_user.id), days=days)
    return stats

@router.get("/token-stats/models", response_model=list)
async def get_model_token_stats(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get token usage statistics per model (admin only).
    
    Requires admin role.
    """
    stats = await TokenUsageService.get_model_token_stats(db)
    logger.info("Admin viewed model token stats", admin_id=str(current_user.id))
    return stats

@router.get("/token-stats/top-consumers", response_model=list)
async def get_top_token_consumers(
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get users who consume the most tokens (admin only).
    
    - **limit**: Maximum number of users to return (default 10)
    
    Requires admin role.
    """
    stats = await TokenUsageService.get_top_token_consumers(db, limit=limit)
    logger.info("Admin viewed top token consumers", admin_id=str(current_user.id), limit=limit)
    return stats

@router.get("/users/{user_id}/token-stats", response_model=dict)
async def get_user_token_stats(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get token statistics for a specific user (admin only).
    
    - **user_id**: The user's ID
    
    Requires admin role.
    """
    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    stats = await TokenUsageService.get_user_token_stats(db, user_id=user_id)
    logger.info("Admin viewed user token stats", admin_id=str(current_user.id), target_user_id=user_id)
    return stats

