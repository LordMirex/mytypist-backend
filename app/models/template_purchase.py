"""
Template Purchase Model
Handles template purchase transactions and history
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class TemplatePurchase(Base):
    """Template purchase transaction model"""
    __tablename__ = 'template_purchases'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    template_id = Column(Integer, ForeignKey('templates.id'), nullable=False)
    
    # Transaction details
    amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default='NGN')  # NGN, TOK (tokens), USD
    payment_method = Column(String(50), nullable=True)  # flutterwave, tokens, etc.
    transaction_reference = Column(String(100), nullable=True)
    
    # Status and metadata
    status = Column(String(20), nullable=False, default='completed')  # pending, completed, failed, refunded
    purchased_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Access control
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # For time-limited access
    
    # Relationships
    user = relationship("User", backref="template_purchases")
    template = relationship("Template", backref="purchases")

    def __repr__(self):
        return f"<TemplatePurchase(id={self.id}, user_id={self.user_id}, template_id={self.template_id}, amount={self.amount})>"