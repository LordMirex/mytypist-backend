"""
Template and Placeholder models
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class Template(Base):
    """Document template model"""
    __tablename__ = "templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False)  # contract, letter, invoice, etc.
    type = Column(String(50), nullable=False)  # letter, affidavit, contract, etc.
    
    # File information
    file_path = Column(String(500), nullable=False)  # Extraction version
    preview_file_path = Column(String(500), nullable=True)  # Preview version
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    file_hash = Column(String(64), nullable=False)  # SHA256 hash
    
    # Template metadata
    placeholders = Column(JSON, nullable=True)  # JSON array of placeholder info
    version = Column(String(20), nullable=False, default="1.0")
    language = Column(String(10), nullable=False, default="en")
    
    # Formatting
    font_family = Column(String(100), nullable=False, default="Times New Roman")
    font_size = Column(Integer, nullable=False, default=12)
    page_margins = Column(JSON, nullable=True)  # {top, bottom, left, right}
    
    # Usage and access
    is_active = Column(Boolean, nullable=False, default=True)
    is_public = Column(Boolean, nullable=False, default=False)
    is_premium = Column(Boolean, nullable=False, default=False)
    token_cost = Column(Integer, nullable=False, default=1)  # Number of tokens needed
    price = Column(Float, nullable=False, default=0.0)  # in Naira
    special_offer = Column(JSON, nullable=True)  # {discount_percent, start_date, end_date, original_price}
    bulk_pricing_rules = Column(JSON, nullable=True)  # [{min_tokens, max_tokens, price_per_token}]
    
    # Analytics
    usage_count = Column(Integer, nullable=False, default=0)
    download_count = Column(Integer, nullable=False, default=0)
    rating = Column(Float, nullable=False, default=0.0)
    rating_count = Column(Integer, nullable=False, default=0)
    
    # Preview metrics
    preview_count = Column(Integer, nullable=False, default=0)
    preview_to_download_rate = Column(Float, nullable=False, default=0.0)
    average_generation_time = Column(Float, nullable=True)  # in seconds
    
    # Time tracking
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # SEO and discoverability
    tags = Column(JSON, nullable=True)  # JSON array of tags
    keywords = Column(Text, nullable=True)
    search_vector = Column(Text, nullable=True)  # For full-text search
    
    # Relationships
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    creator = relationship("User", back_populates="templates")
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    placeholders_rel = relationship("Placeholder", back_populates="template", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="template")
    
    def __repr__(self):
        return f"<Template(id={self.id}, name='{self.name}', category='{self.category}')>"


class Placeholder(Base):
    """Placeholder model for template variables"""
    __tablename__ = "placeholders"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=False)
    
    # Placeholder identification
    name = Column(String(100), nullable=False)  # e.g., "client_name", "date"
    display_name = Column(String(200), nullable=True)  # Human-readable name
    description = Column(Text, nullable=True)
    placeholder_type = Column(String(50), nullable=False, default="text")  # text, date, number, email, etc.
    
    # Document position
    paragraph_index = Column(Integer, nullable=False)
    start_run_index = Column(Integer, nullable=False)
    end_run_index = Column(Integer, nullable=False)
    
    # Formatting
    bold = Column(Boolean, nullable=False, default=False)
    italic = Column(Boolean, nullable=False, default=False)
    underline = Column(Boolean, nullable=False, default=False)
    casing = Column(String(20), nullable=False, default="none")  # none, upper, lower, title
    
    # Validation
    is_required = Column(Boolean, nullable=False, default=True)
    min_length = Column(Integer, nullable=True)
    max_length = Column(Integer, nullable=True)
    pattern = Column(String(500), nullable=True)  # Regex pattern
    default_value = Column(Text, nullable=True)
    
    # Options for select/dropdown type
    options = Column(JSON, nullable=True)  # JSON array of options
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    template = relationship("Template", back_populates="placeholders_rel")
    
    def __repr__(self):
        return f"<Placeholder(id={self.id}, name='{self.name}', type='{self.placeholder_type}')>"
