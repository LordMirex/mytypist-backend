"""Referral system API routes"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from database import get_db
from app.services.auth_service import AuthService
from app.services.referral_service import ReferralService
from app.middleware.rate_limit import rate_limit
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api/referrals", tags=["referrals"])


class ReferralProgramCreate(BaseModel):
    """Request to create a referral program"""
    name: str
    description: Optional[str] = None
    program_code: str
    referrer_token_amount: int
    referee_token_amount: int
    bonus_multiplier: float = 1.0
    max_referrals_per_user: Optional[int] = None
    max_total_referrals: Optional[int] = None
    max_total_rewards: Optional[int] = None
    min_referrer_age_days: int = 0
    referrer_requires_email: bool = True
    referrer_requires_purchase: bool = False
    starts_at: str
    ends_at: str


class ReferralLinkCreate(BaseModel):
    """Request to create a referral link"""
    program_code: str
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ReferralProcess(BaseModel):
    """Request to process a referral"""
    referral_code: str
    metadata: Optional[Dict[str, Any]] = None


@router.post("/admin/programs")
async def create_program(
    request: ReferralProgramCreate,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Create a new referral program (admin only)"""
    result = ReferralService.create_referral_program(
        db=db,
        admin_user_id=current_user.id,
        program_data=request.dict()
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )

    return result


@router.post("/create-link")
@rate_limit(max_requests=5, window_seconds=3600)  # 5 requests per hour
async def create_referral_link(
    request: ReferralLinkCreate,
    req: Request,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_user)
):
    """Create a new referral link with rate limiting"""
    result = ReferralService.create_referral_link(
        db=db,
        user_id=current_user.id,
        program_code=request.program_code,
        source=request.source,
        metadata=request.metadata
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )

    return result


@router.post("/process")
async def process_referral(
    request: ReferralProcess,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_user)
):
    """Process a referral for a new user"""
    result = ReferralService.process_referral(
        db=db,
        referral_code=request.referral_code,
        new_user_id=current_user.id,
        referral_data=request.metadata
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )

    return result


@router.get("/my-referrals")
async def get_my_referrals(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_user)
):
    """Get user's referral history"""
    result = ReferralService.get_user_referrals(
        db=db,
        user_id=current_user.id,
        status=status,
        limit=limit,
        offset=offset
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )

    return result


@router.get("/admin/programs/{program_id}/analytics")
async def get_program_analytics(
    program_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get analytics for a referral program (admin only)"""
    result = ReferralService.get_program_analytics(
        db=db,
        program_id=program_id
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["message"]
        )

    return result