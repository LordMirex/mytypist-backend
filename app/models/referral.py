"""Referral system models"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class ReferralProgram(Base):
    """Referral program configuration"""
    __tablename__ = "referral_programs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Program details
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    program_code = Column(String(50), nullable=False, unique=True, index=True)
    
    # Reward configuration
    referrer_token_amount = Column(Integer, nullable=False)  # Base amount for referrer
    referee_token_amount = Column(Integer, nullable=False)  # Base amount for new user
    bonus_multiplier = Column(Float, nullable=False, default=1.0)
    
    # Program limits
    max_referrals_per_user = Column(Integer, nullable=True)  # Maximum referrals per user
    max_total_referrals = Column(Integer, nullable=True)  # Maximum total referrals
    max_total_rewards = Column(Integer, nullable=True)  # Maximum total rewards to give
    
    # Requirements
    min_referrer_age_days = Column(Integer, nullable=False, default=0)  # Minimum account age
    referrer_requires_email = Column(Boolean, nullable=False, default=True)
    referrer_requires_purchase = Column(Boolean, nullable=False, default=False)
    
    # Tracking
    total_referrals = Column(Integer, nullable=False, default=0)  # Total successful referrals
    total_rewards_given = Column(Integer, nullable=False, default=0)  # Total rewards distributed
    
    # Validity
    is_active = Column(Boolean, nullable=False, default=True)
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    
    # Analytics
    conversion_rate = Column(Float, nullable=False, default=0.0)  # % of successful referrals
    retention_rate = Column(Float, nullable=False, default=0.0)  # % of referred users retained
    roi = Column(Float, nullable=False, default=0.0)  # Return on investment
    
    # Admin
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    creator = relationship("User", backref="created_referral_programs")


class ReferralTracking(Base):
    """Track individual referrals and their status"""
    __tablename__ = "referral_tracking"

    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey('referral_programs.id'), nullable=False)
    referrer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    referee_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Null until signup
    
    # Referral details
    referral_code = Column(String(50), nullable=False, index=True)
    referee_email = Column(String(255), nullable=True)
    
    # Tracking
    status = Column(String(50), nullable=False, default="pending")  # pending, signed_up, completed
    sign_up_date = Column(DateTime, nullable=True)  # When referee created account
    completion_date = Column(DateTime, nullable=True)  # When reward was given
    
    # Analytics and Security data
    source = Column(String(100), nullable=True)  # Where referral link was shared
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(100), nullable=True)
    referrer_ip = Column(String(45), nullable=True)  # IPv6 support
    referee_ip = Column(String(45), nullable=True)
    is_suspicious = Column(Boolean, default=False)  # Flag for potential fraud
    
    # Rewards
    referrer_reward = Column(Integer, nullable=True)  # Actual tokens given to referrer
    referee_reward = Column(Integer, nullable=True)  # Actual tokens given to referee
    
    # Metadata
    notes = Column(Text, nullable=True)  # Any additional info
    referral_metadata = Column(JSON, nullable=True)  # Extensible data storage
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    program = relationship("ReferralProgram", backref="referrals")
    referrer = relationship("User", foreign_keys=[referrer_id], backref="sent_referrals")
    referee = relationship("User", foreign_keys=[referee_id], backref="received_referrals")