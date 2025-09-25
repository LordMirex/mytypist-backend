"""
Signature model and related functionality
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, LargeBinary
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from enum import Enum

from database import Base

class SignatureType(Enum):
    """Signature input types"""
    DRAW = "draw"
    TYPE = "type"
    UPLOAD = "upload"
    CANVAS = "canvas"

class SignatureStatus(Enum):
    """Signature processing status"""
    PENDING = "pending"
    PROCESSED = "processed"
    VERIFIED = "verified"
    REJECTED = "rejected"


class Signature(Base):
    """Digital signature model"""
    __tablename__ = "signatures"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    
    # Signer information
    signer_name = Column(String(200), nullable=False)
    signer_email = Column(String(255), nullable=True)
    signer_phone = Column(String(20), nullable=True)
    signer_ip = Column(String(45), nullable=True)
    signer_user_agent = Column(Text, nullable=True)
    
    # Signature data
    signature_data = Column(LargeBinary, nullable=False)  # Binary signature image
    signature_base64 = Column(Text, nullable=True)  # Base64 encoded signature
    signature_type = Column(String(20), nullable=False, default="draw")  # draw, type, upload
    
    # Position and formatting
    page_number = Column(Integer, nullable=False, default=1)
    x_position = Column(Integer, nullable=True)  # X coordinate
    y_position = Column(Integer, nullable=True)  # Y coordinate
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    
    # Verification and security
    is_verified = Column(Boolean, nullable=False, default=False)
    verification_method = Column(String(50), nullable=True)  # email, sms, biometric
    verification_token = Column(String(100), nullable=True)
    verification_expires_at = Column(DateTime, nullable=True)
    
    # Digital signature integrity
    hash_algorithm = Column(String(20), nullable=False, default="SHA256")
    signature_hash = Column(String(64), nullable=False)  # Hash of signature data
    document_hash_at_signing = Column(String(64), nullable=True)  # Document hash when signed
    
    # Legal and compliance
    consent_given = Column(Boolean, nullable=False, default=False)
    consent_text = Column(Text, nullable=True)
    consent_timestamp = Column(DateTime, nullable=True)
    legal_notice_shown = Column(Boolean, nullable=False, default=False)
    
    # Audit trail
    signing_session_id = Column(String(100), nullable=True)
    signing_device_info = Column(Text, nullable=True)  # JSON device information
    geolocation = Column(String(100), nullable=True)  # "lat,lng" format
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    rejected = Column(Boolean, nullable=False, default=False)
    rejection_reason = Column(Text, nullable=True)
    
    # Timestamps
    signed_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="signatures")
    
    def __repr__(self):
        return f"<Signature(id={self.id}, signer='{self.signer_name}', document_id={self.document_id})>"
    
    @property
    def is_valid(self):
        """Check if signature is valid and active"""
        return (
            getattr(self, 'is_active', False) and
            not getattr(self, 'rejected', False) and
            getattr(self, 'consent_given', False)
        )
