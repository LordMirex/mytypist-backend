"""
Partner Portal API Routes
Business partnership applications and management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel, validator, EmailStr

from database import get_db
from app.services.auth_service import AuthService
from app.services.partner_service import PartnerService, PartnerApplication, Partner, ApplicationStatus

router = APIRouter(prefix="/api/partners", tags=["partners"])


class PartnerApplicationRequest(BaseModel):
    """Partner application submission"""
    # Contact information
    company_name: str
    contact_person: str
    email: EmailStr
    phone: Optional[str] = None
    website: Optional[str] = None
    
    # Business details
    business_type: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    annual_revenue: Optional[str] = None
    
    # Partnership details
    partnership_type: str
    experience_level: Optional[str] = None
    target_market: Optional[str] = None
    marketing_strategy: Optional[str] = None
    
    # Application content
    motivation: str
    value_proposition: str
    technical_capabilities: Optional[str] = None
    previous_partnerships: Optional[str] = None
    
    # Additional
    referral_source: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None

    @validator('company_name')
    def validate_company_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Company name must be at least 2 characters")
        return v.strip()

    @validator('motivation')
    def validate_motivation(cls, v):
        if len(v.strip()) < 50:
            raise ValueError("Motivation must be at least 50 characters")
        return v.strip()

    @validator('value_proposition')
    def validate_value_proposition(cls, v):
        if len(v.strip()) < 50:
            raise ValueError("Value proposition must be at least 50 characters")
        return v.strip()


class ApplicationReviewRequest(BaseModel):
    """Application review by admin"""
    status: str
    review_notes: Optional[str] = None

    @validator('status')
    def validate_status(cls, v):
        try:
            ApplicationStatus(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid status: {v}")


class ReferralLinkRequest(BaseModel):
    """Generate referral link"""
    utm_campaign: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None


# Public endpoints
@router.post("/apply")
async def submit_application(
    request: PartnerApplicationRequest,
    db: Session = Depends(get_db)
):
    """Submit partner application"""
    try:
        application_data = request.dict()
        
        result = PartnerService.submit_application(application_data)
        
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
            detail=f"Failed to submit application: {str(e)}"
        )


@router.get("/application-status/{email}")
async def check_application_status(
    email: str,
    db: Session = Depends(get_db)
):
    """Check application status by email"""
    try:
        application = db.query(PartnerApplication).filter(
            PartnerApplication.email == email
        ).order_by(PartnerApplication.created_at.desc()).first()
        
        if not application:
            return {
                "status": "success",
                "has_application": False,
                "message": "No application found for this email"
            }
        
        return {
            "status": "success",
            "has_application": True,
            "application": {
                "id": application.id,
                "company_name": application.company_name,
                "status": application.status.value,
                "submitted_at": application.created_at.isoformat(),
                "reviewed_at": application.reviewed_at.isoformat() if application.reviewed_at else None
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check application status: {str(e)}"
        )


# Partner-only endpoints (requires partner authentication)
@router.get("/dashboard")
async def get_partner_dashboard(
    db: Session = Depends(get_db),
    # current_partner = Depends(AuthService.get_current_partner)  # Would need to implement this
):
    """Get partner dashboard data"""
    try:
        # For now, assume partner_id is passed or derived from auth
        # In production, this would come from authenticated partner user
        partner_id = 1  # This would come from current_partner.id
        
        result = PartnerService.get_partner_dashboard(db, partner_id)
        
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
            detail=f"Failed to get dashboard: {str(e)}"
        )


@router.post("/referral-link")
async def generate_referral_link(
    request: ReferralLinkRequest,
    db: Session = Depends(get_db)
    # current_partner = Depends(AuthService.get_current_partner)
):
    """Generate referral link for partner"""
    try:
        partner_id = 1  # This would come from current_partner.id
        campaign_data = request.dict(exclude_unset=True)
        
        result = PartnerService.generate_referral_link(db, partner_id, campaign_data)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
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
            detail=f"Failed to generate referral link: {str(e)}"
        )


# Admin endpoints
@router.get("/admin/applications")
async def list_applications(
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """List partner applications (admin only)"""
    try:
        query = db.query(PartnerApplication)
        
        if status_filter:
            query = query.filter(PartnerApplication.status == ApplicationStatus(status_filter))
        
        total = query.count()
        applications = query.order_by(
            PartnerApplication.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        application_list = []
        for app in applications:
            application_list.append({
                "id": app.id,
                "company_name": app.company_name,
                "contact_person": app.contact_person,
                "email": app.email,
                "partnership_type": app.partnership_type,
                "status": app.status.value,
                "created_at": app.created_at.isoformat(),
                "reviewed_at": app.reviewed_at.isoformat() if app.reviewed_at else None,
                "reviewer": app.reviewer.username if app.reviewer else None
            })
        
        return {
            "status": "success",
            "applications": application_list,
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
            detail=f"Failed to list applications: {str(e)}"
        )


@router.get("/admin/applications/{application_id}")
async def get_application_details(
    application_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get application details (admin only)"""
    try:
        application = db.query(PartnerApplication).filter(
            PartnerApplication.id == application_id
        ).first()
        
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        return {
            "status": "success",
            "application": {
                "id": application.id,
                "company_name": application.company_name,
                "contact_person": application.contact_person,
                "email": application.email,
                "phone": application.phone,
                "website": application.website,
                "business_type": application.business_type,
                "industry": application.industry,
                "company_size": application.company_size,
                "annual_revenue": application.annual_revenue,
                "partnership_type": application.partnership_type,
                "experience_level": application.experience_level,
                "target_market": application.target_market,
                "marketing_strategy": application.marketing_strategy,
                "motivation": application.motivation,
                "value_proposition": application.value_proposition,
                "technical_capabilities": application.technical_capabilities,
                "previous_partnerships": application.previous_partnerships,
                "referral_source": application.referral_source,
                "additional_info": application.additional_info,
                "status": application.status.value,
                "review_notes": application.review_notes,
                "created_at": application.created_at.isoformat(),
                "reviewed_at": application.reviewed_at.isoformat() if application.reviewed_at else None,
                "reviewer": application.reviewer.username if application.reviewer else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get application: {str(e)}"
        )


@router.put("/admin/applications/{application_id}/review")
async def review_application(
    application_id: int,
    request: ApplicationReviewRequest,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Review partner application (admin only)"""
    try:
        result = PartnerService.review_application(
            db=db,
            application_id=application_id,
            reviewer_id=current_user.id,
            status=ApplicationStatus(request.status),
            review_notes=request.review_notes
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "message": result["message"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to review application: {str(e)}"
        )


@router.get("/admin/partners")
async def list_partners(
    skip: int = 0,
    limit: int = 20,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """List active partners (admin only)"""
    try:
        query = db.query(Partner)
        
        if active_only:
            query = query.filter(Partner.is_active == True)
        
        total = query.count()
        partners = query.order_by(
            Partner.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        partner_list = []
        for partner in partners:
            partner_list.append({
                "id": partner.id,
                "partner_code": partner.partner_code,
                "company_name": partner.company_name,
                "contact_person": partner.contact_person,
                "email": partner.email,
                "partner_tier": partner.partner_tier.value,
                "commission_rate": partner.commission_rate,
                "is_active": partner.is_active,
                "total_referrals": partner.total_referrals,
                "successful_referrals": partner.successful_referrals,
                "commission_earned": partner.commission_earned,
                "commission_paid": partner.commission_paid,
                "last_activity": partner.last_activity.isoformat() if partner.last_activity else None,
                "created_at": partner.created_at.isoformat()
            })
        
        return {
            "status": "success",
            "partners": partner_list,
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
            detail=f"Failed to list partners: {str(e)}"
        )


@router.get("/admin/statistics")
async def get_partner_statistics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get partner program statistics (admin only)"""
    try:
        from datetime import timedelta
        from sqlalchemy import func
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Application statistics
        total_applications = db.query(PartnerApplication).count()
        pending_applications = db.query(PartnerApplication).filter(
            PartnerApplication.status == ApplicationStatus.PENDING
        ).count()
        
        approved_applications = db.query(PartnerApplication).filter(
            PartnerApplication.status == ApplicationStatus.APPROVED
        ).count()
        
        # Partner statistics
        total_partners = db.query(Partner).filter(Partner.is_active == True).count()
        
        # Recent activity
        recent_applications = db.query(PartnerApplication).filter(
            PartnerApplication.created_at >= start_date
        ).count()
        
        # Revenue metrics
        total_commission_earned = db.query(func.sum(Partner.commission_earned)).scalar() or 0
        total_commission_paid = db.query(func.sum(Partner.commission_paid)).scalar() or 0
        
        return {
            "status": "success",
            "statistics": {
                "period_days": days,
                "applications": {
                    "total": total_applications,
                    "pending": pending_applications,
                    "approved": approved_applications,
                    "recent": recent_applications
                },
                "partners": {
                    "total_active": total_partners
                },
                "revenue": {
                    "total_commission_earned": float(total_commission_earned),
                    "total_commission_paid": float(total_commission_paid),
                    "pending_commission": float(total_commission_earned - total_commission_paid)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )