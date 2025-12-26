"""
HIPAA-compliant patient data models.
Separates PII (encrypted, deletable) from Persona (retained for analytics).
"""
from sqlalchemy import Column, String, Integer, Date, Numeric, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from .database import Base


class PatientPII(Base):
    """
    Patient Personally Identifiable Information (PII).
    
    This table stores sensitive personal information that is:
    - Encrypted at rest (field-level encryption)
    - Deleted when user requests account deletion
    - Subject to HIPAA audit logging
    
    All encrypted fields are stored as base64-encoded strings.
    """
    __tablename__ = "patient_pii"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True,
        index=True
    )
    
    # Encrypted PII fields (stored as base64-encoded encrypted strings)
    full_name_encrypted = Column(Text, nullable=False)  # First + Last name
    email_encrypted = Column(Text, nullable=False)  # Backup encrypted email
    phone_number_encrypted = Column(Text, nullable=True)  # Contact/Phone number
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="patient_pii")
    
    # Indexes
    __table_args__ = (
        Index('idx_patient_pii_user_id', 'user_id'),
    )


class PatientPersona(Base):
    """
    Patient Health Persona/Metadata.
    
    This table stores health-related metadata that is:
    - NOT encrypted (used for analytics and research)
    - Retained when user deletes account (user_id set to NULL for anonymization)
    - Used for population health analytics
    
    This data is anonymized upon user deletion but retained for research purposes.
    """
    __tablename__ = "patient_persona"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True,  # Nullable to allow anonymization
        unique=True,
        index=True
    )
    
    # Demographics (non-sensitive)
    gender = Column(String(30), nullable=True)  # male, female, other, prefer_not_to_say
    date_of_birth = Column(Date, nullable=True)  # For age calculation
    
    # Health Metrics
    blood_group = Column(String(5), nullable=True)  # A+, A-, B+, B-, AB+, AB-, O+, O-
    height_cm = Column(Numeric(5, 2), nullable=True)  # Height in cm (e.g., 175.50)
    weight_kg = Column(Numeric(5, 2), nullable=True)  # Weight in kg (e.g., 75.50)
    
    # Location & Origin (non-sensitive)
    current_location = Column(String(100), nullable=True)  # City/State
    birth_place = Column(String(100), nullable=True)  # City/Country
    nationality = Column(String(50), nullable=True)  # Country
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    anonymized_at = Column(DateTime(timezone=True), nullable=True)  # When user_id was set to NULL
    
    # Relationships
    user = relationship("User", back_populates="patient_persona")
    
    # Indexes
    __table_args__ = (
        Index('idx_patient_persona_user_id', 'user_id'),
        Index('idx_patient_persona_blood_group', 'blood_group'),
    )
