"""
Production-ready Token-based Payment System
Advanced wallet with fraud detection, subscription plans, and comprehensive transaction management
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator
import logging

from database import get_db
from app.models.user import User
from app.utils.security import get_current_active_user, get_client_ip
from app.services.wallet_service import WalletService
from app.services.audit_service import AuditService
from app.services.fraud_detection_service import FraudDetectionService
from app.services.subscription_service import SubscriptionService

router = APIRouter()
logger = logging.getLogger(__name__)


# Enhanced Pydantic models for token system
class TokenPurchaseRequest(BaseModel):
    """Token purchase request with fraud detection"""
    amount: float
    token_quantity: int
    payment_method: str = "flutterwave"
    device_fingerprint: Optional[str] = None

    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        if v > 10000:  # Maximum purchase limit
            raise ValueError('Amount exceeds maximum limit')
        return v

    @validator('token_quantity')
    def validate_token_quantity(cls, v):
        if v <= 0:
            raise ValueError('Token quantity must be positive')
        if v > 100000:  # Maximum token purchase
            raise ValueError('Token quantity exceeds maximum limit')
        return v


class SubscriptionPurchaseRequest(BaseModel):
    """Subscription plan purchase request"""
    plan_type: str
    billing_cycle: str = "monthly"  # monthly, yearly
    auto_renewal: bool = True
    device_fingerprint: Optional[str] = None

    @validator('plan_type')
    def validate_plan_type(cls, v):
        valid_plans = ["pay_as_you_go", "business", "enterprise"]
        if v not in valid_plans:
            raise ValueError(f'Plan type must be one of: {valid_plans}')
        return v

    @validator('billing_cycle')
    def validate_billing_cycle(cls, v):
        valid_cycles = ["monthly", "yearly"]
        if v not in valid_cycles:
            raise ValueError(f'Billing cycle must be one of: {valid_cycles}')
        return v


class WalletTransferRequest(BaseModel):
    """Internal wallet transfer request"""
    recipient_email: str
    amount: float
    description: str

    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        if v > 1000:  # Maximum transfer limit
            raise ValueError('Amount exceeds maximum transfer limit')
        return v


@router.get("/balance")
async def get_wallet_balance(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive wallet balance and token information"""

    try:
        balance_info = WalletService.get_wallet_balance(db, current_user.id)

        # Add token-specific information
        token_info = await WalletService.get_token_information(db, current_user.id)

        return {
            **balance_info,
            "tokens": token_info,
            "subscription": await SubscriptionService.get_user_subscription_info(db, current_user.id)
        }

    except Exception as e:
        logger.error(f"Get wallet balance failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve wallet balance"
        )


