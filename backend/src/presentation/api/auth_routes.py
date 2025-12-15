from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from ...infrastructure.database.database import get_db
from ...application.services.auth_service import AuthService
from ...application.services.audit_service import AuditService
from ...infrastructure.auth.jwt import verify_token, create_access_token
from ...infrastructure.utils.logger import logger

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

# Request/Response Models
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    firstName: str = Field(..., min_length=1, max_length=100)
    lastName: str = Field(..., min_length=1, max_length=100)
    age: Optional[int] = Field(None, ge=1, le=150)
    gender: Optional[str] = Field(None, max_length=20)

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
    signup_data: SignUpRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user account.
    
    - **email**: Valid email address (unique)
    - **password**: Minimum 8 characters with complexity requirements
    - **firstName**: User's first name
    - **lastName**: User's last name
    - **age**: Optional age (1-150)
    - **gender**: Optional gender
    """
    try:
        result = await AuthService.register_user(
            db=db,
            email=signup_data.email,
            password=signup_data.password,
            first_name=signup_data.firstName,
            last_name=signup_data.lastName,
            age=signup_data.age,
            gender=signup_data.gender
        )
        
        # Log successful registration
        await AuditService.log_auth_event(
            db=db,
            action="signup_success",
            email=signup_data.email,
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
            email=signup_data.email,
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
    signin_data: SignInRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens.
    
    - **email**: User's email address
    - **password**: User's password
    """
    try:
        result = await AuthService.authenticate_user(
            db=db,
            email=signin_data.email,
            password=signin_data.password
        )
        
        # Log successful login
        await AuditService.log_auth_event(
            db=db,
            action="login_success",
            email=signin_data.email,
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
            email=signin_data.email,
            success=False,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
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
