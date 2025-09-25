"""
Payment and subscription-related Pydantic schemas
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator
from app.models.payment import PaymentStatus, PaymentMethod, SubscriptionStatus, SubscriptionPlan


class PaymentCreate(BaseModel):
    """Payment creation schema"""
    amount: float = Field(..., gt=0)
    currency: str = Field("NGN", pattern=r"^[A-Z]{3}$")
    description: Optional[str] = Field(None, max_length=255)
    payment_method: PaymentMethod
    customer_name: Optional[str] = Field(None, max_length=200)
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = Field(None, pattern=r"^\+?[1-9]\d{1,14}$")
    redirect_url: Optional[str] = Field(None, max_length=500)
    metadata: Optional[Dict[str, Any]] = {}


class PaymentResponse(BaseModel):
    """Payment response schema"""
    id: int
    transaction_id: str
    flutterwave_tx_ref: str
    amount: float
    currency: str
    description: Optional[str]
    payment_method: PaymentMethod
    status: PaymentStatus
    customer_name: Optional[str]
    customer_email: Optional[str]
    customer_phone: Optional[str]
    authorization_code: Optional[str]
    card_last4: Optional[str]
    card_type: Optional[str]
    bank_name: Optional[str]
    net_amount: float
    initiated_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class PaymentWebhook(BaseModel):
    """Flutterwave webhook payload schema"""
    event: str
    data: Dict[str, Any]
    
    @validator('event')
    def validate_event(cls, v):
        allowed_events = [
            'charge.completed',
            'charge.failed',
            'transfer.completed',
            'transfer.failed'
        ]
        if v not in allowed_events:
            raise ValueError(f'Unsupported event type: {v}')
        return v


class SubscriptionCreate(BaseModel):
    """Subscription creation schema"""
    plan: SubscriptionPlan
    billing_cycle: str = Field("monthly", pattern=r"^(monthly|yearly)$")
    payment_method: PaymentMethod
    auto_renew: bool = True


class SubscriptionUpdate(BaseModel):
    """Subscription update schema"""
    plan: Optional[SubscriptionPlan] = None
    billing_cycle: Optional[str] = Field(None, pattern=r"^(monthly|yearly)$")
    auto_renew: Optional[bool] = None
    status: Optional[SubscriptionStatus] = None


class SubscriptionResponse(BaseModel):
    """Subscription response schema"""
    id: int
    user_id: int
    plan: SubscriptionPlan
    status: SubscriptionStatus
    amount: float
    currency: str
    billing_cycle: str
    documents_limit: int
    documents_used: int
    documents_remaining: int
    templates_limit: int
    storage_limit: int
    storage_used: int
    storage_remaining: int
    custom_templates: bool
    api_access: bool
    priority_support: bool
    white_label: bool
    starts_at: datetime
    ends_at: datetime
    next_billing_date: Optional[datetime]
    auto_renew: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    """Invoice response schema"""
    id: int
    invoice_number: str
    amount: float
    currency: str
    tax_amount: float
    total_amount: float
    billing_period_start: datetime
    billing_period_end: datetime
    due_date: datetime
    status: str
    customer_name: str
    customer_email: str
    line_items: List[Dict[str, Any]]
    created_at: datetime
    paid_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class PaymentLink(BaseModel):
    """Payment link generation schema"""
    amount: float = Field(..., gt=0)
    currency: str = Field("NGN", pattern=r"^[A-Z]{3}$")
    description: str = Field(..., max_length=255)
    customer_email: EmailStr
    customer_name: str = Field(..., max_length=200)
    redirect_url: Optional[str] = Field(None, max_length=500)
    expires_in_hours: int = Field(24, ge=1, le=168)  # Max 7 days


class PaymentLinkResponse(BaseModel):
    """Payment link response schema"""
    payment_link: str
    reference: str
    expires_at: datetime


class RefundRequest(BaseModel):
    """Refund request schema"""
    payment_id: int
    amount: Optional[float] = None  # Full refund if not specified
    reason: str = Field(..., max_length=255)


class RefundResponse(BaseModel):
    """Refund response schema"""
    id: int
    payment_id: int
    amount: float
    reason: str
    status: str
    processed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class PaymentStats(BaseModel):
    """Payment statistics schema"""
    total_revenue: float
    total_transactions: int
    successful_transactions: int
    failed_transactions: int
    average_transaction_value: float
    this_month_revenue: float
    last_month_revenue: float
    growth_rate: float
    top_payment_methods: List[Dict[str, Any]]


class SubscriptionPlanInfo(BaseModel):
    """Subscription plan information schema"""
    plan: SubscriptionPlan
    name: str
    description: str
    monthly_price: float
    yearly_price: float
    features: List[str]
    documents_limit: int
    templates_limit: int
    storage_limit: int
    custom_templates: bool
    api_access: bool
    priority_support: bool
    white_label: bool
    popular: bool = False


class BillingHistory(BaseModel):
    """Billing history schema"""
    payments: List[PaymentResponse]
    invoices: List[InvoiceResponse]
    total_spent: float
    next_billing_date: Optional[datetime]
    payment_method: Optional[str]
