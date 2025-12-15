from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ...infrastructure.database.database import get_db
from ...infrastructure.database.auth_models import User, AuditLog, Role, UserRole
from ...infrastructure.auth.dependencies import require_admin
from ...infrastructure.utils.logger import logger

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

# Response Models
class UserListItem(BaseModel):
    id: str
    email: str
    firstName: str
    lastName: str
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
            "firstName": user.first_name,
            "lastName": user.last_name,
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
