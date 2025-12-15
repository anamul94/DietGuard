from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from ...infrastructure.database.auth_models import AuditLog
from ...infrastructure.utils.logger import logger

class AuditService:
    """Service for audit logging"""
    
    @staticmethod
    async def log_event(
        db: AsyncSession,
        action: str,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an audit event.
        
        Args:
            db: Database session
            action: Action performed (e.g., 'login', 'logout', 'create_user')
            user_id: User ID (optional for anonymous actions)
            resource: Resource affected (optional)
            ip_address: Client IP address
            user_agent: Client user agent
            extra_data: Additional metadata (JSON)
        """
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data=extra_data
        )
        db.add(audit_log)
        await db.commit()
        
        logger.info(
            "Audit event logged",
            action=action,
            user_id=user_id,
            resource=resource,
            ip_address=ip_address
        )
    
    @staticmethod
    async def log_auth_event(
        db: AsyncSession,
        action: str,
        email: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        Log authentication event.
        
        Args:
            db: Database session
            action: Auth action (e.g., 'login_attempt', 'login_success', 'login_failed')
            email: User email
            success: Whether action was successful
            ip_address: Client IP
            user_agent: Client user agent
            user_id: User ID if available
        """
        await AuditService.log_event(
            db=db,
            action=action,
            user_id=user_id,
            resource="authentication",
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data={
                "email": email,
                "success": success
            }
        )
    
    @staticmethod
    async def log_authorization_failure(
        db: AsyncSession,
        user_id: str,
        resource: str,
        required_roles: list,
        user_roles: list,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Log authorization failure.
        
        Args:
            db: Database session
            user_id: User ID
            resource: Resource attempted to access
            required_roles: Roles required
            user_roles: User's actual roles
            ip_address: Client IP
            user_agent: Client user agent
        """
        await AuditService.log_event(
            db=db,
            action="authorization_failed",
            user_id=user_id,
            resource=resource,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data={
                "required_roles": required_roles,
                "user_roles": user_roles
            }
        )
    
    @staticmethod
    async def log_data_modification(
        db: AsyncSession,
        action: str,
        user_id: str,
        resource: str,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log data modification event.
        
        Args:
            db: Database session
            action: Action type (e.g., 'create', 'update', 'delete')
            user_id: User ID
            resource: Resource type
            resource_id: ID of affected resource
            ip_address: Client IP
            user_agent: Client user agent
            changes: Details of changes made
        """
        await AuditService.log_event(
            db=db,
            action=f"{action}_{resource}",
            user_id=user_id,
            resource=resource,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data={
                "resource_id": resource_id,
                "changes": changes
            }
        )
