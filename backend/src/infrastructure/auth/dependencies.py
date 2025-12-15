from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from ..database.database import get_db
from ..database.auth_models import User, UserRole, Role
from .jwt import verify_token
from ...infrastructure.utils.logger import logger

# HTTP Bearer token scheme
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token
        db: Database session
        
    Returns:
        User object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Verify token
    payload = verify_token(token, token_type="access")
    if not payload:
        logger.warning("Invalid or expired token", token_prefix=token[:20])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        logger.warning("Token missing user ID")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True, User.deleted_at == None))
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning("User not found or inactive", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get the current active user (not deleted).
    
    Args:
        current_user: Current user from token
        
    Returns:
        User object
        
    Raises:
        HTTPException: If user is inactive or deleted
    """
    if not current_user.is_active or current_user.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or deleted"
        )
    return current_user

async def get_user_roles(user: User, db: AsyncSession) -> List[str]:
    """
    Get roles for a user.
    
    Args:
        user: User object
        db: Database session
        
    Returns:
        List of role names
    """
    result = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
    )
    roles = result.scalars().all()
    return list(roles)

def require_role(required_roles: List[str]):
    """
    Dependency factory to require specific roles.
    
    Args:
        required_roles: List of role names that are allowed
        
    Returns:
        Dependency function
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        user_roles = await get_user_roles(current_user, db)
        
        if not any(role in required_roles for role in user_roles):
            logger.warning(
                "Authorization failed - insufficient permissions",
                user_id=str(current_user.id),
                user_roles=user_roles,
                required_roles=required_roles
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        return current_user
    
    return role_checker

# Common role dependencies
require_admin = require_role(["admin"])
require_user = require_role(["user", "admin"])
