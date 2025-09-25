"""
Template Management Models
Enhanced models for template management with versioning and metadata
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey, Table
from sqlalchemy.orm import relationship
from database import Base

# Association table for template categories
template_category_links = Table(
    'template_category_links',
    Base.metadata,
    Column('template_id', Integer, ForeignKey('templates.id'), primary_key=True),
    Column('category_id', Integer, ForeignKey('template_categories.id'), primary_key=True)
)

class TemplateCategory(Base):
    """Category model for organizing templates"""
    __tablename__ = 'template_categories'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    description = Column(String)
    parent_id = Column(Integer, ForeignKey('template_categories.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Enhanced classification fields
    keywords = Column(JSON, default=list)  # TF-IDF extracted keywords
    feature_vector = Column(JSON, default=list)  # Numeric feature vector for clustering
    cluster_id = Column(Integer, nullable=True)  # Assigned cluster
    similarity_score = Column(JSON, default=dict)  # Similarity scores with other templates
    auto_tags = Column(JSON, default=list)  # Automatically generated tags
    
    # Relationships
    parent = relationship("TemplateCategory", remote_side=[id], backref="subcategories")
    # templates relationship is defined in the Template model (app.models.template)


class TemplateVersion(Base):
    """Template version model for version control"""
    __tablename__ = 'template_versions'

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey('templates.id'), nullable=False)
    version_number = Column(String, nullable=False)  # Semantic versioning
    content_hash = Column(String, nullable=False)  # Hash of template content
    preview_file_path = Column(String)
    template_file_path = Column(String)
    changes = Column(JSON)  # List of changes in this version
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    template_metadata = Column(JSON)  # Additional version-specific metadata

    # Relationships
    template = relationship("Template")
    creator = relationship("User")

# Note: Template model is defined in app.models.template
# We use that model for consistency across the application

class TemplateReview(Base):
    """User reviews and ratings for templates"""
    __tablename__ = 'template_reviews'

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey('templates.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5 rating
    review_text = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    template = relationship("Template")
    user = relationship("User")
