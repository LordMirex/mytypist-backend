"""
Signature-related Pydantic schemas
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, validator
import base64


class SignatureBase(BaseModel):
    """Base signature schema"""
    signer_name: str = Field(..., min_length=1, max_length=200)
    signer_email: Optional[EmailStr] = None
    signer_phone: Optional[str] = Field(None, pattern=r"^\+?[1-9]\d{1,14}$")


class SignatureCreate(SignatureBase):
    """Signature creation schema"""
    document_id: int
    signature_data: str  # Base64 encoded signature image
    signature_type: str = Field("draw", pattern=r"^(draw|type|upload)$")
    page_number: int = Field(1, ge=1)
    x_position: Optional[int] = Field(None, ge=0)
    y_position: Optional[int] = Field(None, ge=0)
    width: Optional[int] = Field(None, ge=1)
    height: Optional[int] = Field(None, ge=1)
    consent_given: bool = True
    consent_text: Optional[str] = Field(None, max_length=1000)
    
    @validator('signature_data')
    def validate_signature_data(cls, v):
        """Validate base64 signature data"""
        try:
            # Remove data URL prefix if present
            if v.startswith('data:image/'):
                v = v.split(',', 1)[1]
            
            # Validate base64
            decoded = base64.b64decode(v)
            
            # Basic size validation (max 5MB)
            if len(decoded) > 5 * 1024 * 1024:
                raise ValueError('Signature image too large (max 5MB)')
                
            return v
        except Exception:
            raise ValueError('Invalid base64 signature data')


class SignatureUpdate(BaseModel):
    """Signature update schema"""
    signer_name: Optional[str] = Field(None, min_length=1, max_length=200)
    signer_email: Optional[EmailStr] = None
    signer_phone: Optional[str] = Field(None, pattern=r"^\+?[1-9]\d{1,14}$")
    is_verified: Optional[bool] = None
    verification_method: Optional[str] = Field(None, pattern=r"^(email|sms|biometric)$")


class SignatureResponse(BaseModel):
    """Signature response schema"""
    id: int
    document_id: int
    signer_name: str
    signer_email: Optional[str]
    signer_phone: Optional[str]
    signature_type: str
    page_number: int
    x_position: Optional[int]
    y_position: Optional[int]
    width: Optional[int]
    height: Optional[int]
    is_verified: bool
    verification_method: Optional[str]
    consent_given: bool
    consent_timestamp: Optional[datetime]
    is_active: bool
    rejected: bool
    rejection_reason: Optional[str]
    signed_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True


class SignatureVerify(BaseModel):
    """Signature verification schema"""
    verification_token: str
    verification_code: Optional[str] = Field(None, pattern=r"^\d{6}$")


class SignatureRequest(BaseModel):
    """Signature request schema"""
    document_id: int
    signer_email: EmailStr
    signer_name: str
    message: Optional[str] = Field(None, max_length=500)
    expires_in_days: int = Field(7, ge=1, le=30)
    reminder_enabled: bool = True
    reminder_days: int = Field(3, ge=1, le=7)


class SignatureRequestResponse(BaseModel):
    """Signature request response schema"""
    id: int
    document_id: int
    signer_email: str
    signer_name: str
    request_token: str
    status: str
    expires_at: datetime
    sent_at: datetime
    
    class Config:
        from_attributes = True


class SignatureCanvas(BaseModel):
    """Signature canvas configuration schema"""
    width: int = Field(400, ge=200, le=800)
    height: int = Field(200, ge=100, le=400)
    pen_color: str = Field("#000000", pattern=r"^#[0-9A-Fa-f]{6}$")
    pen_width: int = Field(2, ge=1, le=10)
    background_color: str = Field("#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")


class SignatureValidation(BaseModel):
    """Signature validation response schema"""
    is_valid: bool
    signature_hash: str
    document_hash: str
    signed_at: datetime
    signer_info: dict
    validation_errors: list = []


class SignatureBatch(BaseModel):
    """Batch signature request schema"""
    document_id: int
    signers: list = Field(..., min_items=1, max_items=10)
    message: Optional[str] = Field(None, max_length=500)
    expires_in_days: int = Field(7, ge=1, le=30)
    
    @validator('signers')
    def validate_signers(cls, v):
        for i, signer in enumerate(v):
            if 'email' not in signer:
                raise ValueError(f'Signer {i+1} missing required field: email')
            if 'name' not in signer:
                raise ValueError(f'Signer {i+1} missing required field: name')
        return v


class SignatureStats(BaseModel):
    """Signature statistics schema"""
    total_signatures: int
    verified_signatures: int
    pending_signatures: int
    rejected_signatures: int
    average_signing_time: float
    completion_rate: float
