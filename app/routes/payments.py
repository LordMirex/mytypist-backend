"""
Payment and subscription routes using Flutterwave
"""

import uuid
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session

from database import get_db
from config import settings
from app.models.payment import Payment, Subscription, Invoice, PaymentStatus, SubscriptionPlan
from app.models.user import User
from app.schemas.payment import (
    PaymentCreate, PaymentResponse, PaymentWebhook,
    SubscriptionCreate, SubscriptionResponse, SubscriptionUpdate,
    InvoiceResponse, PaymentLink, PaymentLinkResponse,
    RefundRequest, RefundResponse, PaymentStats, SubscriptionPlanInfo,
    BillingHistory
)
from app.services.payment_service import PaymentService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user
from app.tasks.payment_tasks import process_payment_webhook_task

router = APIRouter()


@router.post("/initialize", response_model=dict, status_code=status.HTTP_201_CREATED)
async def initialize_payment(
    payment_data: PaymentCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Initialize payment with Flutterwave"""
    
    # Create payment record
    payment = PaymentService.create_payment(db, payment_data, current_user.id)
    
    # Initialize payment with Flutterwave
    flutterwave_response = PaymentService.initialize_flutterwave_payment(
        payment, request
    )
    
    # Log payment initialization
    AuditService.log_payment_event(
        "PAYMENT_INITIATED",
        current_user.id,
        request,
        {
            "payment_id": payment.id,
            "amount": payment.amount,
            "currency": payment.currency,
            "flutterwave_tx_ref": payment.flutterwave_tx_ref
        }
    )
    
    return {
        "payment_id": payment.id,
        "payment_link": flutterwave_response["data"]["link"],
        "reference": payment.flutterwave_tx_ref,
        "status": payment.status.value
    }


@router.get("/", response_model=List[PaymentResponse])
async def list_payments(
    page: int = 1,
    per_page: int = 20,
    status_filter: Optional[PaymentStatus] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List user's payments with pagination"""
    
    query = db.query(Payment).filter(Payment.user_id == current_user.id)
    
    if status_filter:
        query = query.filter(Payment.status == status_filter)
    
    payments = query.order_by(Payment.initiated_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    
    return [PaymentResponse.from_orm(payment) for payment in payments]


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get payment by ID"""
    
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.user_id == current_user.id
    ).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    return PaymentResponse.from_orm(payment)


@router.get("/{payment_id}/status")
async def check_payment_status(
    payment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Check payment status with Flutterwave"""
    
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.user_id == current_user.id
    ).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Verify payment status with Flutterwave
    updated_payment = PaymentService.verify_flutterwave_payment(db, payment)
    
    return {
        "payment_id": payment.id,
        "status": updated_payment.status.value,
        "amount": updated_payment.amount,
        "currency": updated_payment.currency,
        "completed_at": updated_payment.completed_at
    }


@router.post("/webhook")
async def handle_flutterwave_webhook(
    request: Request,
    webhook_signature: Optional[str] = Header(None, alias="verif-hash"),
    db: Session = Depends(get_db)
):
    """Handle Flutterwave webhook notifications"""
    
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify webhook signature
    expected_signature = hashlib.sha256(
        (settings.FLUTTERWAVE_WEBHOOK_SECRET + body.decode()).encode()
    ).hexdigest()
    
    if not hmac.compare_digest(webhook_signature or "", expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    # Parse webhook data
    webhook_data = await request.json()
    
    # Process webhook asynchronously
    process_payment_webhook_task.delay(webhook_data)
    
    return {"status": "success"}


@router.post("/link", response_model=PaymentLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_link(
    link_data: PaymentLink,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create payment link for sharing"""
    
    # Create payment link
    payment_link = PaymentService.create_payment_link(db, link_data, current_user.id)
    
    # Log payment link creation
    AuditService.log_payment_event(
        "PAYMENT_LINK_CREATED",
        current_user.id,
        request,
        {
            "amount": link_data.amount,
            "customer_email": link_data.customer_email,
            "expires_in_hours": link_data.expires_in_hours
        }
    )
    
    return payment_link


@router.post("/refund", response_model=RefundResponse, status_code=status.HTTP_201_CREATED)
async def request_refund(
    refund_data: RefundRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Request payment refund"""
    
    payment = db.query(Payment).filter(
        Payment.id == refund_data.payment_id,
        Payment.user_id == current_user.id
    ).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    if payment.status != PaymentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only completed payments can be refunded"
        )
    
    # Process refund
    refund = PaymentService.process_refund(db, payment, refund_data)
    
    # Log refund request
    AuditService.log_payment_event(
        "REFUND_REQUESTED",
        current_user.id,
        request,
        {
            "payment_id": payment.id,
            "refund_amount": refund_data.amount or payment.amount,
            "reason": refund_data.reason
        }
    )
    
    return refund


@router.get("/stats", response_model=PaymentStats)
async def get_payment_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get payment statistics for user"""
    
    stats = PaymentService.get_user_payment_stats(db, current_user.id)
    return stats


# Subscription endpoints

@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create new subscription"""
    
    # Check if user already has active subscription
    existing_subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id,
        Subscription.status == "active"
    ).first()
    
    if existing_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has an active subscription"
        )
    
    # Create subscription
    subscription = PaymentService.create_subscription(
        db, subscription_data, current_user.id, request
    )
    
    # Log subscription creation
    AuditService.log_subscription_event(
        "SUBSCRIPTION_CREATED",
        current_user.id,
        request,
        {
            "subscription_id": subscription.id,
            "plan": subscription.plan.value,
            "amount": subscription.amount
        }
    )
    
    return SubscriptionResponse.from_orm(subscription)


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List user's subscriptions"""
    
    subscriptions = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).order_by(Subscription.created_at.desc()).all()
    
    return [SubscriptionResponse.from_orm(sub) for sub in subscriptions]


