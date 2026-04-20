from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ...infrastructure.database.database import get_db
from ...infrastructure.database.auth_models import User, AuditLog, Role, UserRole, Subscription, Package
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

class UpdateUserPackageRequest(BaseModel):
    package_id: str
    duration_days: Optional[int] = None  # Optional: custom duration in days

class CreatePackageRequest(BaseModel):
    name: str
    price: float
    billing_period: str  # 'free', 'monthly', 'yearly'
    daily_upload_limit: int
    daily_nutrition_limit: int
    features: dict = {}
    is_active: bool = True

class UpdatePackageRequest(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    billing_period: Optional[str] = None
    daily_upload_limit: Optional[int] = None
    daily_nutrition_limit: Optional[int] = None
    features: Optional[dict] = None
    is_active: Optional[bool] = None

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


@router.put("/users/{user_id}/package", response_model=dict)
async def update_user_package(
    user_id: str,
    package_data: UpdateUserPackageRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user's subscription package (admin only).
    
    - **user_id**: User ID to update
    - **package_id**: UUID of the package to assign
    - **duration_days**: Optional custom duration in days (defaults to package billing period)
    
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
    
    # Get package
    result = await db.execute(select(Package).where(Package.id == package_data.package_id))
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
    
    if not package.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign inactive package"
        )
    
    # Determine subscription duration
    from datetime import timedelta
    from datetime import timezone
    now = datetime.now(timezone.utc)
    if package_data.duration_days:
        end_date = now + timedelta(days=package_data.duration_days)
    elif package.billing_period == "free":
        end_date = None  # Free subscription has no end date
    elif package.billing_period == "monthly":
        end_date = now + timedelta(days=30)
    elif package.billing_period == "yearly":
        end_date = now + timedelta(days=365)
    else:
        end_date = None
    
    # Check for existing active subscription
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id, Subscription.status == "active")
    )
    existing_sub = result.scalar_one_or_none()
    
    if existing_sub:
        # Update existing subscription
        existing_sub.package_id = package.id
        existing_sub.plan_type = "free" if package.price == 0 else "paid"
        existing_sub.end_date = end_date
        existing_sub.start_date = now  # Reset start date to now
        existing_sub.updated_at = now
    else:
        # Create new subscription
        new_sub = Subscription(
            user_id=user.id,
            package_id=package.id,
            plan_type="free" if package.price == 0 else "paid",
            status="active",
            start_date=now,
            end_date=end_date
        )
        db.add(new_sub)
    
    await db.commit()
    
    logger.info(
        "Admin updated user package",
        admin_id=str(current_user.id),
        user_id=user_id,
        package_name=package.name,
        duration_days=package_data.duration_days
    )
    
    return {
        "message": f"User package updated to '{package.name}'",
        "user_id": user_id,
        "plan_type": "free" if package.price == 0 else "paid",
        "package": {
            "id": str(package.id),
            "name": package.name,
            "price": float(package.price),
            "billing_period": package.billing_period,
            "daily_upload_limit": package.daily_upload_limit,
            "daily_nutrition_limit": package.daily_nutrition_limit,
            "end_date": end_date.isoformat() if end_date else None
        }
    }


