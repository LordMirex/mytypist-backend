"""
Payment and subscription models
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Float, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from database import Base


class PaymentStatus(str, enum.Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, enum.Enum):
    """Payment method enumeration"""
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"
    USSD = "ussd"
    QR = "qr"


class SubscriptionStatus(str, enum.Enum):
    """Subscription status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class SubscriptionPlan(str, enum.Enum):
    """Subscription plan enumeration"""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Payment(Base):
    """Payment transaction model"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Payment identification
    transaction_id = Column(String(100), unique=True, nullable=False)  # Our internal ID
    flutterwave_tx_ref = Column(String(100), unique=True, nullable=False)  # Flutterwave reference
    flutterwave_id = Column(String(100), nullable=True)  # Flutterwave transaction ID
    
    # Payment details
    amount = Column(Float, nullable=False)  # Amount in Naira
    currency = Column(String(3), nullable=False, default="NGN")
    description = Column(Text, nullable=True)
    
    # Payment method and processing
    payment_method = Column(Enum(PaymentMethod), nullable=False)
    processor = Column(String(50), nullable=False, default="flutterwave")
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    
    # Customer information
    customer_name = Column(String(200), nullable=True)
    customer_email = Column(String(255), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    
    # Processing details
    processor_response = Column(JSON, nullable=True)  # Full response from Flutterwave
    authorization_code = Column(String(100), nullable=True)
    card_last4 = Column(String(4), nullable=True)
    card_type = Column(String(20), nullable=True)
    bank_name = Column(String(100), nullable=True)
    
    # Fees and charges
    app_fee = Column(Float, nullable=False, default=0.0)
    merchant_fee = Column(Float, nullable=False, default=0.0)
    processor_fee = Column(Float, nullable=False, default=0.0)
    net_amount = Column(Float, nullable=False, default=0.0)
    
    # Security and verification
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    fraud_status = Column(String(20), nullable=True)  # clear, flagged, blocked
    risk_score = Column(Float, nullable=True)
    
    # Refund information
    refund_amount = Column(Float, nullable=False, default=0.0)
    refund_reason = Column(Text, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    
    # Timestamps
    initiated_at = Column(DateTime, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payment", uselist=False)
    
    def __repr__(self):
        return f"<Payment(id={self.id}, tx_ref='{self.flutterwave_tx_ref}', amount={self.amount}, status='{self.status}')>"


class Subscription(Base):
    """User subscription model"""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    
    # Subscription details
    plan = Column(Enum(SubscriptionPlan), nullable=False)
    status = Column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.ACTIVE)
    
    # Billing information
    amount = Column(Float, nullable=False)  # Amount paid
    currency = Column(String(3), nullable=False, default="NGN")
    billing_cycle = Column(String(20), nullable=False, default="monthly")  # monthly, yearly
    
    # Plan limits and usage
    documents_limit = Column(Integer, nullable=False)  # -1 for unlimited
    documents_used = Column(Integer, nullable=False, default=0)
    templates_limit = Column(Integer, nullable=False, default=-1)  # -1 for unlimited
    storage_limit = Column(Integer, nullable=False, default=-1)  # bytes, -1 for unlimited
    storage_used = Column(Integer, nullable=False, default=0)
    
    # Features
    custom_templates = Column(Boolean, nullable=False, default=False)
    api_access = Column(Boolean, nullable=False, default=False)
    priority_support = Column(Boolean, nullable=False, default=False)
    white_label = Column(Boolean, nullable=False, default=False)
    
    # Dates
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    next_billing_date = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    # Auto-renewal
    auto_renew = Column(Boolean, nullable=False, default=True)
    renewal_attempts = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    payment = relationship("Payment", back_populates="subscription")
    
    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, plan='{self.plan}', status='{self.status}')>"
    
    @property
    def is_active(self):
        """Check if subscription is active"""
        from datetime import datetime
        return (
            getattr(self, 'status', None) == SubscriptionStatus.ACTIVE and
            getattr(self, 'ends_at', None) and getattr(self, 'ends_at') > datetime.now()
        )
    
    @property
    def documents_remaining(self):
        """Get remaining document generation count"""
        limit = getattr(self, 'documents_limit', 0)
        used = getattr(self, 'documents_used', 0)
        if limit == -1:
            return float('inf')
        return max(0, limit - used)
    
    @property
    def storage_remaining(self):
        """Get remaining storage in bytes"""
        limit = getattr(self, 'storage_limit', 0)
        used = getattr(self, 'storage_used', 0)
        if limit == -1:
            return float('inf')
        return max(0, limit - used)


class Invoice(Base):
    """Invoice model for subscription billing"""
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    
    # Invoice details
    invoice_number = Column(String(50), unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="NGN")
    tax_amount = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False)
    
    # Billing information
    billing_period_start = Column(DateTime, nullable=False)
    billing_period_end = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=False)
    
    # Status
    status = Column(String(20), nullable=False, default="pending")  # pending, paid, overdue, cancelled
    paid_at = Column(DateTime, nullable=True)
    
    # Customer information (snapshot)
    customer_name = Column(String(200), nullable=False)
    customer_email = Column(String(255), nullable=False)
    customer_address = Column(Text, nullable=True)
    
    # Line items (JSON)
    line_items = Column(JSON, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Invoice(id={self.id}, number='{self.invoice_number}', amount={self.total_amount}, status='{self.status}')>"
