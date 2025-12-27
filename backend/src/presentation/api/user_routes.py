from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from datetime import date

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
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phoneNumber: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    bloodGroup: Optional[str] = None
    heightCm: Optional[float] = None
    weightKg: Optional[float] = None
    currentLocation: Optional[str] = None
    birthPlace: Optional[str] = None
    nationality: Optional[str] = None
    dateOfBirth: Optional[str] = None
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

def calculate_age(date_of_birth: date) -> int:
    """Calculate age from date of birth"""
    today = date.today()
    return today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))

@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's profile information.
    
    Requires authentication.
    """
    # Get patient data from related tables
    from ...application.services.patient_service import PatientService
    
    patient_profile = await PatientService.get_patient_profile(db, str(current_user.id))
    persona = patient_profile.get("persona", {})
    pii = patient_profile.get("pii", {})
    
    # Parse full name into first and last name
    full_name = pii.get("full_name", "")
    name_parts = full_name.split(" ", 1) if full_name else ["", ""]
    first_name = name_parts[0] if len(name_parts) > 0 else None
    last_name = name_parts[1] if len(name_parts) > 1 else None
    
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "firstName": first_name,
        "lastName": last_name,
        "phoneNumber": pii.get("phone_number"),
        "age": persona.get("age"),
        "gender": persona.get("gender"),
        "bloodGroup": persona.get("blood_group"),
        "heightCm": persona.get("height_cm"),
        "weightKg": persona.get("weight_kg"),
        "currentLocation": persona.get("current_location"),
        "birthPlace": persona.get("birth_place"),
        "nationality": persona.get("nationality"),
        "dateOfBirth": persona.get("date_of_birth"),
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
    - firstName, lastName, phoneNumber (PII - encrypted)
    - gender, bloodGroup, heightCm, weightKg, currentLocation, birthPlace, nationality, dateOfBirth (Persona)
    
    NOT allowed:
    - email (cannot be changed for security reasons)
    
    Requires authentication.
    """
    from ...application.services.patient_service import PatientService
    from ...infrastructure.database.patient_models import PatientPII, PatientPersona
    from sqlalchemy import select
    
    # Get current patient data
    patient_profile = await PatientService.get_patient_profile(db, str(current_user.id))
    pii = patient_profile.get("pii", {})
    
    changes = {}
    
    # Handle PII updates (firstName, lastName, phoneNumber)
    pii_updates = {}
    
    if "firstName" in update_data or "lastName" in update_data:
        # Get current full name
        current_full_name = pii.get("full_name", "")
        name_parts = current_full_name.split(" ", 1) if current_full_name else ["", ""]
        current_first = name_parts[0] if len(name_parts) > 0 else ""
        current_last = name_parts[1] if len(name_parts) > 1 else ""
        
        # Update with new values
        new_first = update_data.get("firstName", current_first)
        new_last = update_data.get("lastName", current_last)
        new_full_name = f"{new_first} {new_last}".strip()
        
        if new_full_name != current_full_name:
            pii_updates["full_name"] = new_full_name
            changes["firstName"] = new_first
            changes["lastName"] = new_last
    
    if "phoneNumber" in update_data:
        pii_updates["phone_number"] = update_data["phoneNumber"]
        changes["phoneNumber"] = update_data["phoneNumber"]
    
    # Update PII if there are changes
    if pii_updates:
        await PatientService.update_patient_pii(
            db, 
            str(current_user.id), 
            pii_updates,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
    
    # Handle Persona updates (gender, blood_group, height, weight, location, etc.)
    persona_updates = {}
    
    if "gender" in update_data and update_data["gender"] is not None:
        persona_updates["gender"] = update_data["gender"]
        changes["gender"] = update_data["gender"]
    
    if "bloodGroup" in update_data and update_data["bloodGroup"] is not None:
        persona_updates["blood_group"] = update_data["bloodGroup"]
        changes["bloodGroup"] = update_data["bloodGroup"]
    
    if "heightCm" in update_data and update_data["heightCm"] is not None:
        persona_updates["height_cm"] = update_data["heightCm"]
        changes["heightCm"] = update_data["heightCm"]
    
    if "weightKg" in update_data and update_data["weightKg"] is not None:
        persona_updates["weight_kg"] = update_data["weightKg"]
        changes["weightKg"] = update_data["weightKg"]
    
    if "currentLocation" in update_data and update_data["currentLocation"] is not None:
        persona_updates["current_location"] = update_data["currentLocation"]
        changes["currentLocation"] = update_data["currentLocation"]
    
    if "birthPlace" in update_data and update_data["birthPlace"] is not None:
        persona_updates["birth_place"] = update_data["birthPlace"]
        changes["birthPlace"] = update_data["birthPlace"]
    
    if "nationality" in update_data and update_data["nationality"] is not None:
        persona_updates["nationality"] = update_data["nationality"]
        changes["nationality"] = update_data["nationality"]
    
    if "dateOfBirth" in update_data and update_data["dateOfBirth"] is not None:
        # Parse date string to date object
        from datetime import datetime
        dob_str = update_data["dateOfBirth"]
        try:
            dob = datetime.fromisoformat(dob_str.replace('Z', '+00:00')).date()
            persona_updates["date_of_birth"] = dob
            changes["dateOfBirth"] = dob_str
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid dateOfBirth format. Use ISO format (YYYY-MM-DD)"
            )
    
    # Update Persona if there are changes
    if persona_updates:
        await PatientService.update_patient_persona(
            db, 
            str(current_user.id), 
            persona_updates,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
    
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
    
    # Get updated profile
    updated_profile = await PatientService.get_patient_profile(db, str(current_user.id))
    updated_persona = updated_profile.get("persona", {})
    updated_pii = updated_profile.get("pii", {})
    
    # Parse full name
    full_name = updated_pii.get("full_name", "")
    name_parts = full_name.split(" ", 1) if full_name else ["", ""]
    first_name = name_parts[0] if len(name_parts) > 0 else None
    last_name = name_parts[1] if len(name_parts) > 1 else None
    
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "firstName": first_name,
        "lastName": last_name,
        "phoneNumber": updated_pii.get("phone_number"),
        "age": updated_persona.get("age"),
        "gender": updated_persona.get("gender"),
        "bloodGroup": updated_persona.get("blood_group"),
        "heightCm": updated_persona.get("height_cm"),
        "weightKg": updated_persona.get("weight_kg"),
        "currentLocation": updated_persona.get("current_location"),
        "birthPlace": updated_persona.get("birth_place"),
        "nationality": updated_persona.get("nationality"),
        "dateOfBirth": updated_persona.get("date_of_birth"),
        "isActive": current_user.is_active,
        "createdAt": current_user.created_at.isoformat()
    }
