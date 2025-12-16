"""
API routes for subscription packages.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from ...infrastructure.database.database import get_db
from ...infrastructure.database.auth_models import Package, User
from ...infrastructure.auth.dependencies import get_current_user, require_admin
from ..schemas.package_schemas import PackageResponse, PackageCreate, PackageUpdate

router = APIRouter(prefix="/packages", tags=["Packages"])


@router.get("/", response_model=List[PackageResponse])
async def list_packages(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    List all available subscription packages.
    
    - **include_inactive**: Include inactive packages (default: False)
    """
    query = select(Package)
    if not include_inactive:
        query = query.where(Package.is_active == True)
    
    result = await db.execute(query.order_by(Package.price))
    packages = result.scalars().all()
    
    return [
        PackageResponse(
            id=str(pkg.id),
            name=pkg.name,
            price=pkg.price,
            billing_period=pkg.billing_period,
            daily_upload_limit=pkg.daily_upload_limit,
            daily_nutrition_limit=pkg.daily_nutrition_limit,
            features=pkg.features,
            is_active=pkg.is_active,
            created_at=pkg.created_at.isoformat(),
            updated_at=pkg.updated_at.isoformat()
        )
        for pkg in packages
    ]


@router.get("/{package_id}", response_model=PackageResponse)
async def get_package(
    package_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific package by ID.
    """
    try:
        pkg_uuid = uuid.UUID(package_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid package ID format"
        )
    
    result = await db.execute(select(Package).where(Package.id == pkg_uuid))
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
    
    return PackageResponse(
        id=str(package.id),
        name=package.name,
        price=package.price,
        billing_period=package.billing_period,
        daily_upload_limit=package.daily_upload_limit,
        daily_nutrition_limit=package.daily_nutrition_limit,
        features=package.features,
        is_active=package.is_active,
        created_at=package.created_at.isoformat(),
        updated_at=package.updated_at.isoformat()
    )


@router.post("/", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
async def create_package(
    package_data: PackageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new subscription package.
    
    **Requires admin role.**
    """
    # Check if package with same name exists
    result = await db.execute(select(Package).where(Package.name == package_data.name))
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Package with name '{package_data.name}' already exists"
        )
    
    # Create package
    package = Package(
        name=package_data.name,
        price=package_data.price,
        billing_period=package_data.billing_period,
        daily_upload_limit=package_data.daily_upload_limit,
        daily_nutrition_limit=package_data.daily_nutrition_limit,
        features=package_data.features,
        is_active=package_data.is_active
    )
    
    db.add(package)
    await db.commit()
    await db.refresh(package)
    
    return PackageResponse(
        id=str(package.id),
        name=package.name,
        price=package.price,
        billing_period=package.billing_period,
        daily_upload_limit=package.daily_upload_limit,
        daily_nutrition_limit=package.daily_nutrition_limit,
        features=package.features,
        is_active=package.is_active,
        created_at=package.created_at.isoformat(),
        updated_at=package.updated_at.isoformat()
    )


@router.put("/{package_id}", response_model=PackageResponse)
async def update_package(
    package_id: str,
    package_data: PackageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update an existing package.
    
    **Requires admin role.**
    """
    try:
        pkg_uuid = uuid.UUID(package_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid package ID format"
        )
    
    result = await db.execute(select(Package).where(Package.id == pkg_uuid))
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
    
    # Update fields
    update_data = package_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(package, field, value)
    
    await db.commit()
    await db.refresh(package)
    
    return PackageResponse(
        id=str(package.id),
        name=package.name,
        price=package.price,
        billing_period=package.billing_period,
        daily_upload_limit=package.daily_upload_limit,
        daily_nutrition_limit=package.daily_nutrition_limit,
        features=package.features,
        is_active=package.is_active,
        created_at=package.created_at.isoformat(),
        updated_at=package.updated_at.isoformat()
    )


@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package(
    package_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete a package (soft delete by setting is_active=False).
    
    **Requires admin role.**
    """
    try:
        pkg_uuid = uuid.UUID(package_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid package ID format"
        )
    
    result = await db.execute(select(Package).where(Package.id == pkg_uuid))
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
    
    # Soft delete
    package.is_active = False
    await db.commit()
    
    return None
