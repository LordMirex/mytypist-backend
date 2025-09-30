"""
Configuration settings for MyTypist backend
"""

import os
import secrets
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "MyTypist"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY")

    # PostgreSQL settings
    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Redis (optional for caching and rate limiting)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD")
    REDIS_URL: str = os.getenv("REDIS_URL",
                               f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0" if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}/0")
    REDIS_ENABLED: bool = os.getenv(
        "REDIS_ENABLED",
        "true").lower() == "true"  # Enabled for production use

    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

    # JWT - Secure configuration with validation
    JWT_SECRET_KEY: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY", ""))

    @field_validator('JWT_SECRET_KEY')
    @classmethod
    def validate_jwt_secret_key(cls, value: str) -> str:
        """Validate JWT secret key for security"""

        # Allow empty key for development
        if not value or value.strip() == "":
            if os.getenv("DEBUG", "false").lower() == "true":
                print("⚠️ WARNING: Using default JWT key for development")
                return "dev-jwt-secret-key-32-characters-minimum"
            else:
                raise ValueError(
                    "JWT_SECRET_KEY environment variable is required for production. "
                    "Please set a cryptographically secure random key (32+ characters)."
                )

        # Validate key strength for production
        if len(value) < 32:
            if os.getenv("DEBUG", "false").lower() == "true":
                print("⚠️ WARNING: JWT key shorter than recommended for development")
                return value
            else:
                raise ValueError(
                    f"JWT_SECRET_KEY must be at least 32 characters long for production. "
                    f"Current length: {len(value)}")

        # Reject weak/default keys in production
        if os.getenv("DEBUG", "false").lower() != "true":
            weak_keys = [
                "your-super-secret-key-change-this-for-production", "secret",
                "key", "password", "jwt-secret", "change-me", "dev-jwt-secret-key-32-characters-minimum"
            ]
            if value.lower() in [key.lower() for key in weak_keys]:
                raise ValueError(
                    "JWT_SECRET_KEY cannot be a common/weak value in production. "
                    "Please use a cryptographically secure random key.")

        return value

    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Security - Configure for production
    ALLOWED_HOSTS: List[str] = os.getenv("ALLOWED_HOSTS", "").split(",")
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "").split(",")

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds

    # File Storage
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "./storage")
    TEMPLATES_PATH: str = os.path.join(STORAGE_PATH, "templates")
    DOCUMENTS_PATH: str = os.path.join(STORAGE_PATH, "documents")
    SIGNATURES_PATH: str = os.path.join(STORAGE_PATH, "signatures")
    UPLOADS_PATH: str = os.path.join(STORAGE_PATH, "uploads")
    QUARANTINE_PATH: str = os.path.join(STORAGE_PATH, "quarantine")
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB for production
    ALLOWED_EXTENSIONS: List[str] = [
        ".docx", ".doc", ".pdf", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg"
    ]

    # MIME type validation
    ALLOWED_MIME_TYPES: List[str] = [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword", "application/pdf",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "image/png", "image/jpeg"
    ]

    # Thumbnails
    THUMBNAILS_PATH: str = os.getenv("THUMBNAILS_PATH",
                                     os.path.join(STORAGE_PATH, "thumbnails"))
    # When True, attempt to generate thumbnails synchronously for previews (may be skipped in async environments).
    ENABLE_SYNC_THUMBNAILS: bool = os.getenv("ENABLE_SYNC_THUMBNAILS",
                                             "false").lower() == "true"

    # Flutterwave
    FLUTTERWAVE_PUBLIC_KEY: str = os.getenv("FLUTTERWAVE_PUBLIC_KEY", "")
    FLUTTERWAVE_SECRET_KEY: str = os.getenv("FLUTTERWAVE_SECRET_KEY", "")
    FLUTTERWAVE_BASE_URL: str = "https://api.flutterwave.com/api"
    FLUTTERWAVE_WEBHOOK_SECRET: str = os.getenv("FLUTTERWAVE_WEBHOOK_SECRET",
                                                "")

    # Email Settings - SendGrid Integration
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    SENDGRID_FROM_EMAIL: str = os.getenv("SENDGRID_FROM_EMAIL",
                                         "noreply@mytypist.com")
    SENDGRID_FROM_NAME: str = os.getenv("SENDGRID_FROM_NAME", "MyTypist")

    # Frontend URL for email links
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://mytypist.com")

    # Legacy SMTP (for backup)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@mytypist.com")

    # Performance
    CACHE_TTL: int = 3600  # 1 hour
    TEMPLATE_CACHE_TTL: int = 86400  # 24 hours
    DOCUMENT_GENERATION_TIMEOUT: int = 30  # seconds

    # Advanced Performance Settings
    MAX_CONCURRENT_UPLOADS: int = 10
    COMPRESSION_THRESHOLD: int = 1024  # Compress responses > 1KB
    SLOW_REQUEST_THRESHOLD: float = 1.0  # Log requests > 1 second
    ENCRYPTION_ENABLED: bool = True

    # Database Performance
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "20"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "30"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    # Control dev shortcuts
    # When True the app will skip any automatic DB table creation at startup.
    SKIP_DB_TABLE_CREATION: bool = os.getenv("SKIP_DB_TABLE_CREATION",
                                             "false").lower() == "true"

    # Compliance
    GDPR_ENABLED: bool = True
    SOC2_ENABLED: bool = True
    AUDIT_LOG_RETENTION_DAYS: int = 2555  # 7 years

    # Subscription Plans
    FREE_PLAN_DOCUMENTS_PER_MONTH: int = 5
    BASIC_PLAN_DOCUMENTS_PER_MONTH: int = 100
    PRO_PLAN_DOCUMENTS_PER_MONTH: int = 1000
    ENTERPRISE_PLAN_DOCUMENTS_PER_MONTH: int = -1  # unlimited

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()

# Ensure directories exist
os.makedirs(settings.STORAGE_PATH, exist_ok=True)
os.makedirs(settings.TEMPLATES_PATH, exist_ok=True)
os.makedirs(settings.DOCUMENTS_PATH, exist_ok=True)
os.makedirs(settings.SIGNATURES_PATH, exist_ok=True)
