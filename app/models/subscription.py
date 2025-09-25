"""
Subscription Plan Management System
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, Text, ForeignKey, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

from database import Base
from .token import TokenType


class SubscriptionTier(str, enum.Enum):
    """Subscription tier levels"""
    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    """Subscription status enumeration"""
    ACTIVE = "active"
    CANCELED = "canceled"
    EXPIRED = "expired"
    PENDING = "pending"


class SubscriptionPlan(Base):
    """Subscription plan configuration"""
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    tier = Column(Enum(SubscriptionTier), nullable=False)
    description = Column(Text, nullable=True)
    
    # Monthly token allocations
    monthly_document_tokens = Column(Integer, nullable=False, default=0)
    monthly_template_tokens = Column(Integer, nullable=False, default=0)
    monthly_api_tokens = Column(Integer, nullable=False, default=0)
    monthly_premium_tokens = Column(Integer, nullable=False, default=0)
    
    # Pricing
    price_monthly = Column(Numeric(10, 2), nullable=False)
    price_yearly = Column(Numeric(10, 2), nullable=False)
    
    # Features
    max_team_members = Column(Integer, nullable=False, default=1)
    priority_support = Column(Boolean, nullable=False, default=False)
    custom_templates = Column(Boolean, nullable=False, default=False)
    api_access = Column(Boolean, nullable=False, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UserSubscription(Base):
    """User subscription records"""
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey('subscription_plans.id'), nullable=False)
    
    status = Column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.PENDING)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    
    # Billing cycle
    billing_cycle_start = Column(DateTime(timezone=True), nullable=False)
    billing_cycle_end = Column(DateTime(timezone=True), nullable=False)
    is_annual = Column(Boolean, nullable=False, default=False)
    
    # Token allocation tracking
    last_token_allocation = Column(DateTime(timezone=True), nullable=True)
    next_token_allocation = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan")