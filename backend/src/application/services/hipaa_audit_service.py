"""
HIPAA Audit Service for tracking PHI access and modifications.
Provides comprehensive audit logging for HIPAA compliance.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, String, Text, DateTime, UUID, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid

from ...infrastructure.database.database import Base
from ...infrastructure.utils.logger import logger


class HIPAAAuditLog(Base):
    """
    HIPAA-compliant audit log for PHI access and modifications.
    
    Tracks:
    - Who accessed/modified PHI
    - What data was accessed/modified
    - When the access/modification occurred
    - Why (action type)
    - How (IP address, user agent)
    """
    __tablename__ = "hipaa_audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Who
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # User who performed action
    patient_user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Patient whose data was accessed
    
    # What
    action = Column(String(100), nullable=False, index=True)  # e.g., 'phi_access', 'phi_update', 'phi_delete'
    resource = Column(String(100), nullable=False)  # e.g., 'patient_pii', 'patient_persona'
    field_accessed = Column(String(100), nullable=True)  # Specific field if applicable
    
    # When
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # How
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    
    # Additional context
    extra_data = Column(JSONB, nullable=True)  # Additional metadata
    success = Column(String(10), nullable=False, default="success")  # success, failure, error
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_hipaa_audit_user_date', 'user_id', 'created_at'),
        Index('idx_hipaa_audit_patient_date', 'patient_user_id', 'created_at'),
        Index('idx_hipaa_audit_action_date', 'action', 'created_at'),
        Index('idx_hipaa_audit_resource', 'resource'),
    )


class HIPAAAuditService:
    """Service for HIPAA-compliant audit logging."""
    
    @staticmethod
    async def log_phi_access(
        db: AsyncSession,
        user_id: Optional[str],
        patient_user_id: str,
        resource: str,
        field_accessed: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log PHI access event.
        
        Args:
            db: Database session
            user_id: User who accessed the data
            patient_user_id: Patient whose data was accessed
            resource: Resource accessed (e.g., 'patient_pii')
            field_accessed: Specific field accessed
            ip_address: IP address of requester
            user_agent: User agent string
            extra_data: Additional metadata
        """
        audit_log = HIPAAAuditLog(
            user_id=uuid.UUID(user_id) if user_id else None,
            patient_user_id=uuid.UUID(patient_user_id),
            action="phi_access",
            resource=resource,
            field_accessed=field_accessed,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data=extra_data,
            success="success"
        )
        
        db.add(audit_log)
        await db.commit()
        
        logger.info(
            "PHI access logged",
            user_id=user_id,
            patient_user_id=patient_user_id,
            resource=resource
        )
    
    @staticmethod
    async def log_phi_modification(
        db: AsyncSession,
        user_id: str,
        patient_user_id: str,
        resource: str,
        action: str,  # 'phi_create', 'phi_update', 'phi_delete'
        fields_modified: Optional[list] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log PHI modification event.
        
        Args:
            db: Database session
            user_id: User who modified the data
            patient_user_id: Patient whose data was modified
            resource: Resource modified
            action: Type of modification
            fields_modified: List of fields modified
            ip_address: IP address of requester
            user_agent: User agent string
            extra_data: Additional metadata
        """
        if extra_data is None:
            extra_data = {}
        
        if fields_modified:
            extra_data['fields_modified'] = fields_modified
        
        audit_log = HIPAAAuditLog(
            user_id=uuid.UUID(user_id),
            patient_user_id=uuid.UUID(patient_user_id),
            action=action,
            resource=resource,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data=extra_data,
            success="success"
        )
        
        db.add(audit_log)
        await db.commit()
        
        logger.info(
            "PHI modification logged",
            user_id=user_id,
            patient_user_id=patient_user_id,
            resource=resource,
            action=action
        )
    
    @staticmethod
    async def log_encryption_event(
        db: AsyncSession,
        user_id: str,
        action: str,  # 'encrypt', 'decrypt'
        resource: str,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log encryption/decryption event.
        
        Args:
            db: Database session
            user_id: User ID
            action: 'encrypt' or 'decrypt'
            resource: Resource being encrypted/decrypted
            success: Whether operation succeeded
            error_message: Error message if failed
        """
        extra_data = {}
        if error_message:
            extra_data['error'] = error_message
        
        audit_log = HIPAAAuditLog(
            user_id=uuid.UUID(user_id),
            patient_user_id=uuid.UUID(user_id),
            action=f"phi_{action}",
            resource=resource,
            extra_data=extra_data,
            success="success" if success else "failure"
        )
        
        db.add(audit_log)
        await db.commit()
        
        logger.info(
            f"Encryption event logged: {action}",
            user_id=user_id,
            resource=resource,
            success=success
        )
    
    @staticmethod
    async def log_anonymization(
        db: AsyncSession,
        patient_user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Log patient data anonymization event.
        
        Args:
            db: Database session
            patient_user_id: Patient whose data was anonymized
            ip_address: IP address of requester
            user_agent: User agent string
        """
        audit_log = HIPAAAuditLog(
            user_id=uuid.UUID(patient_user_id),
            patient_user_id=uuid.UUID(patient_user_id),
            action="phi_anonymize",
            resource="patient_data",
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data={"reason": "user_account_deletion"},
            success="success"
        )
        
        db.add(audit_log)
        await db.commit()
        
        logger.info(
            "Patient data anonymization logged",
            patient_user_id=patient_user_id
        )
