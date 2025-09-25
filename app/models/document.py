"""
Document model and related functionality
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Float, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from database import Base


class DocumentStatus(str, enum.Enum):
    """Document status enumeration"""
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"
    GUEST = "guest"  # Added guest status for anonymous documents


class DocumentAccess(str, enum.Enum):
    """Document access level enumeration"""
    PRIVATE = "private"
    SHARED = "shared"
    PUBLIC = "public"


class Document(Base):
    """Document model"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Document content and generation
    content = Column(Text, nullable=True)  # Final document content
    placeholder_data = Column(JSON, nullable=True)  # User input data
    generated_content = Column(Text, nullable=True)  # Processed content
    
    # File information
    file_path = Column(String(500), nullable=True)
    original_filename = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)  # bytes
    file_hash = Column(String(64), nullable=True)  # SHA256 hash
    file_format = Column(String(10), nullable=False, default="docx")  # docx, pdf
    
    # Status and metadata
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.DRAFT)
    is_downloaded = Column(Boolean, nullable=False, default=False)  # Track if document was downloaded
    download_count = Column(Integer, nullable=False, default=0)  # Number of downloads
    last_downloaded_at = Column(DateTime, nullable=True)  # Last download timestamp
    
    # SEO and sharing
    is_public = Column(Boolean, nullable=False, default=False)  # Whether document is publicly accessible
    seo_title = Column(String(255), nullable=True)  # SEO optimized title
    seo_description = Column(Text, nullable=True)  # SEO meta description
    view_count = Column(Integer, nullable=False, default=0)  # Number of views
    
    # Document access and sharing
    access_level = Column(Enum(DocumentAccess), nullable=False, default=DocumentAccess.PRIVATE)
    version = Column(String(20), nullable=False, default="1.0")
    
    # Relationships
    visits = relationship("DocumentVisit", back_populates="document", cascade="all, delete-orphan")
    
    # Processing information
    generation_time = Column(Float, nullable=True)  # seconds
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    
    # Sharing and collaboration
    share_token = Column(String(64), nullable=True, unique=True)
    share_expires_at = Column(DateTime, nullable=True)
    
    # Compliance and security
    is_encrypted = Column(Boolean, nullable=False, default=False)
    encryption_key_id = Column(String(100), nullable=True)
    requires_signature = Column(Boolean, nullable=False, default=False)
    signature_count = Column(Integer, nullable=False, default=0)
    required_signature_count = Column(Integer, nullable=False, default=0)
    
    # GDPR and data retention
    gdpr_compliant = Column(Boolean, nullable=False, default=True)
    retention_expires_at = Column(DateTime, nullable=True)
    auto_delete = Column(Boolean, nullable=False, default=False)
    
    # Relationships
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    
    user = relationship("User", back_populates="documents")
    template = relationship("Template", back_populates="documents")
    signatures = relationship("Signature", back_populates="document", cascade="all, delete-orphan")
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Document(id={self.id}, title='{self.title}', status='{self.status}')>"
    
    @property
    def is_completed(self):
        """Check if document generation is completed"""
        return getattr(self, 'status', None) == DocumentStatus.COMPLETED
    
    @property
    def is_accessible(self):
        """Check if document is accessible"""
        from datetime import datetime
        return (
            getattr(self, 'status', None) == DocumentStatus.COMPLETED and
            getattr(self, 'deleted_at', None) is None
        )
    
    @property
    def is_shareable(self):
        """Check if document can be shared"""
        return (
            self.is_accessible and
            getattr(self, 'access_level', None) in [DocumentAccess.SHARED, DocumentAccess.PUBLIC]
        )
    
    @property
    def needs_signature(self):
        """Check if document needs more signatures"""
        return (
            getattr(self, 'requires_signature', False) and
            getattr(self, 'signature_count', 0) < getattr(self, 'required_signature_count', 0)
        )
