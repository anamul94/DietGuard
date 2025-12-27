"""
Patient service for managing patient PII and persona data.
Handles encryption, decryption, and HIPAA-compliant operations.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from ...infrastructure.database.patient_models import PatientPII, PatientPersona
from ...infrastructure.database.auth_models import User
from ...infrastructure.security.encryption_service import get_encryption_service
from .hipaa_audit_service import HIPAAAuditService
from ...infrastructure.utils.logger import logger


class PatientService:
    """Service for managing patient data with HIPAA compliance."""
    
    @staticmethod
    async def create_patient_data(
        db: AsyncSession,
        user_id: str,
        # PII fields (will be encrypted)
        full_name: str,
        email: str,
        phone_number: Optional[str] = None,
        # Persona fields (not encrypted)
        gender: Optional[str] = None,
        blood_group: Optional[str] = None,
        height_cm: Optional[float] = None,
        weight_kg: Optional[float] = None,
        current_location: Optional[str] = None,
        birth_place: Optional[str] = None,
        nationality: Optional[str] = None,
        date_of_birth: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create patient PII and persona records.
        
        Args:
            db: Database session
            user_id: User ID
            (other args): Patient data fields
            
        Returns:
            Dict with created patient data
            
        Raises:
            ValueError: If encryption fails or data already exists
        """
        encryption_service = get_encryption_service()
        
        # Check if patient data already exists
        existing_pii = await db.execute(
            select(PatientPII).where(PatientPII.user_id == user_id)
        )
        if existing_pii.scalar_one_or_none():
            raise ValueError("Patient data already exists for this user")
        
        try:
            # Encrypt PII fields
            full_name_encrypted = encryption_service.encrypt(full_name)
            email_encrypted = encryption_service.encrypt(email)
            phone_number_encrypted = encryption_service.encrypt(phone_number) if phone_number else None
            
            # Create PatientPII record
            patient_pii = PatientPII(
                user_id=user_id,
                full_name_encrypted=full_name_encrypted,
                email_encrypted=email_encrypted,
                phone_number_encrypted=phone_number_encrypted
            )
            db.add(patient_pii)
            
            # Create PatientPersona record
            patient_persona = PatientPersona(
                user_id=user_id,
                gender=gender,
                blood_group=blood_group,
                height_cm=height_cm,
                weight_kg=weight_kg,
                current_location=current_location,
                birth_place=birth_place,
                nationality=nationality,
                date_of_birth=date_of_birth.date() if date_of_birth else None # age will be calculated from date_of_birth
            )
            db.add(patient_persona)
            
            await db.flush()
            
            # Log HIPAA audit
            await HIPAAAuditService.log_phi_modification(
                db=db,
                user_id=user_id,
                patient_user_id=user_id,
                resource="patient_pii",
                action="phi_create",
                fields_modified=["full_name", "email", "phone_number"],
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            await HIPAAAuditService.log_phi_modification(
                db=db,
                user_id=user_id,
                patient_user_id=user_id,
                resource="patient_persona",
                action="phi_create",
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            logger.info("Patient data created", user_id=user_id)
            
            return {
                "pii": patient_pii,
                "persona": patient_persona
            }
            
        except Exception as e:
            logger.error(f"Failed to create patient data: {str(e)}", user_id=user_id)
            raise ValueError(f"Failed to create patient data: {str(e)}")
    
    @staticmethod
    async def get_patient_profile(
        db: AsyncSession,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get patient profile with decrypted PII.
        
        Args:
            db: Database session
            user_id: User ID
            ip_address: IP address for audit
            user_agent: User agent for audit
            
        Returns:
            Dict with decrypted patient data, or None if not found
        """
        encryption_service = get_encryption_service()
        
        # Get PII
        pii_result = await db.execute(
            select(PatientPII).where(PatientPII.user_id == user_id)
        )
        patient_pii = pii_result.scalar_one_or_none()
        
        # Get Persona
        persona_result = await db.execute(
            select(PatientPersona).where(PatientPersona.user_id == user_id)
        )
        patient_persona = persona_result.scalar_one_or_none()
        
        if not patient_pii and not patient_persona:
            return None
        
        # Decrypt PII fields
        decrypted_pii = {}
        if patient_pii:
            try:
                decrypted_pii = {
                    "full_name": encryption_service.decrypt(patient_pii.full_name_encrypted),
                    "email": encryption_service.decrypt(patient_pii.email_encrypted),
                    "phone_number": encryption_service.decrypt(patient_pii.phone_number_encrypted) if patient_pii.phone_number_encrypted else None
                }
                
                # Log PHI access
                await HIPAAAuditService.log_phi_access(
                    db=db,
                    user_id=user_id,
                    patient_user_id=user_id,
                    resource="patient_pii",
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
            except Exception as e:
                logger.error(f"Failed to decrypt patient PII: {str(e)}", user_id=user_id)
                raise ValueError("Failed to retrieve patient data")
        
        # Build persona data
        persona_data = {}
        if patient_persona:
            # Calculate age from date_of_birth
            age = None
            if patient_persona.date_of_birth:
                from datetime import date
                today = date.today()
                dob = patient_persona.date_of_birth
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            
            persona_data = {
                "age": age,
                "gender": patient_persona.gender,
                "blood_group": patient_persona.blood_group,
                "height_cm": float(patient_persona.height_cm) if patient_persona.height_cm else None,
                "weight_kg": float(patient_persona.weight_kg) if patient_persona.weight_kg else None,
                "current_location": patient_persona.current_location,
                "birth_place": patient_persona.birth_place,
                "nationality": patient_persona.nationality,
                "date_of_birth": patient_persona.date_of_birth.isoformat() if patient_persona.date_of_birth else None
            }
        
        return {
            "pii": decrypted_pii,
            "persona": persona_data
        }
    
    
    @staticmethod
    async def update_patient_pii(
        db: AsyncSession,
        user_id: str,
        updates: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Update patient PII fields.
        
        Args:
            db: Database session
            user_id: User ID
            updates: Dict of fields to update (full_name, email, phone_number)
            ip_address: IP address for audit
            user_agent: User agent for audit
            
        Returns:
            True if successful
        """
        encryption_service = get_encryption_service()
        
        # Get existing PII
        pii_result = await db.execute(
            select(PatientPII).where(PatientPII.user_id == user_id)
        )
        patient_pii = pii_result.scalar_one_or_none()
        
        if not patient_pii:
            raise ValueError("Patient PII not found")
        
        fields_modified = []
        
        try:
            # Update encrypted fields
            if "full_name" in updates:
                patient_pii.full_name_encrypted = encryption_service.encrypt(updates["full_name"])
                fields_modified.append("full_name")
            
            if "email" in updates:
                patient_pii.email_encrypted = encryption_service.encrypt(updates["email"])
                fields_modified.append("email")
            
            if "phone_number" in updates:
                patient_pii.phone_number_encrypted = encryption_service.encrypt(updates["phone_number"]) if updates["phone_number"] else None
                fields_modified.append("phone_number")
            
            # Log HIPAA audit
            if fields_modified:
                await HIPAAAuditService.log_phi_modification(
                    db=db,
                    user_id=user_id,
                    patient_user_id=user_id,
                    resource="patient_pii",
                    action="phi_update",
                    fields_modified=fields_modified,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            
            await db.commit()
            logger.info("Patient PII updated", user_id=user_id, fields=fields_modified)
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update patient PII: {str(e)}", user_id=user_id)
            raise ValueError(f"Failed to update patient PII: {str(e)}")
    
    @staticmethod
    async def update_patient_persona(
        db: AsyncSession,
        user_id: str,
        updates: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Update patient persona fields.
        
        Args:
            db: Database session
            user_id: User ID
            updates: Dict of fields to update (gender, date_of_birth, height_cm, weight_kg, etc.)
            ip_address: IP address for audit
            user_agent: User agent for audit
            
        Returns:
            True if successful
        """
        # Get existing persona
        persona_result = await db.execute(
            select(PatientPersona).where(PatientPersona.user_id == user_id)
        )
        patient_persona = persona_result.scalar_one_or_none()
        
        if not patient_persona:
            raise ValueError("Patient persona not found")
        
        fields_modified = []
        
        try:
            # Update allowed fields
            allowed_fields = ["gender", "date_of_birth", "blood_group", "height_cm", "weight_kg", 
                            "current_location", "birth_place", "nationality"]
            
            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(patient_persona, field, value)
                    fields_modified.append(field)
            
            # Log HIPAA audit
            if fields_modified:
                await HIPAAAuditService.log_phi_modification(
                    db=db,
                    user_id=user_id,
                    patient_user_id=user_id,
                    resource="patient_persona",
                    action="phi_update",
                    fields_modified=fields_modified,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            
            await db.commit()
            logger.info("Patient persona updated", user_id=user_id, fields=fields_modified)
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update patient persona: {str(e)}", user_id=user_id)
            raise ValueError(f"Failed to update patient persona: {str(e)}")
    
    @staticmethod
    async def anonymize_patient_data(
        db: AsyncSession,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Anonymize patient data by deleting PII and setting persona user_id to NULL.
        
        Args:
            db: Database session
            user_id: User ID
            ip_address: IP address for audit
            user_agent: User agent for audit
            
        Returns:
            True if successful
        """
        # Delete PII (CASCADE will handle this)
        pii_result = await db.execute(
            select(PatientPII).where(PatientPII.user_id == user_id)
        )
        patient_pii = pii_result.scalar_one_or_none()
        
        if patient_pii:
            await db.delete(patient_pii)
            logger.info("Patient PII deleted", user_id=user_id)
        
        # Anonymize Persona (set user_id to NULL)
        persona_result = await db.execute(
            select(PatientPersona).where(PatientPersona.user_id == user_id)
        )
        patient_persona = persona_result.scalar_one_or_none()
        
        if patient_persona:
            patient_persona.user_id = None
            patient_persona.anonymized_at = datetime.now(timezone.utc)
            logger.info("Patient persona anonymized", user_id=user_id)
        
        # Log anonymization
        await HIPAAAuditService.log_anonymization(
            db=db,
            patient_user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        await db.commit()
        
        return True
