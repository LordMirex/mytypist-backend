"""
Token Management API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
from pydantic import BaseModel

from database import get_db
from app.services.token_management_service import TokenManagementService
from app.services.auth_service import AuthService
from app.models.token import TokenType

router = APIRouter(prefix="/api/tokens", tags=["tokens"])


class WelcomeBonusRequest(BaseModel):
    """Request to claim welcome bonus"""
    pass


class ReferralRequest(BaseModel):
    """Request to process referral"""
    referral_code: str


class CampaignCreateRequest(BaseModel):
    """Request to create token campaign"""
    name: str
    description: str = None
    campaign_code: str
    token_type: str
    token_amount: int
    bonus_multiplier: float = 1.0
    max_users: int = None
    max_tokens_per_user: int = None
    max_total_tokens: int = None
    starts_at: str
    ends_at: str
    min_account_age_days: int = 0
    requires_email_verification: bool = True
    requires_phone_verification: bool = False


@router.get("/balance")
async def get_token_balance(
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_user)
):
    """Get user's token balance and statistics"""
    try:
        balance_data = TokenManagementService.get_user_token_balance(
            db=db, 
            user_id=current_user.id
        )
        
        if not balance_data["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=balance_data["message"]
            )
        
        return {
            "status": "success",
            "data": balance_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get token balance: {str(e)}"
        )


@router.post("/claim-welcome-bonus")
async def claim_welcome_bonus(
    request: WelcomeBonusRequest,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_user)
):
    """Claim welcome bonus tokens"""
    try:
        result = TokenManagementService.claim_welcome_bonus(
            db=db,
            user_id=current_user.id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "data": result,
            "message": result["message"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to claim welcome bonus: {str(e)}"
        )


@router.post("/process-referral")
async def process_referral(
    request: ReferralRequest,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_user)
):
    """Process referral bonus for new user"""
    try:
        result = TokenManagementService.process_referral_bonus(
            db=db,
            new_user_id=current_user.id,
            referral_code=request.referral_code
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "data": result,
            "message": result["message"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process referral: {str(e)}"
        )


@router.get("/referral-code")
async def get_referral_code(
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_user)
):
    """Get user's referral code"""
    try:
        balance_data = TokenManagementService.get_user_token_balance(
            db=db,
            user_id=current_user.id
        )
        
        if not balance_data["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get referral code"
            )
        
        return {
            "status": "success",
            "referral_code": balance_data["referral_info"]["referral_code"],
            "referral_bonus_earned": balance_data["referral_info"]["referral_bonus_earned"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get referral code: {str(e)}"
        )


@router.get("/transactions")
async def get_token_transactions(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_user)
):
    """Get user's token transaction history"""
    try:
        from app.models.token import TokenTransaction
        from sqlalchemy import desc
        
        transactions = db.query(TokenTransaction).filter(
            TokenTransaction.user_id == current_user.id
        ).order_by(desc(TokenTransaction.created_at)).offset(offset).limit(limit).all()
        
        transaction_list = []
        for transaction in transactions:
            transaction_list.append({
                "id": transaction.id,
                "transaction_type": transaction.transaction_type.value,
                "token_type": transaction.token_type.value,
                "amount": transaction.amount,
                "balance_after": transaction.balance_after,
                "description": transaction.description,
                "reference_id": transaction.reference_id,
                "reference_type": transaction.reference_type,
                "created_at": transaction.created_at.isoformat(),
                "expires_at": transaction.expires_at.isoformat() if transaction.expires_at else None
            })
        
        return {
            "status": "success",
            "transactions": transaction_list,
            "total": len(transaction_list)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transactions: {str(e)}"
        )


@router.post("/admin/create-campaign")
async def create_campaign(
    request: CampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Create token campaign (admin only)"""
    try:
        campaign_data = request.dict()
        
        result = TokenManagementService.create_token_campaign(
            db=db,
            admin_user_id=current_user.id,
            campaign_data=campaign_data
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "data": result,
            "message": result["message"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create campaign: {str(e)}"
        )


@router.post("/admin/award-tokens")
async def award_tokens_admin(
    user_id: int,
    token_type: str,
    amount: int,
    description: str,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Award tokens to user (admin only)"""
    try:
        success = TokenManagementService.add_tokens(
            db=db,
            user_id=user_id,
            token_type=TokenType(token_type),
            amount=amount,
            description=f"Admin award: {description}",
            reference_type="admin_award"
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to award tokens"
            )
        
        return {
            "status": "success",
            "message": f"Awarded {amount} {token_type} tokens to user {user_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to award tokens: {str(e)}"
        )


@router.get("/admin/statistics")
async def get_token_statistics(
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get token statistics (admin only)"""
    try:
        from app.models.token import UserToken, TokenTransaction
        from sqlalchemy import func, desc
        
        # Get overall statistics
        total_users_with_tokens = db.query(UserToken).count()
        
        total_tokens_distributed = db.query(func.sum(UserToken.lifetime_earned)).scalar() or 0
        total_tokens_spent = db.query(func.sum(UserToken.lifetime_spent)).scalar() or 0
        
        welcome_bonuses_claimed = db.query(UserToken).filter(
            UserToken.welcome_bonus_claimed == True
        ).count()
        
        # Recent activity
        recent_transactions = db.query(TokenTransaction).order_by(
            desc(TokenTransaction.created_at)
        ).limit(10).all()
        
        return {
            "status": "success",
            "statistics": {
                "total_users_with_tokens": total_users_with_tokens,
                "total_tokens_distributed": total_tokens_distributed,
                "total_tokens_spent": total_tokens_spent,
                "tokens_in_circulation": total_tokens_distributed - total_tokens_spent,
                "welcome_bonuses_claimed": welcome_bonuses_claimed
            },
            "recent_activity": [
                {
                    "user_id": t.user_id,
                    "type": t.transaction_type.value,
                    "token_type": t.token_type.value,
                    "amount": t.amount,
                    "description": t.description,
                    "created_at": t.created_at.isoformat()
                }
                for t in recent_transactions
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )