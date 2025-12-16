from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import secrets
import uuid

from ...infrastructure.database.auth_models import User, Role, UserRole, Subscription, PasswordReset
from ...infrastructure.auth.password import hash_password, verify_password, validate_password_strength
from ...infrastructure.auth.jwt import create_access_token, create_refresh_token
from ...infrastructure.utils.logger import logger
from ...infrastructure.config.settings import settings

class AuthService:
    """Service for authentication operations"""
    
    @staticmethod
    async def signup(
        db: AsyncSession,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        age: Optional[int] = None,
        gender: Optional[str] = None,
        weight: Optional[float] = None,
        height: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Register a new user.
        
        Args:
            db: Database session
            email: User email
            password: Plain text password
            first_name: User first name
            last_name: User last name
            age: User age (optional)
            gender: User gender (optional)
            
        Returns:
            Dict with user info and tokens
            
        Raises:
            ValueError: If validation fails
        """
        # Validate password strength
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Check if user already exists
        result = await db.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise ValueError("Email already registered")
        
        # Hash password
        password_hash = hash_password(password)
        
        # Create user
        user = User(
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            age=age,
            gender=gender,
            weight=weight,
            height=height,
            is_active=True
        )
        db.add(user)
        await db.flush()  # Flush to get user.id
        
        # Assign default 'user' role
        role_result = await db.execute(select(Role).where(Role.name == "user"))
        user_role_obj = role_result.scalar_one_or_none()
        
        if user_role_obj:
            user_role = UserRole(user_id=user.id, role_id=user_role_obj.id)
            db.add(user_role)
        
        # Create 7-day paid trial subscription for new users
        trial_end_date = datetime.now(timezone.utc) + timedelta(days=7)
        subscription = Subscription(
            user_id=user.id,
            plan_type="paid",
            status="active",
            end_date=trial_end_date
        )
        db.add(subscription)
        
        await db.commit()
        await db.refresh(user)
        
        logger.info("User registered successfully", user_id=str(user.id), email=email)
        
        # Generate tokens
        access_token = create_access_token({"sub": str(user.id), "email": user.email})
        refresh_token = create_refresh_token({"sub": str(user.id), "email": user.email})
        
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "age": user.age,
                "gender": user.gender,
                "weight": float(user.weight) if user.weight else None,
                "height": float(user.height) if user.height else None,
                "is_active": user.is_active,
                "roles": [ur.role.name for ur in user.user_roles]
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str
    ) -> Dict[str, Any]:
        """
        Authenticate a user and return tokens.
        
        Args:
            db: Database session
            email: User email
            password: Plain text password
            
        Returns:
            Dict with user info and tokens
            
        Raises:
            ValueError: If authentication fails
        """
        # Get user
        result = await db.execute(
            select(User).where(
                and_(
                    User.email == email,
                    User.is_active == True,
                    User.deleted_at == None
                )
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning("Login failed - user not found", email=email)
            raise ValueError("Invalid email or password")
        
        # Verify password
        if not verify_password(password, user.password_hash):
            logger.warning("Login failed - invalid password", user_id=str(user.id), email=email)
            raise ValueError("Invalid email or password")
        
        logger.info("User authenticated successfully", user_id=str(user.id), email=email)
        
        # Generate tokens
        access_token = create_access_token({"sub": str(user.id), "email": user.email})
        refresh_token = create_refresh_token({"sub": str(user.id), "email": user.email})
        
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    @staticmethod
    async def initiate_password_reset(
        db: AsyncSession,
        email: str
    ) -> str:
        """
        Initiate password reset process.
        
        Args:
            db: Database session
            email: User email
            
        Returns:
            Reset token (to be sent via email)
            
        Raises:
            ValueError: If user not found
        """
        # Get user
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            # Don't reveal if email exists or not for security
            logger.warning("Password reset requested for non-existent email", email=email)
            raise ValueError("If the email exists, a reset link will be sent")
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        token_hash = hash_password(reset_token)
        
        # Create password reset record
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
        password_reset = PasswordReset(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        db.add(password_reset)
        await db.commit()
        
        logger.info("Password reset initiated", user_id=str(user.id), email=email)
        
        # In production, send email here
        # For now, just log to console
        print(f"\n{'='*60}")
        print(f"PASSWORD RESET TOKEN (send via email in production):")
        print(f"Email: {email}")
        print(f"Token: {reset_token}")
        print(f"Expires: {expires_at}")
        print(f"{'='*60}\n")
        
        return reset_token
    
    @staticmethod
    async def reset_password(
        db: AsyncSession,
        token: str,
        new_password: str
    ) -> bool:
        """
        Reset user password with token.
        
        Args:
            db: Database session
            token: Reset token
            new_password: New password
            
        Returns:
            True if successful
            
        Raises:
            ValueError: If token invalid or password weak
        """
        # Validate new password
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Find valid reset token
        result = await db.execute(
            select(PasswordReset)
            .where(
                and_(
                    PasswordReset.expires_at > datetime.now(timezone.utc),
                    PasswordReset.used_at == None
                )
            )
        )
        password_resets = result.scalars().all()
        
        # Check each token hash
        valid_reset = None
        for reset in password_resets:
            if verify_password(token, reset.token_hash):
                valid_reset = reset
                break
        
        if not valid_reset:
            logger.warning("Invalid or expired password reset token")
            raise ValueError("Invalid or expired reset token")
        
        # Get user
        user_result = await db.execute(select(User).where(User.id == valid_reset.user_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")
        
        # Update password
        user.password_hash = hash_password(new_password)
        valid_reset.used_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        logger.info("Password reset successful", user_id=str(user.id))
        
        return True
    
    @staticmethod
    async def delete_user_account(
        db: AsyncSession,
        user: User
    ) -> bool:
        """
        Soft delete user account (GDPR compliance).
        
        Args:
            db: Database session
            user: User to delete
            
        Returns:
            True if successful
        """
        # Soft delete
        user.deleted_at = datetime.now(timezone.utc)
        user.is_active = False
        
        await db.commit()
        
        logger.info("User account deleted (soft delete)", user_id=str(user.id))
        
        return True