@router.get("/users/{user_id}/subscription", response_model=dict)
async def get_user_subscription(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's current subscription details (admin only).
    
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
    
    # Get active subscription
    result = await db.execute(
        select(Subscription, Package)
        .join(Package, Package.id == Subscription.package_id)
        .where(Subscription.user_id == user.id, Subscription.status == "active")
    )
    row = result.first()
    
    if not row:
        return {
            "user_id": user_id,
            "subscription": None,
            "package": None
        }
    
    subscription, package = row
    
    return {
        "user_id": user_id,
        "subscription": {
            "id": str(subscription.id),
            "status": subscription.status,
            "plan_type": subscription.plan_type,
            "start_date": subscription.start_date.isoformat() if subscription.start_date else None,
            "end_date": subscription.end_date.isoformat() if subscription.end_date else None
        },
        "package": {
            "id": str(package.id),
            "name": package.name,
            "price": float(package.price),
            "billing_period": package.billing_period,
            "daily_upload_limit": package.daily_upload_limit,
            "daily_nutrition_limit": package.daily_nutrition_limit,
            "features": package.features
        }
    }


@router.get("/packages", response_model=list)
async def list_packages(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    List all available packages (admin only).
    
    Requires admin role.
    """
    result = await db.execute(select(Package).where(Package.is_active == True))
    packages = result.scalars().all()
    
    return [
        {
            "id": str(pkg.id),
            "name": pkg.name,
            "price": float(pkg.price),
            "billing_period": pkg.billing_period,
            "daily_upload_limit": pkg.daily_upload_limit,
            "daily_nutrition_limit": pkg.daily_nutrition_limit,
            "features": pkg.features,
            "is_active": pkg.is_active
        }
        for pkg in packages
    ]


@router.post("/packages", response_model=dict)
async def create_package(
    package_data: CreatePackageRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new subscription package (admin only).
    
    Requires admin role.
    """
    # Check if package name already exists
    result = await db.execute(select(Package).where(Package.name == package_data.name))
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Package with name '{package_data.name}' already exists"
        )
    
    # Validate billing_period
    valid_periods = ["free", "monthly", "yearly"]
    if package_data.billing_period not in valid_periods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid billing_period. Must be one of: {valid_periods}"
        )
    
    new_package = Package(
        name=package_data.name,
        price=package_data.price,
        billing_period=package_data.billing_period,
        daily_upload_limit=package_data.daily_upload_limit,
        daily_nutrition_limit=package_data.daily_nutrition_limit,
        features=package_data.features,
        is_active=package_data.is_active
    )
    
    db.add(new_package)
    await db.commit()
    await db.refresh(new_package)
    
    logger.info(
        "Admin created package",
        admin_id=str(current_user.id),
        package_name=new_package.name
    )
    
    return {
        "message": f"Package '{new_package.name}' created successfully",
        "package": {
            "id": str(new_package.id),
            "name": new_package.name,
            "price": float(new_package.price),
            "billing_period": new_package.billing_period,
            "daily_upload_limit": new_package.daily_upload_limit,
            "daily_nutrition_limit": new_package.daily_nutrition_limit,
            "features": new_package.features,
            "is_active": new_package.is_active
        }
    }


@router.put("/packages/{package_id}", response_model=dict)
async def update_package(
    package_id: str,
    package_data: UpdatePackageRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing subscription package (admin only).
    
    Requires admin role.
    """
    result = await db.execute(select(Package).where(Package.id == package_id))
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
    
    # Update fields if provided
    if package_data.name is not None:
        # Check if name already exists for another package
        result = await db.execute(select(Package).where(Package.name == package_data.name, Package.id != package_id))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Package with name '{package_data.name}' already exists"
            )
        package.name = package_data.name
    
    if package_data.price is not None:
        package.price = package_data.price
    
    if package_data.billing_period is not None:
        valid_periods = ["free", "monthly", "yearly"]
        if package_data.billing_period not in valid_periods:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid billing_period. Must be one of: {valid_periods}"
            )
        package.billing_period = package_data.billing_period
    
    if package_data.daily_upload_limit is not None:
        package.daily_upload_limit = package_data.daily_upload_limit
    
    if package_data.daily_nutrition_limit is not None:
        package.daily_nutrition_limit = package_data.daily_nutrition_limit
    
    if package_data.features is not None:
        package.features = package_data.features
    
    if package_data.is_active is not None:
        package.is_active = package_data.is_active
    
    package.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(package)
    
    logger.info(
        "Admin updated package",
        admin_id=str(current_user.id),
        package_id=package_id
    )
    
    return {
        "message": f"Package '{package.name}' updated successfully",
        "package": {
            "id": str(package.id),
            "name": package.name,
            "price": float(package.price),
            "billing_period": package.billing_period,
            "daily_upload_limit": package.daily_upload_limit,
            "daily_nutrition_limit": package.daily_nutrition_limit,
            "features": package.features,
            "is_active": package.is_active
        }
    }


@router.delete("/packages/{package_id}", response_model=dict)
async def deactivate_package(
    package_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Deactivate a subscription package (admin only). Does not delete, just marks as inactive.
    
    Requires admin role.
    """
    result = await db.execute(select(Package).where(Package.id == package_id))
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
    
    package.is_active = False
    package.updated_at = datetime.utcnow()
    
    await db.commit()
    
    logger.info(
        "Admin deactivated package",
        admin_id=str(current_user.id),
        package_id=package_id
    )
    
    return {
        "message": f"Package '{package.name}' deactivated successfully",
        "package_id": package_id
    }


@router.post("/packages/{package_id}/activate", response_model=dict)
async def activate_package(
    package_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Activate a subscription package (admin only).
    
    Requires admin role.
    """
    result = await db.execute(select(Package).where(Package.id == package_id))
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
    
    package.is_active = True
    package.updated_at = datetime.utcnow()
    
    await db.commit()
    
    logger.info(
        "Admin activated package",
        admin_id=str(current_user.id),
        package_id=package_id
    )
    
    return {
        "message": f"Package '{package.name}' activated successfully",
        "package": {
            "id": str(package.id),
            "name": package.name,
            "is_active": package.is_active
        }
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

