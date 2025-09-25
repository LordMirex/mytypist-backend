"""Admin routes for managing rewards and campaigns"""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from app.services.auth_service import AuthService
from app.services.campaign_service import CampaignService
from app.services.campaign_analytics_service import CampaignAnalyticsService
from app.services.token_management_service import TokenManagementService
from app.services.referral_service import ReferralService
from datetime import datetime
from pydantic import BaseModel
import logging

from app.models.referral import ReferralProgram

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/rewards", tags=["admin-rewards"])


class TokenRewardUpdate(BaseModel):
    """Request to update token reward settings"""
    welcome_bonus_amount: Optional[int] = None
    referral_bonus_amount: Optional[int] = None
    document_token_cost: Optional[int] = None
    template_token_cost: Optional[int] = None
    api_token_cost: Optional[int] = None


class TokenBulkGift(BaseModel):
    """Request to gift tokens to multiple users"""
    user_ids: List[int]
    token_type: str
    amount: int
    description: str
    expires_in_days: Optional[int] = None


class CampaignMetricUpdate(BaseModel):
    """Request to manually update campaign metrics"""
    campaign_id: int
    metrics: Dict[str, Any]


@router.put("/token-settings")
async def update_token_settings(
    request: TokenRewardUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Update token reward settings"""
    try:
        updated_settings = {}
        
        if request.welcome_bonus_amount is not None:
            TokenManagementService.DEFAULT_WELCOME_BONUS = request.welcome_bonus_amount
            updated_settings["welcome_bonus"] = request.welcome_bonus_amount
            
        if request.referral_bonus_amount is not None:
            TokenManagementService.DEFAULT_REFERRAL_BONUS = request.referral_bonus_amount
            updated_settings["referral_bonus"] = request.referral_bonus_amount
            
        if request.document_token_cost is not None:
            TokenManagementService.DEFAULT_DOCUMENT_COST = request.document_token_cost
            updated_settings["document_cost"] = request.document_token_cost
            
        if request.template_token_cost is not None:
            TokenManagementService.DEFAULT_TEMPLATE_COST = request.template_token_cost
            updated_settings["template_cost"] = request.template_token_cost
            
        if request.api_token_cost is not None:
            TokenManagementService.DEFAULT_API_COST = request.api_token_cost
            updated_settings["api_cost"] = request.api_token_cost

        return {
            "success": True,
            "updated_settings": updated_settings
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update token settings: {str(e)}"
        )


@router.post("/gift-tokens")
async def gift_tokens_bulk(
    request: TokenBulkGift,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Gift tokens to multiple users"""
    results = []
    failures = []

    for user_id in request.user_ids:
        success = TokenManagementService.add_tokens(
            db=db,
            user_id=user_id,
            token_type=request.token_type,
            amount=request.amount,
            description=request.description,
            reference_type="admin_gift",
            expires_in_days=request.expires_in_days
        )

        if success:
            results.append(user_id)
        else:
            failures.append(user_id)

    return {
        "success": True,
        "gifted_users": len(results),
        "failed_users": len(failures),
        "failed_user_ids": failures
    }


@router.get("/campaign-analytics/{campaign_id}")
async def get_campaign_analytics(
    campaign_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get detailed campaign analytics"""
    date_range = (start_date, end_date) if start_date and end_date else None
    
    result = CampaignAnalyticsService.get_campaign_analytics(
        db=db,
        campaign_id=campaign_id,
        date_range=date_range
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["message"]
        )

    return result


@router.put("/campaign-metrics/{campaign_id}")
async def update_campaign_metrics(
    request: CampaignMetricUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Manually update campaign metrics"""
    from app.models.campaign import Campaign
    campaign = db.query(Campaign).filter(Campaign.id == request.campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    try:
        for metric, value in request.metrics.items():
            if hasattr(campaign, metric):
                setattr(campaign, metric, value)

        db.commit()
        db.refresh(campaign)

        return {
            "success": True,
            "campaign_id": campaign.id,
            "updated_metrics": request.metrics
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update metrics: {str(e)}"
        )


@router.get("/referral-programs")
async def get_referral_programs(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get list of referral programs"""
    from app.models.referral import ReferralProgram
    query = db.query(ReferralProgram)

    if active_only:
        query = query.filter(ReferralProgram.is_active == True)
    
    programs = query.all()
    
    return {
        "success": True,
        "programs": [
            {
                "id": p.id,
                "name": p.name,
                "code": p.program_code,
                "active": p.is_active,
                "referrer_reward": p.referrer_token_amount,
                "referee_reward": p.referee_token_amount,
                "total_referrals": p.total_referrals,
                "total_rewards": p.total_rewards_given,
                "conversion_rate": p.conversion_rate,
                "start_date": p.starts_at.isoformat(),
                "end_date": p.ends_at.isoformat()
            } for p in programs
        ]
    }


@router.get("/referral-analytics/{program_id}")
async def get_referral_analytics(
    program_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get detailed referral program analytics"""
    program = db.query(ReferralProgram).filter(ReferralProgram.id == program_id).first()
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral program not found"
        )

    analytics = await ReferralService.get_program_analytics(db, program_id)
    
    if not analytics["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=analytics["message"]
        )

    return analytics