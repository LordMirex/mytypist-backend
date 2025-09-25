"""
Campaign Management API Routes
Email marketing and token distribution campaigns
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, validator
from datetime import datetime

from database import get_db
from app.services.auth_service import AuthService
from app.services.campaign_service import CampaignService, Campaign, CampaignType, CampaignStatus
from app.models.user import UserRole

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignCreateRequest(BaseModel):
    """Request to create a new campaign"""
    name: str
    description: Optional[str] = None
    campaign_type: str
    
    # Targeting
    target_audience: Optional[Dict[str, Any]] = None
    target_user_ids: Optional[List[int]] = None
    exclude_user_ids: Optional[List[int]] = None
    
    # Email configuration
    send_email: bool = False
    email_subject: Optional[str] = None
    email_template_name: Optional[str] = None
    email_template_data: Optional[Dict[str, Any]] = None
    
    # Token gifting
    gift_tokens: bool = False
    token_type: Optional[str] = None
    token_amount: Optional[int] = None
    token_message: Optional[str] = None
    
    # Scheduling
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    send_immediately: bool = False
    recurring: bool = False
    recurring_interval: Optional[str] = None
    
    # Limits
    max_recipients: Optional[int] = None
    max_tokens_per_campaign: Optional[int] = None
    cooldown_hours: int = 24

    @validator('campaign_type')
    def validate_campaign_type(cls, v):
        try:
            CampaignType(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid campaign type: {v}")

    @validator('token_amount')
    def validate_token_amount(cls, v, values):
        if values.get('gift_tokens') and (v is None or v <= 0):
            raise ValueError("Token amount must be positive when gifting tokens")
        return v

    @validator('email_subject')
    def validate_email_subject(cls, v, values):
        if values.get('send_email') and not v:
            raise ValueError("Email subject required when sending emails")
        return v


class CampaignUpdateRequest(BaseModel):
    """Request to update campaign"""
    name: Optional[str] = None
    description: Optional[str] = None
    email_subject: Optional[str] = None
    email_template_data: Optional[Dict[str, Any]] = None
    token_amount: Optional[int] = None
    token_message: Optional[str] = None
    max_recipients: Optional[int] = None


@router.post("/create")
async def create_campaign(
    request: CampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Create a new marketing campaign (admin only)"""
    try:
        campaign_data = request.dict()
        
        result = CampaignService.create_campaign(
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


@router.get("/list")
async def list_campaigns(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
    campaign_type_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """List campaigns with optional filtering (admin only)"""
    try:
        query = db.query(Campaign).order_by(Campaign.created_at.desc())
        
        # Apply filters
        if status_filter:
            query = query.filter(Campaign.status == CampaignStatus(status_filter))
        
        if campaign_type_filter:
            query = query.filter(Campaign.campaign_type == CampaignType(campaign_type_filter))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        campaigns = query.offset(skip).limit(limit).all()
        
        campaign_list = []
        for campaign in campaigns:
            campaign_list.append({
                "id": campaign.id,
                "name": campaign.name,
                "description": campaign.description,
                "campaign_type": campaign.campaign_type.value,
                "status": campaign.status.value,
                "recipients_count": campaign.recipients_count,
                "emails_sent": campaign.emails_sent,
                "tokens_distributed": campaign.tokens_distributed,
                "created_at": campaign.created_at.isoformat(),
                "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
                "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None
            })
        
        return {
            "status": "success",
            "campaigns": campaign_list,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total,
                "has_more": skip + limit < total
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list campaigns: {str(e)}"
        )


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get campaign details (admin only)"""
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        return {
            "status": "success",
            "campaign": {
                "id": campaign.id,
                "name": campaign.name,
                "description": campaign.description,
                "campaign_type": campaign.campaign_type.value,
                "status": campaign.status.value,
                "target_audience": campaign.target_audience,
                "target_user_ids": campaign.target_user_ids,
                "exclude_user_ids": campaign.exclude_user_ids,
                "send_email": campaign.send_email,
                "email_subject": campaign.email_subject,
                "email_template_name": campaign.email_template_name,
                "email_template_data": campaign.email_template_data,
                "gift_tokens": campaign.gift_tokens,
                "token_type": campaign.token_type,
                "token_amount": campaign.token_amount,
                "token_message": campaign.token_message,
                "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
                "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
                "send_immediately": campaign.send_immediately,
                "recurring": campaign.recurring,
                "recurring_interval": campaign.recurring_interval,
                "max_recipients": campaign.max_recipients,
                "max_tokens_per_campaign": campaign.max_tokens_per_campaign,
                "cooldown_hours": campaign.cooldown_hours,
                "recipients_count": campaign.recipients_count,
                "emails_sent": campaign.emails_sent,
                "emails_opened": campaign.emails_opened,
                "emails_clicked": campaign.emails_clicked,
                "tokens_distributed": campaign.tokens_distributed,
                "total_cost": campaign.total_cost,
                "created_at": campaign.created_at.isoformat(),
                "executed_at": campaign.executed_at.isoformat() if campaign.executed_at else None,
                "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get campaign: {str(e)}"
        )


@router.put("/{campaign_id}")
async def update_campaign(
    campaign_id: int,
    request: CampaignUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Update campaign details (admin only)"""
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        # Only allow updates to draft campaigns
        if campaign.status != CampaignStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft campaigns can be updated"
            )
        
        # Update campaign fields
        update_data = request.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(campaign, field, value)
        
        campaign.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "status": "success",
            "message": "Campaign updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update campaign: {str(e)}"
        )


