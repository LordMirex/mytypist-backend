"""
Partner Portal for Business Applications
Enterprise partner management with applications and referral tracking
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, Enum, JSON, func
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum

from database import Base
from app.models.user import User

logger = logging.getLogger(__name__)


class ApplicationStatus(str, PyEnum):
    """Partner application status"""
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class PartnerTier(str, PyEnum):
    """Partner tier levels"""
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class PartnerApplication(Base):
    """Partner application submissions"""
    __tablename__ = "partner_applications"

    id = Column(Integer, primary_key=True, index=True)
    
    # Contact information
    company_name = Column(String(200), nullable=False, index=True)
    contact_person = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    website = Column(String(500), nullable=True)
    
    # Business details
    business_type = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    company_size = Column(String(50), nullable=True)  # 1-10, 11-50, 51-200, 200+
    annual_revenue = Column(String(50), nullable=True)
    
    # Partnership details
    partnership_type = Column(String(100), nullable=False)  # reseller, integrator, referral
    experience_level = Column(String(50), nullable=True)
    target_market = Column(Text, nullable=True)
    marketing_strategy = Column(Text, nullable=True)
    
    # Application content
    motivation = Column(Text, nullable=False)  # Why they want to partner
    value_proposition = Column(Text, nullable=False)  # What they bring
    technical_capabilities = Column(Text, nullable=True)
    previous_partnerships = Column(Text, nullable=True)
    
    # Status and review
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.PENDING, index=True)
    reviewer_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Additional information
    referral_source = Column(String(200), nullable=True)
    additional_info = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    reviewer = relationship("User")


class Partner(Base):
    """Approved partners"""
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey('partner_applications.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Partner user account
    
    # Partner details
    partner_code = Column(String(50), nullable=False, unique=True, index=True)
    company_name = Column(String(200), nullable=False)
    contact_person = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    
    # Partnership configuration
    partner_tier = Column(Enum(PartnerTier), default=PartnerTier.BRONZE, index=True)
    commission_rate = Column(Float, default=10.0)  # Percentage
    referral_bonus = Column(Float, default=25.0)  # Fixed amount
    custom_pricing_enabled = Column(Boolean, default=False)
    
    # Status and limits
    is_active = Column(Boolean, default=True, index=True)
    max_monthly_volume = Column(Integer, nullable=True)
    credit_limit = Column(Float, default=1000.0)
    
    # Performance metrics
    total_referrals = Column(Integer, default=0)
    successful_referrals = Column(Integer, default=0)
    total_revenue_generated = Column(Float, default=0.0)
    commission_earned = Column(Float, default=0.0)
    commission_paid = Column(Float, default=0.0)
    
    # Account management
    account_manager_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    onboarding_completed = Column(Boolean, default=False)
    last_activity = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    application = relationship("PartnerApplication")
    user = relationship("User", foreign_keys=[user_id])
    account_manager = relationship("User", foreign_keys=[account_manager_id])


class PartnerReferral(Base):
    """Partner referral tracking"""
    __tablename__ = "partner_referrals"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey('partners.id'), nullable=False, index=True)
    
    # Referral details
    referral_code = Column(String(50), nullable=False, unique=True, index=True)
    referred_email = Column(String(255), nullable=False, index=True)
    referred_name = Column(String(200), nullable=True)
    referred_company = Column(String(200), nullable=True)
    
    # Conversion tracking
    signed_up = Column(Boolean, default=False)
    signed_up_at = Column(DateTime, nullable=True)
    first_payment = Column(Boolean, default=False)
    first_payment_at = Column(DateTime, nullable=True)
    first_payment_amount = Column(Float, default=0.0)
    
    # Commission calculation
    commission_rate = Column(Float, nullable=False)  # Rate at time of referral
    commission_amount = Column(Float, default=0.0)
    commission_paid = Column(Boolean, default=False)
    commission_paid_at = Column(DateTime, nullable=True)
    
    # Tracking metadata
    referral_source = Column(String(200), nullable=True)  # Website, email, etc.
    utm_campaign = Column(String(200), nullable=True)
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    conversion_at = Column(DateTime, nullable=True)
    
    # Relationships
    partner = relationship("Partner", backref="referrals")


class PartnerActivity(Base):
    """Partner activity and engagement tracking"""
    __tablename__ = "partner_activities"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey('partners.id'), nullable=False, index=True)
    
    # Activity details
    activity_type = Column(String(50), nullable=False, index=True)  # login, referral, training, etc.
    activity_description = Column(String(500), nullable=False)
    activity_data = Column(JSON, nullable=True)
    
    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    partner = relationship("Partner", backref="activities")


class PartnerService:
    """Service for managing partner portal"""

    @staticmethod
    def submit_application(application_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit partner application"""
        try:
            from database import get_db
            db = next(get_db())
            
            # Validate required fields
            required_fields = ['company_name', 'contact_person', 'email', 'partnership_type', 'motivation', 'value_proposition']
            for field in required_fields:
                if not application_data.get(field):
                    return {"success": False, "message": f"Missing required field: {field}"}
            
            # Check for duplicate applications
            existing = db.query(PartnerApplication).filter(
                PartnerApplication.email == application_data['email'],
                PartnerApplication.status.in_([ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW, ApplicationStatus.APPROVED])
            ).first()
            
            if existing:
                return {"success": False, "message": "Application already exists for this email"}
            
            # Create application
            application = PartnerApplication(
                company_name=application_data['company_name'],
                contact_person=application_data['contact_person'],
                email=application_data['email'],
                phone=application_data.get('phone'),
                website=application_data.get('website'),
                business_type=application_data.get('business_type'),
                industry=application_data.get('industry'),
                company_size=application_data.get('company_size'),
                annual_revenue=application_data.get('annual_revenue'),
                partnership_type=application_data['partnership_type'],
                experience_level=application_data.get('experience_level'),
                target_market=application_data.get('target_market'),
                marketing_strategy=application_data.get('marketing_strategy'),
                motivation=application_data['motivation'],
                value_proposition=application_data['value_proposition'],
                technical_capabilities=application_data.get('technical_capabilities'),
                previous_partnerships=application_data.get('previous_partnerships'),
                referral_source=application_data.get('referral_source'),
                additional_info=application_data.get('additional_info')
            )
            
            db.add(application)
            db.commit()
            db.refresh(application)
            
            # Send notification email to admin (would integrate with email service)
            logger.info(f"New partner application submitted: {application.id}")
            
            return {
                "success": True,
                "application_id": application.id,
                "message": "Application submitted successfully. We'll review it within 5 business days."
            }
            
        except Exception as e:
            logger.error(f"Failed to submit partner application: {e}")
            return {"success": False, "message": "Failed to submit application"}

    @staticmethod
    def review_application(
        db: Session,
        application_id: int,
        reviewer_id: int,
        status: ApplicationStatus,
        review_notes: str = None
    ) -> Dict[str, Any]:
        """Review partner application"""
        try:
            application = db.query(PartnerApplication).filter(
                PartnerApplication.id == application_id
            ).first()
            
            if not application:
                return {"success": False, "message": "Application not found"}
            
            application.status = status
            application.reviewer_id = reviewer_id
            application.review_notes = review_notes
            application.reviewed_at = datetime.utcnow()
            
            # If approved, create partner record
            if status == ApplicationStatus.APPROVED:
                partner_code = PartnerService._generate_partner_code(application.company_name)
                
                partner = Partner(
                    application_id=application.id,
                    partner_code=partner_code,
                    company_name=application.company_name,
                    contact_person=application.contact_person,
                    email=application.email,
                    phone=application.phone
                )
                
                db.add(partner)
            
            db.commit()
            
            return {"success": True, "message": f"Application {status.value} successfully"}
            
        except Exception as e:
            logger.error(f"Failed to review application: {e}")
            db.rollback()
            return {"success": False, "message": "Failed to review application"}

    @staticmethod
    def get_partner_dashboard(db: Session, partner_id: int) -> Dict[str, Any]:
        """Get partner dashboard data"""
        try:
            partner = db.query(Partner).filter(Partner.id == partner_id).first()
            if not partner:
                return {"success": False, "message": "Partner not found"}
            
            # Get recent referrals
            recent_referrals = db.query(PartnerReferral).filter(
                PartnerReferral.partner_id == partner_id
            ).order_by(PartnerReferral.created_at.desc()).limit(10).all()
            
            # Calculate this month's metrics
            now = datetime.utcnow()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            monthly_referrals = db.query(PartnerReferral).filter(
                PartnerReferral.partner_id == partner_id,
                PartnerReferral.created_at >= month_start
            ).count()
            
            monthly_conversions = db.query(PartnerReferral).filter(
                PartnerReferral.partner_id == partner_id,
                PartnerReferral.signed_up == True,
                PartnerReferral.signed_up_at >= month_start
            ).count()
            
            from sqlalchemy import func
            monthly_commission = db.query(func.sum(PartnerReferral.commission_amount)).filter(
                PartnerReferral.partner_id == partner_id,
                PartnerReferral.first_payment_at >= month_start
            ).scalar() or 0
            
            return {
                "success": True,
                "partner": {
                    "id": partner.id,
                    "partner_code": partner.partner_code,
                    "company_name": partner.company_name,
                    "partner_tier": partner.partner_tier.value,
                    "commission_rate": partner.commission_rate,
                    "is_active": partner.is_active,
                    "total_referrals": partner.total_referrals,
                    "successful_referrals": partner.successful_referrals,
                    "commission_earned": partner.commission_earned,
                    "commission_paid": partner.commission_paid,
                    "pending_commission": partner.commission_earned - partner.commission_paid
                },
                "monthly_metrics": {
                    "referrals": monthly_referrals,
                    "conversions": monthly_conversions,
                    "commission": float(monthly_commission),
                    "conversion_rate": round((monthly_conversions / monthly_referrals * 100) if monthly_referrals > 0 else 0, 2)
                },
                "recent_referrals": [
                    {
                        "id": ref.id,
                        "referral_code": ref.referral_code,
                        "referred_email": ref.referred_email,
                        "referred_name": ref.referred_name,
                        "signed_up": ref.signed_up,
                        "first_payment": ref.first_payment,
                        "commission_amount": ref.commission_amount,
                        "created_at": ref.created_at.isoformat()
                    }
                    for ref in recent_referrals
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get partner dashboard: {e}")
            return {"success": False, "message": "Failed to get dashboard data"}

    @staticmethod
    def generate_referral_link(db: Session, partner_id: int, campaign_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate referral link for partner"""
        try:
            partner = db.query(Partner).filter(Partner.id == partner_id).first()
            if not partner:
                return {"success": False, "message": "Partner not found"}
            
            import secrets
            referral_code = f"{partner.partner_code}_{secrets.token_urlsafe(8)}"
            
            # Create referral record
            referral = PartnerReferral(
                partner_id=partner_id,
                referral_code=referral_code,
                referred_email="",  # Will be filled when someone uses the link
                commission_rate=partner.commission_rate,
                utm_campaign=campaign_data.get('utm_campaign') if campaign_data else None,
                utm_source=campaign_data.get('utm_source') if campaign_data else None,
                utm_medium=campaign_data.get('utm_medium') if campaign_data else None
            )
            
            # Don't save until someone actually uses it
            from config import settings
            referral_link = f"{settings.FRONTEND_URL}/signup?ref={referral_code}"
            
            return {
                "success": True,
                "referral_code": referral_code,
                "referral_link": referral_link,
                "commission_rate": partner.commission_rate
            }
            
        except Exception as e:
            logger.error(f"Failed to generate referral link: {e}")
            return {"success": False, "message": "Failed to generate referral link"}

    @staticmethod
    def track_referral_conversion(db: Session, referral_code: str, user_data: Dict[str, Any]) -> bool:
        """Track referral conversion when user signs up"""
        try:
            # This would be called when a user signs up with a referral code
            partner = db.query(Partner).join(PartnerReferral).filter(
                PartnerReferral.referral_code == referral_code
            ).first()
            
            if not partner:
                return False
            
            # Create or update referral record
            referral = db.query(PartnerReferral).filter(
                PartnerReferral.referral_code == referral_code
            ).first()
            
            if not referral:
                referral = PartnerReferral(
                    partner_id=partner.id,
                    referral_code=referral_code,
                    commission_rate=partner.commission_rate
                )
                db.add(referral)
            
            # Update referral with user data
            referral.referred_email = user_data.get('email', '')
            referral.referred_name = user_data.get('name', '')
            referral.referred_company = user_data.get('company', '')
            referral.signed_up = True
            referral.signed_up_at = datetime.utcnow()
            
            # Update partner stats
            partner.total_referrals += 1
            partner.last_activity = datetime.utcnow()
            
            db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to track referral conversion: {e}")
            return False

    @staticmethod
    def _generate_partner_code(company_name: str) -> str:
        """Generate unique partner code"""
        import re
        import secrets
        
        # Clean company name for code
        clean_name = re.sub(r'[^a-zA-Z0-9]', '', company_name.upper())[:6]
        random_suffix = secrets.token_hex(3).upper()
        
        return f"PTR_{clean_name}_{random_suffix}"