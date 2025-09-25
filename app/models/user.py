"""
User model and related functionality
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from database import Base


class UserRole(str, enum.Enum):
    """User role enumeration - Production hierarchy"""
    GUEST = "guest"        # Temporary users, limited access
    USER = "user"          # Standard registered users
    MODERATOR = "moderator"  # Staff members, content moderation
    ADMIN = "admin"        # Full system access


class UserStatus(str, enum.Enum):
    """User status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"
    DELETED = "deleted"


class User(Base):
    """User model"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)

    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)
    status = Column(Enum(UserStatus), nullable=False, default=UserStatus.ACTIVE)

    # Profile information
    company = Column(String(200), nullable=True)
    job_title = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)

    # Settings
    language = Column(String(10), nullable=False, default="en")
    timezone = Column(String(50), nullable=False, default="Africa/Lagos")
    email_notifications = Column(Boolean, nullable=False, default=True)
    sms_notifications = Column(Boolean, nullable=False, default=False)

    # Security
    email_verified = Column(Boolean, nullable=False, default=False)
    phone_verified = Column(Boolean, nullable=False, default=False)
    two_factor_enabled = Column(Boolean, nullable=False, default=False)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    password_changed_at = Column(DateTime, nullable=True)

    # GDPR compliance
    gdpr_consent = Column(Boolean, nullable=False, default=False)
    gdpr_consent_date = Column(DateTime, nullable=True)
    marketing_consent = Column(Boolean, nullable=False, default=False)
    data_retention_consent = Column(Boolean, nullable=False, default=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    templates = relationship("Template", back_populates="creator", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    page_visits = relationship("PageVisit", back_populates="user", lazy="dynamic")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"

    @property
    def full_name(self):
        """Get user's full name"""
        if getattr(self, 'first_name', None) and getattr(self, 'last_name', None):
            return f"{self.first_name} {self.last_name}"
        elif getattr(self, 'first_name', None):
            return self.first_name
        elif getattr(self, 'last_name', None):
            return self.last_name
        else:
            return getattr(self, 'username', '')

    @property
    def is_active(self):
        """Check if user is active"""
        return getattr(self, 'status', None) == UserStatus.ACTIVE and getattr(self, 'deleted_at', None) is None

    @property
    def is_admin(self):
        """Check if user is admin"""
        return getattr(self, 'role', None) == UserRole.ADMIN

    @property
    def is_moderator(self):
        """Check if user is moderator or higher"""
        return getattr(self, 'role', None) in [UserRole.MODERATOR, UserRole.ADMIN]

    @property
    def is_guest(self):
        """Check if user is guest"""
        return getattr(self, 'role', None) == UserRole.GUEST

    @property
    def is_verified(self):
        """Check if user email is verified"""
        return getattr(self, 'email_verified', False)