@router.post("/{campaign_id}/schedule")
async def schedule_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Schedule campaign for execution (admin only)"""
    try:
        result = CampaignService.schedule_campaign(db, campaign_id)
        
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
            detail=f"Failed to schedule campaign: {str(e)}"
        )


@router.post("/{campaign_id}/execute")
async def execute_campaign(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Execute campaign immediately (admin only)"""
    try:
        campaign_service = CampaignService()
        
        # Execute campaign in background
        background_tasks.add_task(
            campaign_service.execute_campaign,
            db,
            campaign_id
        )
        
        return {
            "status": "success",
            "message": "Campaign execution started in background"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute campaign: {str(e)}"
        )


@router.get("/{campaign_id}/analytics")
async def get_campaign_analytics(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get campaign analytics and performance metrics (admin only)"""
    try:
        result = CampaignService.get_campaign_analytics(db, campaign_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get campaign analytics: {str(e)}"
        )


@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Delete campaign (admin only)"""
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        # Only allow deletion of draft or completed campaigns
        if campaign.status in [CampaignStatus.RUNNING, CampaignStatus.SCHEDULED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete running or scheduled campaigns"
            )
        
        db.delete(campaign)
        db.commit()
        
        return {
            "status": "success",
            "message": "Campaign deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete campaign: {str(e)}"
        )


@router.get("/types/list")
async def list_campaign_types(
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get list of available campaign types (admin only)"""
    return {
        "status": "success",
        "campaign_types": [
            {
                "value": campaign_type.value,
                "label": campaign_type.value.replace('_', ' ').title()
            }
            for campaign_type in CampaignType
        ]
    }


@router.get("/statistics/overview")
async def get_campaign_statistics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get campaign statistics overview (admin only)"""
    try:
        from datetime import timedelta
        from sqlalchemy import func
        
        # Date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Campaign counts by status
        status_counts = {}
        for status in CampaignStatus:
            count = db.query(Campaign).filter(Campaign.status == status).count()
            status_counts[status.value] = count
        
        # Recent campaign performance
        recent_campaigns = db.query(Campaign).filter(
            Campaign.created_at >= start_date,
            Campaign.status == CampaignStatus.COMPLETED
        ).all()
        
        total_emails_sent = sum(c.emails_sent for c in recent_campaigns)
        total_emails_opened = sum(c.emails_opened for c in recent_campaigns)
        total_tokens_distributed = sum(c.tokens_distributed for c in recent_campaigns)
        
        avg_open_rate = (total_emails_opened / total_emails_sent * 100) if total_emails_sent > 0 else 0
        
        return {
            "status": "success",
            "statistics": {
                "period_days": days,
                "campaign_counts": status_counts,
                "performance_metrics": {
                    "total_campaigns": len(recent_campaigns),
                    "total_emails_sent": total_emails_sent,
                    "total_emails_opened": total_emails_opened,
                    "total_tokens_distributed": total_tokens_distributed,
                    "average_open_rate": round(avg_open_rate, 2)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get campaign statistics: {str(e)}"
        )