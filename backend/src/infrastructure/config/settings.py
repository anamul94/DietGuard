import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Database
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "dietguard")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "password")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "dietguard")
    
    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200"))  # 30 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    
    # Security
    ADMIN_KEY: str = os.getenv("ADMIN_KEY", "your_secure_admin_api_key_here")
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_HOURS", "1"))
    RATE_LIMIT_LOGIN_ATTEMPTS: int = int(os.getenv("RATE_LIMIT_LOGIN_ATTEMPTS", "5"))
    RATE_LIMIT_LOGIN_WINDOW_MINUTES: int = int(os.getenv("RATE_LIMIT_LOGIN_WINDOW_MINUTES", "15"))
    
    # AWS
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_SESSION_TOKEN: Optional[str] = os.getenv("AWS_SESSION_TOKEN")
    AWS_PROFILE: Optional[str] = os.getenv("AWS_PROFILE")
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")

    # AWS Transcribe (Mood check-ins)
    TRANSCRIBE_S3_BUCKET: Optional[str] = os.getenv("TRANSCRIBE_S3_BUCKET")
    TRANSCRIBE_S3_PREFIX: str = os.getenv("TRANSCRIBE_S3_PREFIX", "mood-checkins/")
    TRANSCRIBE_LANGUAGE_CODE: str = os.getenv("TRANSCRIBE_LANGUAGE_CODE", "en-US")
    TRANSCRIBE_TIMEOUT_SECONDS: int = int(os.getenv("TRANSCRIBE_TIMEOUT_SECONDS", "180"))
    TRANSCRIBE_POLL_INTERVAL_SECONDS: float = float(os.getenv("TRANSCRIBE_POLL_INTERVAL_SECONDS", "2"))
    MAX_MOOD_AUDIO_MB: int = int(os.getenv("MAX_MOOD_AUDIO_MB", "12"))
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "myredissecret")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Subscription
    FREE_TIER_DAILY_UPLOAD_LIMIT: int = int(os.getenv("FREE_TIER_DAILY_UPLOAD_LIMIT", "2"))

settings = Settings()
