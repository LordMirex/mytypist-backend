"""
Template Favorite Model
Handles user favorite templates functionality
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class TemplateFavorite(Base):
    """User's favorite templates model"""
    __tablename__ = 'template_favorites'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    template_id = Column(Integer, ForeignKey('templates.id'), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Unique constraint to prevent duplicate favorites
    __table_args__ = (
        UniqueConstraint('user_id', 'template_id', name='uq_user_template_favorite'),
    )
    
    # Relationships
    user = relationship("User", backref="favorite_templates")
    template = relationship("Template", backref="favorited_by")

    def __repr__(self):
        return f"<TemplateFavorite(id={self.id}, user_id={self.user_id}, template_id={self.template_id})>"