@router.get("/subscriptions/current", response_model=Optional[SubscriptionResponse])
async def get_current_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's current active subscription"""
    
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id,
        Subscription.status == "active"
    ).first()
    
    if not subscription:
        return None
    
    return SubscriptionResponse.from_orm(subscription)


@router.put("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    subscription_update: SubscriptionUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update subscription"""
    
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id,
        Subscription.user_id == current_user.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Update subscription
    updated_subscription = PaymentService.update_subscription(
        db, subscription, subscription_update
    )
    
    # Log subscription update
    AuditService.log_subscription_event(
        "SUBSCRIPTION_UPDATED",
        current_user.id,
        request,
        {
            "subscription_id": subscription.id,
            "updated_fields": list(subscription_update.dict(exclude_unset=True).keys())
        }
    )
    
    return SubscriptionResponse.from_orm(updated_subscription)


@router.post("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: int,
    reason: Optional[str] = None,
    request: Request = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cancel subscription"""
    
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id,
        Subscription.user_id == current_user.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    if subscription.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only active subscriptions can be cancelled"
        )
    
    # Cancel subscription
    PaymentService.cancel_subscription(db, subscription, reason)
    
    # Log subscription cancellation
    AuditService.log_subscription_event(
        "SUBSCRIPTION_CANCELLED",
        current_user.id,
        request,
        {
            "subscription_id": subscription.id,
            "reason": reason
        }
    )
    
    return {"message": "Subscription cancelled successfully"}


@router.get("/plans", response_model=List[SubscriptionPlanInfo])
async def get_subscription_plans():
    """Get available subscription plans"""
    
    plans = PaymentService.get_subscription_plans()
    return plans


@router.get("/billing-history", response_model=BillingHistory)
async def get_billing_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's billing history"""
    
    billing_history = PaymentService.get_billing_history(db, current_user.id)
    return billing_history


@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List user's invoices"""
    
    invoices = db.query(Invoice).filter(
        Invoice.user_id == current_user.id
    ).order_by(Invoice.created_at.desc()).all()
    
    return [InvoiceResponse.from_orm(invoice) for invoice in invoices]


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get invoice by ID"""
    
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == current_user.id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return InvoiceResponse.from_orm(invoice)


@router.get("/invoices/{invoice_id}/download")
async def download_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Download invoice PDF"""
    
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == current_user.id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Generate and return invoice PDF
    pdf_content = PaymentService.generate_invoice_pdf(invoice)
    
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "pdf_content": pdf_content,
        "filename": f"invoice_{invoice.invoice_number}.pdf"
    }
