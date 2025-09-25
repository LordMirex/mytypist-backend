"""
Advanced Token Management System with Welcome Bonuses
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, Text, ForeignKey, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

from database import Base


class TokenType(str, enum.Enum):
    """Token type enumeration"""
    DOCUMENT_GENERATION = "document_generation"
    TEMPLATE_CREATION = "template_creation"
    API_USAGE = "api_usage"
    PREMIUM_FEATURES = "premium_features"
    WELCOME_BONUS = "welcome_bonus"
    REFERRAL_BONUS = "referral_bonus"
    LOYALTY_BONUS = "loyalty_bonus"


class TokenTransactionType(str, enum.Enum):
    """Token transaction types"""
    EARNED = "earned"
    SPENT = "spent"
    GIFTED = "gifted"
    REFUNDED = "refunded"
    EXPIRED = "expired"
    BONUS = "bonus"


class UserToken(Base):
    """User token balance and management"""
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Token balances by type
    document_tokens = Column(Integer, nullable=False, default=0)
    template_tokens = Column(Integer, nullable=False, default=0)
    api_tokens = Column(Integer, nullable=False, default=0)
    premium_tokens = Column(Integer, nullable=False, default=0)
    
    # Total lifetime tokens
    lifetime_earned = Column(Integer, nullable=False, default=0)
    lifetime_spent = Column(Integer, nullable=False, default=0)
    
    # Welcome bonus tracking
    welcome_bonus_claimed = Column(Boolean, nullable=False, default=False)
    welcome_bonus_date = Column(DateTime, nullable=True)
    welcome_bonus_amount = Column(Integer, nullable=False, default=50)  # Default 50 tokens
    
    # Referral system
    referral_code = Column(String(20), nullable=True, unique=True, index=True)
    referred_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    referral_bonus_earned = Column(Integer, nullable=False, default=0)
    
    # Monthly limits and resets
    monthly_limit = Column(Integer, nullable=False, default=500)
    monthly_used = Column(Integer, nullable=False, default=0)
    last_monthly_reset = Column(DateTime, nullable=True)
    
    # Token expiry settings
    token_expiry_days = Column(Integer, nullable=False, default=365)  # 1 year default
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="token_account")
    referrer = relationship("User", foreign_keys=[referred_by], remote_side="User.id", backref="referrals")
    
    @property
    def total_tokens(self):
        """Get total available tokens across all types"""
        return (self.document_tokens + self.template_tokens + 
                self.api_tokens + self.premium_tokens)
    
    @property
    def can_claim_welcome_bonus(self):
        """Check if user can claim welcome bonus"""
        return not getattr(self, 'welcome_bonus_claimed', True)


class TokenTransaction(Base):
    """Token transaction history"""
    __tablename__ = "token_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Transaction details
    transaction_type = Column(Enum(TokenTransactionType), nullable=False, index=True)
    token_type = Column(Enum(TokenType), nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # Positive for earned, negative for spent
    balance_before = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    
    # Transaction metadata
    description = Column(String(255), nullable=False)
    reference_id = Column(String(100), nullable=True, index=True)  # Document ID, Payment ID, etc.
    reference_type = Column(String(50), nullable=True)  # document, payment, bonus, etc.
    
    # Campaign/bonus tracking
    campaign_id = Column(String(50), nullable=True, index=True)
    bonus_multiplier = Column(Numeric(3, 2), nullable=False, default=1.0)
    
    # Expiry
    expires_at = Column(DateTime, nullable=True)
    is_expired = Column(Boolean, nullable=False, default=False)
    
    # Admin notes
    admin_notes = Column(Text, nullable=True)
    processed_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="token_transactions")
    processor = relationship("User", foreign_keys=[processed_by])


class TokenCampaign(Base):
    """Token campaigns and promotions"""
    __tablename__ = "token_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    
    # Campaign details
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    campaign_code = Column(String(50), nullable=False, unique=True, index=True)
    
    # Token rewards
    token_type = Column(Enum(TokenType), nullable=False)
    token_amount = Column(Integer, nullable=False)
    bonus_multiplier = Column(Numeric(3, 2), nullable=False, default=1.0)
    
    # Campaign limits
    max_users = Column(Integer, nullable=True)
    max_tokens_per_user = Column(Integer, nullable=True)
    max_total_tokens = Column(Integer, nullable=True)
    
    # Tracking
    users_participated = Column(Integer, nullable=False, default=0)
    tokens_distributed = Column(Integer, nullable=False, default=0)
    
    # Validity
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Requirements
    min_account_age_days = Column(Integer, nullable=False, default=0)
    requires_email_verification = Column(Boolean, nullable=False, default=True)
    requires_phone_verification = Column(Boolean, nullable=False, default=False)
    
    # Admin
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    creator = relationship("User", backref="created_campaigns")


class TokenReward(Base):
    """Token reward rules and configurations"""
    __tablename__ = "token_rewards"

    id = Column(Integer, primary_key=True, index=True)
    
    # Reward trigger
    event_type = Column(String(50), nullable=False, index=True)  # registration, document_created, etc.
    description = Column(String(255), nullable=False)
    
    # Reward amount
    token_type = Column(Enum(TokenType), nullable=False)
    token_amount = Column(Integer, nullable=False)
    bonus_multiplier = Column(Numeric(3, 2), nullable=False, default=1.0)
    
    # Limits
    max_per_user = Column(Integer, nullable=True)
    max_per_day = Column(Integer, nullable=True)
    max_total = Column(Integer, nullable=True)
    
    # Requirements
    min_user_level = Column(String(20), nullable=False, default="user")
    requires_email_verification = Column(Boolean, nullable=False, default=True)
    
    # Tracking
    times_awarded = Column(Integer, nullable=False, default=0)
    total_tokens_awarded = Column(Integer, nullable=False, default=0)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    
    # Admin
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)