"""
Document-related Pydantic schemas
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from app.models.document import DocumentStatus, DocumentAccess


class DocumentBase(BaseModel):
    """Base document schema"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    access_level: DocumentAccess = DocumentAccess.PRIVATE
    requires_signature: bool = False
    required_signature_count: int = Field(0, ge=0, le=10)
    auto_delete: bool = False

    @validator('required_signature_count')
    def validate_signature_count(cls, v, values):
        if 'requires_signature' in values and values['requires_signature'] and v == 0:
            raise ValueError('required_signature_count must be greater than 0 when signature is required')
        return v


class DocumentCustomization(BaseModel):
    """Document customization options"""
    font: Optional[str] = Field(None, pattern=r"^[A-Za-z ]+$")
    size: Optional[int] = Field(None, ge=8, le=14)
    replacements: Optional[Dict[str, str]] = {}


class DocumentCreate(DocumentBase):
    """Document creation schema"""
    template_id: Optional[int] = None
    placeholder_data: Optional[Dict[str, Any]] = {}
    content: Optional[str] = None
    file_format: str = Field("docx", pattern=r"^(docx|pdf)$")
    customization: Optional[DocumentCustomization] = None


class DocumentUpdate(BaseModel):
    """Document update schema"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    content: Optional[str] = None
    access_level: Optional[DocumentAccess] = None
    requires_signature: Optional[bool] = None
    required_signature_count: Optional[int] = Field(None, ge=0, le=10)
    auto_delete: Optional[bool] = None


class DocumentGenerate(BaseModel):
    """Document generation schema"""
    template_id: int
    placeholder_data: Dict[str, Any]
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    file_format: str = Field("docx", pattern=r"^(docx|pdf)$")
    access_level: DocumentAccess = DocumentAccess.PRIVATE
    requires_signature: bool = False
    required_signature_count: int = Field(0, ge=0, le=10)

    @validator('placeholder_data')
    def validate_placeholder_data(cls, v):
        if not v:
            raise ValueError('placeholder_data cannot be empty')
        return v


class DocumentShare(BaseModel):
    """Document sharing schema"""
    access_level: DocumentAccess
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    password_protected: bool = False
    password: Optional[str] = Field(None, min_length=4, max_length=50)

    @validator('password')
    def validate_password(cls, v, values):
        if 'password_protected' in values and values['password_protected'] and not v:
            raise ValueError('password is required when password_protected is True')
        return v


class DocumentResponse(BaseModel):
    """Document response schema"""
    id: int
    title: str
    description: Optional[str]
    status: DocumentStatus
    access_level: DocumentAccess
    version: str
    file_path: Optional[str]
    file_size: Optional[int]
    file_format: str
    requires_signature: bool
    signature_count: int
    required_signature_count: int
    generation_time: Optional[float]
    download_count: int
    view_count: int
    share_token: Optional[str]
    share_expires_at: Optional[datetime]
    user_id: int
    template_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    """Document list response schema"""
    documents: List[DocumentResponse]
    total: int
    page: int
    per_page: int
    pages: int


class DocumentDownload(BaseModel):
    """Document download response schema"""
    url: str
    filename: str
    size: int
    format: str
    expires_at: datetime


class DocumentPreview(BaseModel):
    """Document preview schema"""
    id: int
    title: str
    content_preview: str
    thumbnail_url: Optional[str]
    page_count: int
    watermarked: bool = True


class DocumentSearch(BaseModel):
    """Document search schema"""
    query: Optional[str] = None
    status: Optional[DocumentStatus] = None
    template_id: Optional[int] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    sort_by: str = Field("created_at", pattern=r"^(created_at|title|status|updated_at)$")
    sort_order: str = Field("desc", pattern=r"^(asc|desc)$")
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)


class DocumentStats(BaseModel):
    """Document statistics schema"""
    total_documents: int
    completed_documents: int
    draft_documents: int
    failed_documents: int
    total_size: int
    this_month: int
    last_month: int
    growth_rate: float


class DocumentBatchItem(BaseModel):
    """Individual document in batch"""
    title: str
    template_id: int
    placeholder_data: Dict[str, Any] = {}
    description: Optional[str] = None


class DocumentBatchSettings(BaseModel):
    """Batch processing settings"""
    enable_consolidation: bool = True
    consolidation_threshold: int = 2  # Minimum documents to trigger consolidation
    preserve_individual_styling: bool = True
    generate_consolidated_preview: bool = True


class DocumentBatch(BaseModel):
    """Enhanced batch document generation schema"""
    documents: List[DocumentBatchItem] = Field(..., min_items=1, max_items=100)
    file_format: str = Field("docx", pattern=r"^(docx|pdf)$")
    batch_settings: Optional[DocumentBatchSettings] = DocumentBatchSettings()

    @validator('documents')
    def validate_documents(cls, v):
        template_ids = [doc.template_id for doc in v]
        if len(set(template_ids)) > 10:
            raise ValueError('Maximum 10 different templates allowed in a batch')
        return v


class ConsolidationSummary(BaseModel):
    """Summary of input consolidation"""
    original_input_count: int
    consolidated_input_count: int
    reduction_percentage: float
    duplicate_groups: int


class DocumentBatchResponse(BaseModel):
    """Enhanced batch document generation response schema"""
    batch_id: str
    total_documents: int
    processing_status: str
    estimated_completion: datetime
    documents: List[DocumentResponse] = []
    consolidation_summary: Optional[ConsolidationSummary] = None
