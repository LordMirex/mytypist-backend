"""
User-related Pydantic schemas
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator
from app.models.user import UserRole, UserStatus


class UserBase(BaseModel):
    """Base user schema"""
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, pattern=r"^\+?[1-9]\d{1,14}$")
    company: Optional[str] = Field(None, max_length=200)
    job_title: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=1000)


class UserCreate(UserBase):
    """User creation schema"""
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str
    role: UserRole = UserRole.USER
    gdpr_consent: bool = True
    marketing_consent: bool = False
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)
        
        if not (has_upper and has_lower and has_digit and has_special):
            raise ValueError(
                'Password must contain at least one uppercase letter, '
                'one lowercase letter, one digit, and one special character'
            )
        
        return v


class UserUpdate(BaseModel):
    """User update schema"""
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, pattern=r"^\+?[1-9]\d{1,14}$")
    company: Optional[str] = Field(None, max_length=200)
    job_title: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=1000)
    avatar_url: Optional[str] = Field(None, max_length=500)


class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr
    password: str
    remember_me: bool = False


class UserPasswordChange(BaseModel):
    """Password change schema"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class UserSettings(BaseModel):
    """User settings schema"""
    language: str = Field("en", pattern=r"^[a-z]{2}$")
    timezone: str = Field("Africa/Lagos", max_length=50)
    email_notifications: bool = True
    sms_notifications: bool = False
    marketing_consent: bool = False


class UserProfile(BaseModel):
    """User profile response schema"""
    id: int
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    phone: Optional[str]
    company: Optional[str]
    job_title: Optional[str]
    bio: Optional[str]
    avatar_url: Optional[str]
    role: UserRole
    status: UserStatus
    email_verified: bool
    phone_verified: bool
    two_factor_enabled: bool
    language: str
    timezone: str
    email_notifications: bool
    sms_notifications: bool
    marketing_consent: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Basic user response schema"""
    id: int
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    role: UserRole
    status: UserStatus
    email_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserList(BaseModel):
    """User list response schema"""
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    pages: int


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class PasswordResetRequest(BaseModel):
    """Password reset request schema"""
    email: EmailStr


class PasswordReset(BaseModel):
    """Password reset schema"""
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class EmailVerification(BaseModel):
    """Email verification schema"""
    token: str


class TwoFactorSetup(BaseModel):
    """Two-factor authentication setup schema"""
    secret: str
    qr_code: str


class TwoFactorVerify(BaseModel):
    """Two-factor authentication verification schema"""
    code: str = Field(..., pattern=r"^\d{6}$")
