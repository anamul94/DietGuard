from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime

from ...infrastructure.database.database import get_db
from ...infrastructure.database.auth_models import User
from ...application.services.auth_service import AuthService
from ...application.services.audit_service import AuditService
from ...infrastructure.auth.jwt import verify_token, create_access_token, get_current_user
from ...infrastructure.utils.logger import logger
from ...infrastructure.utils.date_utils import validate_date_of_birth

router = APIRouter(tags=["Authentication"])

# Request/Response Models
class SignUpRequest(BaseModel):
    # Authentication
    email: EmailStr
    password: str = Field(..., min_length=6)
    
    # Patient PII (will be encrypted)
    full_name: str = Field(..., min_length=1, max_length=200, description="Full name")
    phone_number: Optional[str] = Field(None, min_length=10, max_length=20, description="Contact/Phone number")
    
    # Patient Persona (not encrypted)
    gender: Optional[str] = Field(None, pattern="^(male|female|other|prefer_not_to_say)$")
    blood_group: Optional[str] = Field(None, pattern="^(A\\+|A-|B\\+|B-|AB\\+|AB-|O\\+|O-)$")
    height_cm: Optional[float] = Field(None, ge=50, le=300, description="Height in cm")
    weight_kg: Optional[float] = Field(None, ge=20, le=500, description="Weight in kg")
    current_location: Optional[str] = Field(None, max_length=100, description="Current city/state")
    birth_place: Optional[str] = Field(None, max_length=100, description="Birth city/country")
    nationality: Optional[str] = Field(None, max_length=50, description="Nationality")
    date_of_birth: Optional[datetime] = Field(None, description="Date of birth in ISO format (age will be calculated)")
    
    @field_validator('date_of_birth')
    @classmethod
    def validate_dob(cls, v):
        if v and not validate_date_of_birth(v, min_age=13):
            raise ValueError('Invalid date of birth. User must be at least 13 years old.')
        return v

class SignInRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    user: dict
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)

class MessageResponse(BaseModel):
    message: str

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: Request,
    user_data: SignUpRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user with patient data (HIPAA-compliant).
    
    Args:
        user_data: User registration data including patient PII and persona
        
    Returns:
        User info with patient data and JWT tokens
        
    Raises:
        HTTPException: 400 for validation errors or duplicate email
    """
    try:
        result = await AuthService.signup(
            db=db,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            phone_number=user_data.phone_number,
            gender=user_data.gender,
            blood_group=user_data.blood_group,
            height_cm=user_data.height_cm,
            weight_kg=user_data.weight_kg,
            current_location=user_data.current_location,
            birth_place=user_data.birth_place,
            nationality=user_data.nationality,
            date_of_birth=user_data.date_of_birth,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        # Log successful registration
        await AuditService.log_auth_event(
            db=db,
            action="signup_success",
            email=user_data.email,
            success=True,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            user_id=result["user"]["id"]
        )
        
        return result
    
    except ValueError as e:
        # Log failed registration
        await AuditService.log_auth_event(
            db=db,
            action="signup_failed",
            email=user_data.email,
            success=False,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/signin", response_model=AuthResponse)
async def signin(
    request: Request,
    credentials: SignInRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Sign in a user.
    
    Args:
        credentials: User credentials (email and password)
        
    Returns:
        User info and JWT tokens
        
    Raises:
        HTTPException: 401 for invalid credentials, 403 for inactive account
    """
    try:
        result = await AuthService.authenticate_user(
            db=db,
            email=credentials.email,
            password=credentials.password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        # Log successful login
        await AuditService.log_auth_event(
            db=db,
            action="login_success",
            email=credentials.email,
            success=True,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            user_id=result["user"]["id"]
        )
        
        return result
    
    except ValueError as e:
        # Log failed login
        await AuditService.log_auth_event(
            db=db,
            action="login_failed",
            email=credentials.email,
            success=False,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        error_msg = str(e).lower()
        if "not found" in error_msg or "invalid" in error_msg or "incorrect" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        elif "inactive" in error_msg or "disabled" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Please contact support."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )
    
    except Exception as e:
        # Log unexpected error
        logger.error(f"Signin error: {str(e)}", exc_info=True)
        await AuditService.log_auth_event(
            db=db,
            action="login_error",
            email=credentials.email,
            success=False,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service temporarily unavailable. Please try again later."
        )

@router.post("/refresh-token", response_model=dict)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    
    - **refresh_token**: Valid refresh token
    """
    # Verify refresh token
    payload = verify_token(refresh_data.refresh_token, token_type="refresh")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    user_id = payload.get("sub")
    email = payload.get("email")
    
    # Create new access token
    new_access_token = create_access_token({"sub": user_id, "email": email})
    
    logger.info("Access token refreshed", user_id=user_id)
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request: Request,
    forgot_data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate password reset process.
    
    - **email**: User's email address
    
    Note: In production, this will send an email with reset link.
    For now, the token is logged to console.
    """
    try:
        await AuthService.initiate_password_reset(
            db=db,
            email=forgot_data.email
        )
        
        # Log password reset request
        await AuditService.log_event(
            db=db,
            action="password_reset_requested",
            resource="authentication",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            extra_data={"email": forgot_data.email}
        )
        
        return {"message": "If the email exists, a password reset link has been sent"}
    
    except ValueError as e:
        # Still return success message for security (don't reveal if email exists)
        return {"message": "If the email exists, a password reset link has been sent"}

@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: Request,
    reset_data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password using reset token.
    
    - **token**: Password reset token (from email)
    - **new_password**: New password (minimum 8 characters with complexity requirements)
    """
    try:
        await AuthService.reset_password(
            db=db,
            token=reset_data.token,
            new_password=reset_data.new_password
        )
        
        # Log successful password reset
        await AuditService.log_event(
            db=db,
            action="password_reset_success",
            resource="authentication",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        return {"message": "Password reset successful"}
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/delete-account", response_model=MessageResponse)
async def delete_account(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete user account (HIPAA-compliant).
    
    This endpoint:
    - Deletes all PII (PatientPII) - CASCADE
    - Anonymizes persona data (sets user_id to NULL)
    - Soft deletes the user account
    - Logs the action for HIPAA audit
    
    Requires JWT authentication.
    
    Returns:
        Success message confirming account deletion
    """
    try:
        # Get user from database
        user_result = await db.execute(
            select(User).where(User.id == current_user["user_id"])
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user.deleted_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account already deleted"
            )
        
        # Delete account (HIPAA-compliant: deletes PII, anonymizes persona)
        await AuthService.delete_user_account(
            db=db,
            user=user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        logger.info("User account deleted", user_id=str(user.id))
        
        return {
            "message": "Account successfully deleted. All personal information has been removed."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete account error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account. Please try again later."
        )
