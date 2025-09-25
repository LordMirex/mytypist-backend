"""
Campaign models for marketing and promotional campaigns
"""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, Float
from sqlalchemy.sql import func
from database import Base


class CampaignType(str, Enum):
    """Campaign type enumeration"""
    EMAIL_MARKETING = "email_marketing"
    TOKEN_GIFTING = "token_gifting"
    USER_ONBOARDING = "user_onboarding" 
    RETENTION = "retention"
    REACTIVATION = "reactivation"
    SEASONAL_PROMOTION = "seasonal_promotion"
    REFERRAL_BOOST = "referral_boost"
    TOKEN_DISTRIBUTION = "token_distribution"


class CampaignStatus(str, Enum):
    """Campaign status enumeration"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Campaign(Base):
    """Marketing campaign model"""
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    campaign_type = Column(String(50), nullable=False, default="token_distribution")
    
    # Campaign configuration
    status = Column(String(20), nullable=False, default="active")  # active, paused, completed
    priority = Column(Integer, nullable=False, default=1)
    
    # Token rewards
    token_reward_amount = Column(Integer, nullable=False, default=0)
    max_participants = Column(Integer, nullable=True)
    max_total_tokens = Column(Integer, nullable=True)
    
    # Analytics
    participants_count = Column(Integer, nullable=False, default=0)
    tokens_distributed = Column(Integer, nullable=False, default=0)
    conversion_rate = Column(Float, nullable=False, default=0.0)
    
    # Time tracking
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Campaign metadata
    campaign_metadata = Column(JSON, nullable=True)
    rules = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<Campaign(id={self.id}, name='{self.name}', type='{self.campaign_type}')>"