@router.post("/purchase-tokens")
async def purchase_tokens(
    purchase_request: TokenPurchaseRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Purchase tokens with advanced fraud detection"""

    client_ip = get_client_ip(request)

    try:
        # Fraud detection check
        fraud_assessment = await FraudDetectionService.assess_payment_risk(
            db=db,
            user_id=current_user.id,
            amount=purchase_request.amount,
            ip_address=client_ip,
            payment_method=purchase_request.payment_method,
            device_fingerprint=purchase_request.device_fingerprint
        )

        # Block if high risk
        if fraud_assessment["should_block"]:
            await FraudDetectionService.create_fraud_alert(
                db=db,
                user_id=current_user.id,
                fraud_type="payment_fraud",
                risk_level=fraud_assessment["risk_level"],
                confidence_score=fraud_assessment["risk_score"],
                evidence=fraud_assessment["evidence"],
                description=f"Blocked token purchase: {', '.join(fraud_assessment['risk_factors'])}",
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent"),
                device_fingerprint=purchase_request.device_fingerprint
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Transaction blocked due to security concerns. Please contact support."
            )

        # Process token purchase
        result = await WalletService.purchase_tokens(
            db=db,
            user_id=current_user.id,
            token_quantity=purchase_request.token_quantity,
            amount=purchase_request.amount,
            payment_method=purchase_request.payment_method,
            fraud_assessment=fraud_assessment
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )

        # Log successful token purchase
        AuditService.log_auth_event(
            "TOKEN_PURCHASE",
            current_user.id,
            request,
            {
                "token_quantity": purchase_request.token_quantity,
                "amount": purchase_request.amount,
                "payment_method": purchase_request.payment_method,
                "fraud_score": fraud_assessment["risk_score"]
            }
        )

        return {
            "success": True,
            "message": f"Successfully purchased {purchase_request.token_quantity} tokens",
            "transaction_id": result["transaction_id"],
            "tokens_purchased": purchase_request.token_quantity,
            "amount_paid": purchase_request.amount,
            "new_balance": result["new_balance"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token purchase failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token purchase failed. Please try again."
        )


@router.post("/purchase-subscription")
async def purchase_subscription(
    subscription_request: SubscriptionPurchaseRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Purchase subscription plan with fraud detection"""

    client_ip = get_client_ip(request)

    try:
        # Get subscription plan details
        plan_details = await SubscriptionService.get_plan_details(subscription_request.plan_type, subscription_request.billing_cycle)

        if not plan_details:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid subscription plan"
            )

        # Fraud detection check
        fraud_assessment = await FraudDetectionService.assess_payment_risk(
            db=db,
            user_id=current_user.id,
            amount=plan_details["amount"],
            ip_address=client_ip,
            payment_method="subscription",
            device_fingerprint=subscription_request.device_fingerprint
        )

        # Block if high risk
        if fraud_assessment["should_block"]:
            await FraudDetectionService.create_fraud_alert(
                db=db,
                user_id=current_user.id,
                fraud_type="payment_fraud",
                risk_level=fraud_assessment["risk_level"],
                confidence_score=fraud_assessment["risk_score"],
                evidence=fraud_assessment["evidence"],
                description=f"Blocked subscription purchase: {', '.join(fraud_assessment['risk_factors'])}",
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent"),
                device_fingerprint=subscription_request.device_fingerprint
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subscription blocked due to security concerns. Please contact support."
            )

        # Process subscription purchase
        result = await SubscriptionService.create_subscription(
            db=db,
            user_id=current_user.id,
            plan_type=subscription_request.plan_type,
            billing_cycle=subscription_request.billing_cycle,
            auto_renewal=subscription_request.auto_renewal,
            fraud_assessment=fraud_assessment
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )

        # Log successful subscription purchase
        AuditService.log_auth_event(
            "SUBSCRIPTION_PURCHASE",
            current_user.id,
            request,
            {
                "plan_type": subscription_request.plan_type,
                "billing_cycle": subscription_request.billing_cycle,
                "amount": plan_details["amount"],
                "auto_renewal": subscription_request.auto_renewal
            }
        )

        return {
            "success": True,
            "message": f"Successfully subscribed to {subscription_request.plan_type} plan",
            "subscription_id": result["subscription_id"],
            "plan_details": plan_details,
            "next_billing_date": result["next_billing_date"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Subscription purchase failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Subscription purchase failed. Please try again."
        )


@router.post("/validate-free-eligibility")
async def validate_free_token_eligibility(
    device_fingerprint: Optional[str] = Body(None),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Validate if user is eligible for free tokens (prevent abuse)"""

    client_ip = get_client_ip(request)

    try:
        # Check eligibility
        eligibility = await FraudDetectionService.validate_free_token_eligibility(
            db=db,
            ip_address=client_ip,
            device_fingerprint=device_fingerprint or "",
            email=current_user.email if current_user else ""
        )

        # Track device fingerprint if provided
        if device_fingerprint and current_user:
            await FraudDetectionService.track_device_fingerprint(
                db=db,
                user_id=current_user.id,
                fingerprint_data={
                    "user_agent": request.headers.get("user-agent"),
                    "device_fingerprint": device_fingerprint
                }
            )

        return {
            "eligible": eligibility["eligible"],
            "reason": eligibility["reason"],
            "message": "You are eligible for free tokens!" if eligibility["eligible"] else "Free token limit reached for this device/IP."
        }

    except Exception as e:
        logger.error(f"Free token eligibility check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Eligibility check failed"
        )


@router.get("/transaction-history")
async def get_transaction_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    transaction_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's transaction history with pagination"""

    try:
        history = await WalletService.get_transaction_history(
            db=db,
            user_id=current_user.id,
            page=page,
            per_page=per_page,
            transaction_type=transaction_type
        )

        return {
            "success": True,
            "transactions": history["transactions"],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": history["total"],
                "pages": (history["total"] + per_page - 1) // per_page
            }
        }

    except Exception as e:
        logger.error(f"Get transaction history failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transaction history"
        )


@router.get("/admin/token-rates")
async def get_token_rates(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current token exchange rates (Admin can modify)"""

    # Check admin permissions for modification
    can_modify = current_user.is_admin

    try:
        rates = await WalletService.get_token_rates(db)

        return {
            "success": True,
            "rates": rates,
            "can_modify": can_modify
        }

    except Exception as e:
        logger.error(f"Get token rates failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve token rates"
        )


@router.post("/admin/update-token-rates")
async def update_token_rates(
    rates: Dict[str, float] = Body(...),
    current_user: User = Depends(get_current_active_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Update token exchange rates (Admin only)"""

    # Check admin permissions
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        result = await WalletService.update_token_rates(db, rates)

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )

        # Log rate update
        AuditService.log_auth_event(
            "TOKEN_RATES_UPDATED",
            current_user.id,
            request,
            {"new_rates": rates}
        )

        return {
            "success": True,
            "message": "Token rates updated successfully",
            "new_rates": rates
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update token rates failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update token rates"
        )
