"""
Template-related Pydantic schemas
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class PlaceholderCreate(BaseModel):
    """Placeholder creation schema"""
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    display_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    placeholder_type: str = Field("text", pattern=r"^(text|date|number|email|phone|url|select)$")
    is_required: bool = True
    min_length: Optional[int] = Field(None, ge=0)
    max_length: Optional[int] = Field(None, ge=1)
    pattern: Optional[str] = Field(None, max_length=500)
    default_value: Optional[str] = None
    options: Optional[List[str]] = None
    casing: str = Field("none", pattern=r"^(none|upper|lower|title)$")
    
    @validator('max_length')
    def validate_max_length(cls, v, values):
        if v and 'min_length' in values and values['min_length'] and v < values['min_length']:
            raise ValueError('max_length must be greater than min_length')
        return v


class PlaceholderResponse(BaseModel):
    """Placeholder response schema"""
    id: int
    name: str
    display_name: Optional[str]
    description: Optional[str]
    placeholder_type: str
    is_required: bool
    min_length: Optional[int]
    max_length: Optional[int]
    pattern: Optional[str]
    default_value: Optional[str]
    options: Optional[List[str]]
    casing: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class TemplateBase(BaseModel):
    """Base template schema"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    category: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=50)
    language: str = Field("en", pattern=r"^[a-z]{2}$")
    font_family: str = Field("Times New Roman", max_length=100)
    font_size: int = Field(12, ge=8, le=72)
    is_public: bool = False
    is_premium: bool = False
    price: float = Field(0.0, ge=0.0)
    tags: Optional[List[str]] = None
    keywords: Optional[str] = Field(None, max_length=500)


class TemplateCreate(TemplateBase):
    """Template creation schema"""
    placeholders: Optional[List[PlaceholderCreate]] = []
    
    @validator('tags')
    def validate_tags(cls, v):
        if v and len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        return v


class TemplateUpdate(BaseModel):
    """Template update schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[str] = Field(None, min_length=1, max_length=50)
    language: Optional[str] = Field(None, pattern=r"^[a-z]{2}$")
    font_family: Optional[str] = Field(None, max_length=100)
    font_size: Optional[int] = Field(None, ge=8, le=72)
    is_public: Optional[bool] = None
    is_premium: Optional[bool] = None
    price: Optional[float] = Field(None, ge=0.0)
    tags: Optional[List[str]] = None
    keywords: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    """Template response schema"""
    id: int
    name: str
    description: Optional[str]
    category: str
    type: str
    file_path: str
    original_filename: str
    file_size: int
    version: str
    language: str
    font_family: str
    font_size: int
    is_active: bool
    is_public: bool
    is_premium: bool
    price: float
    usage_count: int
    download_count: int
    rating: float
    rating_count: int
    tags: Optional[List[str]]
    keywords: Optional[str]
    created_by: int
    created_at: datetime
    updated_at: datetime
    placeholders: List[PlaceholderResponse] = []
    
    class Config:
        from_attributes = True


class TemplateList(BaseModel):
    """Template list response schema"""
    templates: List[TemplateResponse]
    total: int
    page: int
    per_page: int
    pages: int
    categories: List[str] = []
    types: List[str] = []


class TemplateUpload(BaseModel):
    """Template upload response schema"""
    id: int
    name: str
    file_path: str
    placeholders_found: int
    processing_status: str
    message: str


class TemplatePreview(BaseModel):
    """Template preview schema"""
    id: int
    name: str
    description: Optional[str]
    category: str
    type: str
    placeholders: List[PlaceholderResponse]
    preview_url: Optional[str]
    watermarked: bool = True


class TemplateSearch(BaseModel):
    """Template search schema"""
    query: Optional[str] = None
    category: Optional[str] = None
    type: Optional[str] = None
    language: Optional[str] = None
    is_public: Optional[bool] = None
    is_premium: Optional[bool] = None
    min_price: Optional[float] = Field(None, ge=0.0)
    max_price: Optional[float] = Field(None, ge=0.0)
    tags: Optional[List[str]] = None
    sort_by: str = Field("created_at", pattern=r"^(created_at|name|usage_count|rating|price)$")
    sort_order: str = Field("desc", pattern=r"^(asc|desc)$")
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)
    
    @validator('max_price')
    def validate_price_range(cls, v, values):
        if v and 'min_price' in values and values['min_price'] and v < values['min_price']:
            raise ValueError('max_price must be greater than min_price')
        return v


class TemplateRating(BaseModel):
    """Template rating schema"""
    rating: float = Field(..., ge=1.0, le=5.0)
    comment: Optional[str] = Field(None, max_length=500)


class TemplateStats(BaseModel):
    """Template statistics schema"""
    id: int
    name: str
    usage_count: int
    download_count: int
    rating: float
    rating_count: int
    revenue: float
    created_at: datetime
    last_used: Optional[datetime]


# Template Management Schemas
class CategoryBase(BaseModel):
    """Base schema for template categories"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    parent_id: Optional[int] = None


class CategoryCreate(CategoryBase):
    """Schema for creating a new category"""
    pass


class CategoryUpdate(CategoryBase):
    """Schema for updating a category"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class CategoryResponse(CategoryBase):
    """Schema for category response"""
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
    subcategories: Optional[List['CategoryResponse']] = None

    class Config:
        from_attributes = True


class TemplateVersionBase(BaseModel):
    """Base schema for template versions"""
    version_number: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    changes: List[str]
    metadata: Optional[Dict[str, Any]] = None


class TemplateVersionCreate(TemplateVersionBase):
    """Schema for creating a new template version"""
    pass


class TemplateVersionResponse(TemplateVersionBase):
    """Schema for template version response"""
    id: int
    template_id: int
    content_hash: str
    template_file_path: str
    preview_file_path: str
    created_by: int
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class TemplateApproval(BaseModel):
    """Schema for template approval/rejection"""
    approval_status: str = Field(..., pattern=r"^(approved|rejected)$")
    notes: Optional[str] = Field(None, max_length=1000)


class TemplateReviewBase(BaseModel):
    """Base schema for template reviews"""
    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = Field(None, max_length=1000)


class TemplateReviewCreate(TemplateReviewBase):
    """Schema for creating a new template review"""
    pass


class TemplateReviewResponse(TemplateReviewBase):
    """Schema for template review response"""
    id: int
    template_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True
