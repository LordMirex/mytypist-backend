"""
Payment and subscription service using Flutterwave
"""

import os
import uuid
import hmac
import hashlib
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from fastapi import Request, HTTPException
from pydantic import ValidationError

from config import settings
from app.models.payment import (
    Payment, Subscription, Invoice, PaymentStatus, PaymentMethod,
    SubscriptionStatus, SubscriptionPlan
)
from app.models.user import User
from app.schemas.payment import (
    PaymentCreate, SubscriptionCreate, SubscriptionUpdate,
    PaymentLink, PaymentLinkResponse, RefundRequest, RefundResponse,
    PaymentStats, SubscriptionPlanInfo, BillingHistory
)
from database import get_db


class FlutterwaveError(Exception):
    """Custom exception for Flutterwave API errors"""
    pass


class PaymentService:
    """Payment and subscription management service"""
    
    FLUTTERWAVE_BASE_URL = "https://api.flutterwave.com/api"
    
    @staticmethod
    def create_payment(db: Session, payment_data: PaymentCreate, user_id: int) -> Payment:
        """Create new payment record"""
        
        # Generate unique transaction references
        transaction_id = f"MTK_{uuid.uuid4().hex[:16].upper()}"
        flutterwave_tx_ref = f"FW_{uuid.uuid4().hex[:20].upper()}"
        
        payment = Payment(
            user_id=user_id,
            transaction_id=transaction_id,
            flutterwave_tx_ref=flutterwave_tx_ref,
            amount=payment_data.amount,
            currency=payment_data.currency,
            description=payment_data.description,
            payment_method=payment_data.payment_method,
            customer_name=payment_data.customer_name,
            customer_email=payment_data.customer_email,
            customer_phone=payment_data.customer_phone,
            status=PaymentStatus.PENDING,
            initiated_at=datetime.utcnow()
        )
        
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        return payment
    
    @staticmethod
    def initialize_flutterwave_payment(payment: Payment, request: Request) -> Dict[str, Any]:
        """Initialize payment with Flutterwave"""
        
        # Prepare payment data
        payload = {
            "tx_ref": payment.flutterwave_tx_ref,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "redirect_url": f"{request.base_url}api/payments/{payment.id}/callback",
            "payment_options": "card,banktransfer,ussd,mobilemoney",
            "customer": {
                "email": payment.customer_email,
                "name": payment.customer_name,
                "phonenumber": payment.customer_phone
            },
            "customizations": {
                "title": "MyTypist Payment",
                "description": payment.description or "Document processing service",
                "logo": f"{request.base_url}static/logo.png"
            },
            "meta": {
                "payment_id": payment.id,
                "user_id": payment.user_id
            }
        }
        
        headers = {
            "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{PaymentService.FLUTTERWAVE_BASE_URL}/payments",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get("status") == "success":
                return response_data
            else:
                raise FlutterwaveError(f"Flutterwave error: {response_data.get('message', 'Unknown error')}")
        
        except requests.exceptions.RequestException as e:
            raise FlutterwaveError(f"Network error: {str(e)}")
        except json.JSONDecodeError:
            raise FlutterwaveError("Invalid response from Flutterwave")
    
    @staticmethod
    def verify_flutterwave_payment(db: Session, payment: Payment) -> Payment:
        """Verify payment status with Flutterwave"""
        
        headers = {
            "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(
                f"{PaymentService.FLUTTERWAVE_BASE_URL}/transactions/verify_by_reference?tx_ref={payment.flutterwave_tx_ref}",
                headers=headers,
                timeout=30
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get("status") == "success":
                transaction_data = response_data.get("data", {})
                
                # Update payment with Flutterwave data
                payment.flutterwave_id = transaction_data.get("id")
                payment.processor_response = transaction_data
                
                # Update status based on Flutterwave status
                fw_status = transaction_data.get("status", "").lower()
                if fw_status == "successful":
                    payment.status = PaymentStatus.COMPLETED
                    payment.completed_at = datetime.utcnow()
                elif fw_status == "failed":
                    payment.status = PaymentStatus.FAILED
                elif fw_status == "cancelled":
                    payment.status = PaymentStatus.CANCELLED
                
                # Update payment details
                if "card" in transaction_data:
                    card_data = transaction_data["card"]
                    payment.card_last4 = card_data.get("last_4digits")
                    payment.card_type = card_data.get("type")
                
                if "customer" in transaction_data:
                    customer_data = transaction_data["customer"]
                    payment.customer_name = customer_data.get("name")
                    payment.customer_email = customer_data.get("email")
                
                # Calculate fees
                payment.app_fee = float(transaction_data.get("app_fee", 0))
                payment.merchant_fee = float(transaction_data.get("merchant_fee", 0))
                payment.processor_fee = float(transaction_data.get("processor_fee", 0))
                payment.net_amount = float(transaction_data.get("amount_settled", payment.amount))
                
                db.commit()
            
            return payment
        
        except requests.exceptions.RequestException as e:
            print(f"Error verifying payment: {e}")
            return payment
    
    @staticmethod
    def process_webhook(webhook_data: Dict[str, Any]) -> bool:
        """Process Flutterwave webhook notification"""
        
        try:
            event_type = webhook_data.get("event")
            data = webhook_data.get("data", {})
            
            if event_type == "charge.completed":
                return PaymentService._handle_charge_completed(data)
            elif event_type == "charge.failed":
                return PaymentService._handle_charge_failed(data)
            
            return True
        
        except Exception as e:
            print(f"Webhook processing error: {e}")
            return False
    
    @staticmethod
    def _handle_charge_completed(data: Dict[str, Any]) -> bool:
        """Handle successful charge webhook with atomic transaction protection"""
        
        db = next(get_db())
        
        try:
            tx_ref = data.get("tx_ref")
            
            # Use SELECT FOR UPDATE to prevent race conditions
            payment = db.query(Payment).filter(
                Payment.flutterwave_tx_ref == tx_ref
            ).with_for_update().first()
            
            if not payment:
                return False
                
            # Prevent duplicate processing - check if already completed
            if payment.status == PaymentStatus.COMPLETED:
                return True  # Already processed, avoid duplicate
            
            # Begin atomic transaction for all payment updates
            try:
                # Update all payment fields atomically
                payment.status = PaymentStatus.COMPLETED
                payment.completed_at = datetime.utcnow()
                payment.processor_response = data
                payment.flutterwave_id = data.get("id")
                
                # Update fees and amounts atomically
                payment.app_fee = float(data.get("app_fee", 0))
                payment.merchant_fee = float(data.get("merchant_fee", 0))
                payment.processor_fee = float(data.get("processor_fee", 0))
                payment.net_amount = float(data.get("amount_settled", payment.amount))
                
                # Process subscription atomically in same transaction
                subscription = db.query(Subscription).filter(
                    Subscription.payment_id == payment.id
                ).first()
                
                if subscription and subscription.status != SubscriptionStatus.ACTIVE:
                    subscription.status = SubscriptionStatus.ACTIVE
                    subscription.activated_at = datetime.utcnow()
                    
                    # Generate invoice in same transaction
                    invoice = PaymentService._generate_invoice_atomic(db, subscription, payment)
                
                # Commit all changes atomically
                db.commit()
                
                return True
                
            except Exception as e:
                # Rollback on any error to maintain consistency
                db.rollback()
                raise e
            
        except Exception as e:
            print(f"Error handling charge completed: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    @staticmethod
    def _handle_charge_failed(data: Dict[str, Any]) -> bool:
        """Handle failed charge webhook with atomic transaction protection"""
        
        db = next(get_db())
        
        try:
            tx_ref = data.get("tx_ref")
            
            # Use SELECT FOR UPDATE to prevent race conditions  
            payment = db.query(Payment).filter(
                Payment.flutterwave_tx_ref == tx_ref
            ).with_for_update().first()
            
            if not payment:
                return False
                
            # Prevent duplicate processing - check if already failed
            if payment.status == PaymentStatus.FAILED:
                return True  # Already processed, avoid duplicate
            
            try:
                # Update payment atomically
                payment.status = PaymentStatus.FAILED
                payment.processor_response = data
                payment.error_message = data.get("narration", "Payment failed")
                payment.failed_at = datetime.utcnow()
                
                # If this was a subscription payment, handle subscription failure
                subscription = db.query(Subscription).filter(
                    Subscription.payment_id == payment.id
                ).first()
                
                if subscription and subscription.status == SubscriptionStatus.PENDING:
                    subscription.status = SubscriptionStatus.FAILED
                    subscription.failure_reason = payment.error_message
                
                # Commit all changes atomically
                db.commit()
                
                return True
                
            except Exception as e:
                # Rollback on any error to maintain consistency  
                db.rollback()
                raise e
            
        except Exception as e:
            print(f"Error handling charge failed: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    @staticmethod
    def create_payment_link(db: Session, link_data: PaymentLink, user_id: int) -> PaymentLinkResponse:
        """Create payment link for sharing"""
        
        # Create payment record
        payment_data = PaymentCreate(
            amount=link_data.amount,
            currency=link_data.currency,
            description=link_data.description,
            customer_email=link_data.customer_email,
            customer_name=link_data.customer_name,
            payment_method=PaymentMethod.CARD  # Default
        )
        
        payment = PaymentService.create_payment(db, payment_data, user_id)
        
        # Create Flutterwave payment link
        payload = {
            "tx_ref": payment.flutterwave_tx_ref,
            "amount": str(link_data.amount),
            "currency": link_data.currency,
            "customer": {
                "email": link_data.customer_email,
                "name": link_data.customer_name
            },
            "customizations": {
                "title": "MyTypist Payment Link",
                "description": link_data.description
            }
        }
        
        headers = {
            "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{PaymentService.FLUTTERWAVE_BASE_URL}/payment-links",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get("status") == "success":
                data = response_data.get("data", {})
                expires_at = datetime.utcnow() + timedelta(hours=link_data.expires_in_hours)
                
                return PaymentLinkResponse(
                    payment_link=data.get("link"),
                    reference=payment.flutterwave_tx_ref,
                    expires_at=expires_at
                )
            else:
                raise FlutterwaveError(response_data.get("message", "Failed to create payment link"))
        
        except requests.exceptions.RequestException as e:
            raise FlutterwaveError(f"Network error: {str(e)}")
    
    @staticmethod
    def process_refund(db: Session, payment: Payment, refund_data: RefundRequest) -> RefundResponse:
        """Process payment refund"""
        
        refund_amount = refund_data.amount or payment.amount
        
        # Create refund with Flutterwave
        payload = {
            "id": payment.flutterwave_id,
            "amount": str(refund_amount)
        }
        
        headers = {
            "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{PaymentService.FLUTTERWAVE_BASE_URL}/transactions/{payment.flutterwave_id}/refund",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get("status") == "success":
                # Update payment record
                payment.refund_amount = refund_amount
                payment.refund_reason = refund_data.reason
                payment.refunded_at = datetime.utcnow()
                
                if refund_amount >= payment.amount:
                    payment.status = PaymentStatus.REFUNDED
                
                db.commit()
                
                return RefundResponse(
                    id=payment.id,
                    payment_id=payment.id,
                    amount=refund_amount,
                    reason=refund_data.reason,
                    status="processed",
                    processed_at=datetime.utcnow()
                )
            else:
                raise FlutterwaveError(response_data.get("message", "Refund failed"))
        
        except requests.exceptions.RequestException as e:
            raise FlutterwaveError(f"Network error: {str(e)}")
    
    @staticmethod
    def get_user_payment_stats(db: Session, user_id: int) -> PaymentStats:
        """Get payment statistics for user"""
        
        # Total revenue
        total_revenue_result = db.query(func.sum(Payment.amount)).filter(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.COMPLETED
        ).scalar()
        total_revenue = float(total_revenue_result or 0)
        
        # Transaction counts
        total_transactions = db.query(Payment).filter(Payment.user_id == user_id).count()
        successful_transactions = db.query(Payment).filter(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.COMPLETED
        ).count()
        failed_transactions = db.query(Payment).filter(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.FAILED
        ).count()
        
        # Average transaction value
        avg_transaction = total_revenue / successful_transactions if successful_transactions > 0 else 0
        
        # Monthly revenue
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        
        this_month_revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.COMPLETED,
            Payment.completed_at >= current_month_start
        ).scalar() or 0
        
        last_month_revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.COMPLETED,
            Payment.completed_at >= last_month_start,
            Payment.completed_at < current_month_start
        ).scalar() or 0
        
        # Growth rate
        if last_month_revenue > 0:
            growth_rate = ((this_month_revenue - last_month_revenue) / last_month_revenue) * 100
        else:
            growth_rate = 100.0 if this_month_revenue > 0 else 0.0
        
        # Top payment methods
        payment_methods = db.query(
            Payment.payment_method,
            func.count(Payment.id).label('count'),
            func.sum(Payment.amount).label('total_amount')
        ).filter(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.COMPLETED
        ).group_by(Payment.payment_method).all()
        
        top_payment_methods = [
            {
                "method": method.payment_method.value,
                "count": method.count,
                "total_amount": float(method.total_amount or 0)
            }
            for method in payment_methods
        ]
        
        return PaymentStats(
            total_revenue=total_revenue,
            total_transactions=total_transactions,
            successful_transactions=successful_transactions,
            failed_transactions=failed_transactions,
            average_transaction_value=avg_transaction,
            this_month_revenue=float(this_month_revenue),
            last_month_revenue=float(last_month_revenue),
            growth_rate=growth_rate,
            top_payment_methods=top_payment_methods
        )
    
    # Subscription methods
    
    @staticmethod
    def create_subscription(db: Session, subscription_data: SubscriptionCreate, 
                          user_id: int, request: Request) -> Subscription:
        """Create new subscription"""
        
        # Get plan details
        plan_info = PaymentService._get_plan_info(subscription_data.plan)
        
        # Calculate amount based on billing cycle
        if subscription_data.billing_cycle == "yearly":
            amount = plan_info["yearly_price"]
        else:
            amount = plan_info["monthly_price"]
        
        # Create subscription record
        starts_at = datetime.utcnow()
        if subscription_data.billing_cycle == "yearly":
            ends_at = starts_at + timedelta(days=365)
        else:
            ends_at = starts_at + timedelta(days=30)
        
        subscription = Subscription(
            user_id=user_id,
            plan=subscription_data.plan,
            status=SubscriptionStatus.ACTIVE,
            amount=amount,
            billing_cycle=subscription_data.billing_cycle,
            documents_limit=plan_info["documents_limit"],
            templates_limit=plan_info["templates_limit"],
            storage_limit=plan_info["storage_limit"],
            custom_templates=plan_info["custom_templates"],
            api_access=plan_info["api_access"],
            priority_support=plan_info["priority_support"],
            white_label=plan_info["white_label"],
            starts_at=starts_at,
            ends_at=ends_at,
            next_billing_date=ends_at,
            auto_renew=subscription_data.auto_renew
        )
        
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        
        # Create initial payment if not free plan
        if subscription_data.plan != SubscriptionPlan.FREE:
            payment_data = PaymentCreate(
                amount=amount,
                description=f"{subscription_data.plan.value.title()} subscription - {subscription_data.billing_cycle}",
                payment_method=subscription_data.payment_method
            )
            
            payment = PaymentService.create_payment(db, payment_data, user_id)
            subscription.payment_id = payment.id
            db.commit()
        
        return subscription
    
    @staticmethod
    def update_subscription(db: Session, subscription: Subscription, 
                          subscription_update: SubscriptionUpdate) -> Subscription:
        """Update subscription"""
        
        for field, value in subscription_update.dict(exclude_unset=True).items():
            setattr(subscription, field, value)
        
        subscription.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(subscription)
        
        return subscription
    
    @staticmethod
    def cancel_subscription(db: Session, subscription: Subscription, reason: Optional[str] = None) -> None:
        """Cancel subscription"""
        
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancelled_at = datetime.utcnow()
        subscription.auto_renew = False
        
        db.commit()
    
    @staticmethod
    def _generate_invoice_atomic(db: Session, subscription: Subscription, payment: Payment) -> Invoice:
        """Generate invoice for subscription payment atomically within transaction"""
        
        invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{subscription.id:06d}"
        
        line_items = [
            {
                "description": f"{subscription.plan.value.title()} Plan - {subscription.billing_cycle.title()}",
                "quantity": 1,
                "unit_price": subscription.amount,
                "total": subscription.amount
            }
        ]
        
        invoice = Invoice(
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            payment_id=payment.id,
            invoice_number=invoice_number,
            amount=subscription.amount,
            currency=payment.currency,
            total_amount=subscription.amount,
            billing_period_start=subscription.starts_at,
            billing_period_end=subscription.ends_at,
            due_date=subscription.starts_at + timedelta(days=30),
            status="paid",
            paid_at=payment.completed_at,
            customer_name=payment.customer_name,
            customer_email=payment.customer_email,
            line_items=line_items
        )
        
        db.add(invoice)
        # Note: Not calling commit() here - will be committed by caller atomically
        
        return invoice
    
    @staticmethod
    def _generate_invoice(db: Session, subscription: Subscription, payment: Payment) -> Invoice:
        """Generate invoice for subscription payment"""
        
        invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{subscription.id:06d}"
        
        line_items = [
            {
                "description": f"{subscription.plan.value.title()} Plan - {subscription.billing_cycle.title()}",
                "quantity": 1,
                "unit_price": subscription.amount,
                "total": subscription.amount
            }
        ]
        
        invoice = Invoice(
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            payment_id=payment.id,
            invoice_number=invoice_number,
            amount=subscription.amount,
            currency=payment.currency,
            total_amount=subscription.amount,
            billing_period_start=subscription.starts_at,
            billing_period_end=subscription.ends_at,
            due_date=subscription.starts_at + timedelta(days=30),
            status="paid",
            paid_at=payment.completed_at,
            customer_name=payment.customer_name,
            customer_email=payment.customer_email,
            line_items=line_items
        )
        
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        
        return invoice
    
    @staticmethod
    def get_subscription_plans() -> List[SubscriptionPlanInfo]:
        """Get available subscription plans"""
        
        return [
            SubscriptionPlanInfo(
                plan=SubscriptionPlan.FREE,
                name="Free",
                description="Basic document generation",
                monthly_price=0.0,
                yearly_price=0.0,
                features=[
                    "5 documents per month",
                    "Basic templates",
                    "Standard support"
                ],
                documents_limit=5,
                templates_limit=10,
                storage_limit=100 * 1024 * 1024,  # 100MB
                custom_templates=False,
                api_access=False,
                priority_support=False,
                white_label=False
            ),
            SubscriptionPlanInfo(
                plan=SubscriptionPlan.BASIC,
                name="Basic",
                description="Enhanced document generation",
                monthly_price=2000.0,  # 2000 NGN
                yearly_price=20000.0,  # 20000 NGN (2 months free)
                features=[
                    "100 documents per month",
                    "All templates",
                    "Priority support",
                    "Custom templates"
                ],
                documents_limit=100,
                templates_limit=-1,  # Unlimited
                storage_limit=1024 * 1024 * 1024,  # 1GB
                custom_templates=True,
                api_access=False,
                priority_support=True,
                white_label=False,
                popular=True
            ),
            SubscriptionPlanInfo(
                plan=SubscriptionPlan.PRO,
                name="Professional",
                description="Advanced features for professionals",
                monthly_price=5000.0,  # 5000 NGN
                yearly_price=50000.0,  # 50000 NGN
                features=[
                    "1000 documents per month",
                    "API access",
                    "White label",
                    "Advanced analytics",
                    "Priority support"
                ],
                documents_limit=1000,
                templates_limit=-1,
                storage_limit=5 * 1024 * 1024 * 1024,  # 5GB
                custom_templates=True,
                api_access=True,
                priority_support=True,
                white_label=True
            ),
            SubscriptionPlanInfo(
                plan=SubscriptionPlan.ENTERPRISE,
                name="Enterprise",
                description="Unlimited usage for enterprises",
                monthly_price=15000.0,  # 15000 NGN
                yearly_price=150000.0,  # 150000 NGN
                features=[
                    "Unlimited documents",
                    "Unlimited storage",
                    "API access",
                    "White label",
                    "Dedicated support",
                    "Custom integrations"
                ],
                documents_limit=-1,
                templates_limit=-1,
                storage_limit=-1,
                custom_templates=True,
                api_access=True,
                priority_support=True,
                white_label=True
            )
        ]
    
    @staticmethod
    def _get_plan_info(plan: SubscriptionPlan) -> Dict[str, Any]:
        """Get plan information"""
        
        plans = {plan.plan: plan for plan in PaymentService.get_subscription_plans()}
        return plans.get(plan, {})
    
    @staticmethod
    def get_billing_history(db: Session, user_id: int) -> BillingHistory:
        """Get user's billing history"""
        
        # Get payments
        payments = db.query(Payment).filter(
            Payment.user_id == user_id
        ).order_by(desc(Payment.created_at)).all()
        
        # Get invoices
        invoices = db.query(Invoice).filter(
            Invoice.user_id == user_id
        ).order_by(desc(Invoice.created_at)).all()
        
        # Calculate total spent
        total_spent = db.query(func.sum(Payment.amount)).filter(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.COMPLETED
        ).scalar() or 0
        
        # Get current subscription
        current_subscription = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).first()
        
        next_billing_date = None
        payment_method = None
        
        if current_subscription:
            next_billing_date = current_subscription.next_billing_date
            # Get most recent payment method
            recent_payment = db.query(Payment).filter(
                Payment.user_id == user_id,
                Payment.status == PaymentStatus.COMPLETED
            ).order_by(desc(Payment.completed_at)).first()
            
            if recent_payment:
                payment_method = recent_payment.payment_method.value
        
        return BillingHistory(
            payments=payments,
            invoices=invoices,
            total_spent=float(total_spent),
            next_billing_date=next_billing_date,
            payment_method=payment_method
        )
    
    @staticmethod
    def generate_invoice_pdf(invoice: Invoice) -> str:
        """Generate PDF content for invoice using ReportLab"""
        import base64
        from io import BytesIO
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
        
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4,
                                  rightMargin=72, leftMargin=72,
                                  topMargin=72, bottomMargin=72)
            
            # Get styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=1,  # Center alignment
                textColor=colors.darkblue
            )
            
            # Build story
            story = []
            
            # Header
            story.append(Paragraph("MyTypist Invoice", title_style))
            story.append(Spacer(1, 12))
            
            # Invoice details table
            invoice_data = [
                ['Invoice Number:', invoice.invoice_number],
                ['Date:', invoice.created_at.strftime('%Y-%m-%d %H:%M:%S')],
                ['Status:', invoice.status.value],
                ['Due Date:', invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else 'N/A']
            ]
            
            invoice_table = Table(invoice_data, colWidths=[2*inch, 3*inch])
            invoice_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ]))
            
            story.append(invoice_table)
            story.append(Spacer(1, 12))
            
            # Customer details
            story.append(Paragraph("Bill To:", styles['Heading2']))
            customer_data = [
                ['Name:', invoice.customer_name],
                ['Email:', invoice.customer_email],
                ['Phone:', invoice.customer_phone or 'N/A']
            ]
            
            customer_table = Table(customer_data, colWidths=[2*inch, 3*inch])
            customer_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ]))
            
            story.append(customer_table)
            story.append(Spacer(1, 20))
            
            # Line items
            story.append(Paragraph("Items:", styles['Heading2']))
            
            # Parse line items from JSON if available
            line_items_data = [['Description', 'Quantity', 'Unit Price', 'Total']]
            
            if invoice.line_items:
                for item in invoice.line_items:
                    line_items_data.append([
                        item.get('description', 'N/A'),
                        str(item.get('quantity', 1)),
                        f"{invoice.currency} {item.get('unit_price', invoice.subtotal)}",
                        f"{invoice.currency} {item.get('total', invoice.subtotal)}"
                    ])
            else:
                # Default single item
                line_items_data.append([
                    invoice.description or 'MyTypist Service',
                    '1',
                    f"{invoice.currency} {invoice.subtotal}",
                    f"{invoice.currency} {invoice.subtotal}"
                ])
            
            # Add totals
            line_items_data.extend([
                ['', '', 'Subtotal:', f"{invoice.currency} {invoice.subtotal}"],
                ['', '', 'Tax:', f"{invoice.currency} {invoice.tax_amount}"],
                ['', '', 'Total:', f"{invoice.currency} {invoice.total_amount}"]
            ])
            
            items_table = Table(line_items_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -4), colors.beige),
                ('BACKGROUND', (0, -3), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -3), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(items_table)
            story.append(Spacer(1, 20))
            
            # Payment status and notes
            if invoice.notes:
                story.append(Paragraph("Notes:", styles['Heading3']))
                story.append(Paragraph(invoice.notes, styles['Normal']))
            
            # Footer
            story.append(Spacer(1, 30))
            footer_text = "Thank you for your business! For questions about this invoice, please contact support@mytypist.net"
            story.append(Paragraph(footer_text, styles['Normal']))
            
            # Build PDF
            doc.build(story)
            
            # Get PDF content and encode
            pdf_content = buffer.getvalue()
            buffer.close()
            
            return base64.b64encode(pdf_content).decode('utf-8')
            
        except Exception as e:
            # Fallback to simple text-based PDF in case of error
            from reportlab.pdfgen import canvas
            from io import BytesIO
            
            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
            
            # Simple text layout
            p.drawString(100, height - 100, f"MyTypist Invoice: {invoice.invoice_number}")
            p.drawString(100, height - 140, f"Customer: {invoice.customer_name}")
            p.drawString(100, height - 160, f"Email: {invoice.customer_email}")
            p.drawString(100, height - 180, f"Amount: {invoice.currency} {invoice.total_amount}")
            p.drawString(100, height - 200, f"Date: {invoice.created_at.strftime('%Y-%m-%d')}")
            p.drawString(100, height - 220, f"Status: {invoice.status.value}")
            
            p.save()
            
            pdf_content = buffer.getvalue()
            buffer.close()
            
            return base64.b64encode(pdf_content).decode('utf-8')
