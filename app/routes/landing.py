"""
Landing Page Routes
Seamless guest to registration workflow with free document creation
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from database import get_db
from app.models.user import User
from app.services.landing_page_service import LandingPageService
from app.services.audit_service import AuditService
from app.services.realtime_analytics_service import RealtimeAnalyticsService
from app.utils.security import get_current_active_user
from app.core.auth import get_optional_user
from app.schemas.analytics import EventType, EventData, PageViewData, TemplateInteractionData

logger = logging.getLogger(__name__)

router = APIRouter()


class TrackVisitRequest(BaseModel):
    """Request model for tracking landing page visit"""
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


class SearchTemplatesRequest(BaseModel):
    """Request model for searching templates"""
    search_term: str


class CreateFreeDocumentRequest(BaseModel):
    """Request model for creating free document"""
    template_id: int


class CompleteRegistrationRequest(BaseModel):
    """Request model for completing registration"""
    draft_id: int
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None


def get_session_info(request: Request) -> Dict[str, str]:
    """Extract session and device info from request"""
    return {
        "session_id": request.headers.get("x-session-id", f"guest_{int(datetime.utcnow().timestamp())}"),
        "device_fingerprint": request.headers.get("x-device-fingerprint"),
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent")
    }

async def track_page_interaction(request: Request, db: Session, interaction_data: Dict[str, Any]):
    """Helper to track page interactions in real-time"""
    try:
        session_info = get_session_info(request)
        event_data = {
            **interaction_data,
            **session_info
        }

        await RealtimeAnalyticsService.track_user_interaction(
            db=db,
            session_id=session_info["session_id"],
            event_type=event_data.pop("event_type"),
            event_data=event_data
        )
    except Exception as e:
        logger.error(f"Failed to track real-time interaction: {e}", exc_info=True)


@router.post("/track-visit", response_model=Dict[str, Any])
async def track_landing_visit(
    track_request: TrackVisitRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Track landing page visit for analytics"""
    try:
        session_info = get_session_info(request)

        utm_params = {
            "utm_source": track_request.utm_source,
            "utm_medium": track_request.utm_medium,
            "utm_campaign": track_request.utm_campaign
        }

        utm_params = {k: v for k, v in utm_params.items() if v is not None}

        result = LandingPageService.track_landing_visit(
            db=db,
            session_id=session_info["session_id"],
            request=request,
            utm_params=utm_params if utm_params else None,
            device_fingerprint=session_info["device_fingerprint"],
            ip_address=session_info["ip_address"],
            user_agent=session_info["user_agent"],
            referrer=track_request.referrer
        )

        # Track in real-time analytics
        await track_page_interaction(
            request=request,
            db=db,
            interaction_data={
                "event_type": EventType.PAGE_VIEW,
                "page": "landing",
                "referrer": track_request.referrer,
                "utm_params": utm_params,
                "entry_point": True
            }
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track visit: {str(e)}"
        )


@router.get("/templates", response_model=Dict[str, Any])
async def get_landing_templates(
    limit: int = Query(12, ge=1, le=50, description="Number of templates to return"),
    featured_only: bool = Query(False, description="Return only featured templates"),
    db: Session = Depends(get_db)
):
    """Get templates to display on landing page"""
    try:
        result = LandingPageService.get_landing_templates(
            db=db,
            limit=limit,
            featured_only=featured_only
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get landing templates: {str(e)}"
        )


@router.post("/search", response_model=Dict[str, Any])
async def search_landing_templates(
    search_request: SearchTemplatesRequest,
    request: Request,
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    db: Session = Depends(get_db)
):
    """Search templates on landing page"""
    try:
        session_info = get_session_info(request)

        result = LandingPageService.search_landing_templates(
            db=db,
            search_term=search_request.search_term,
            session_id=session_info["session_id"],
            limit=limit
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search templates: {str(e)}"
        )


@router.post("/template/{template_id}/view", response_model=Dict[str, Any])
async def track_template_view(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Track when a user views a template preview"""
    try:
        session_info = get_session_info(request)

        result = LandingPageService.track_template_view(
            db=db,
            template_id=template_id,
            session_id=session_info["session_id"]
        )

        # Track in real-time analytics
        await track_page_interaction(
            request=request,
            db=db,
            interaction_data={
                "event_type": EventType.TEMPLATE_INTERACTION,
                "template_id": template_id,
                "action": "view"
            }
        )

        return result

    except Exception as e:
        # Don't raise error for tracking failures
        return {"success": False, "error": "Tracking failed"}


@router.get("/template/{template_id}/preview", response_model=Dict[str, Any])
async def get_template_preview(
    template_id: int,
    request: Request,
    interaction_time: Optional[int] = Query(None, description="Time spent viewing template in seconds"),
    db: Session = Depends(get_db)
):
    """Get template preview with demo data for landing page"""
    try:
        session_info = get_session_info(request)

        # Track the view
        result = LandingPageService.track_template_view(
            db=db,
            template_id=template_id,
            session_id=session_info["session_id"]
        )

        # Track in real-time analytics with duration if provided
        interaction_data = {
            "event_type": EventType.TEMPLATE_INTERACTION,
            "template_id": template_id,
            "action": "preview"
        }
        if interaction_time is not None:
            interaction_data["duration"] = interaction_time

        await track_page_interaction(
            request=request,
            db=db,
            interaction_data=interaction_data
        )

        # Get template details
        from app.models.template import Template
        from app.services.landing_page_service import LandingPageTemplate

        template = db.query(Template).filter(Template.id == template_id).first()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )

        # Get landing page settings
        landing_template = db.query(LandingPageTemplate).filter(
            LandingPageTemplate.template_id == template_id,
            LandingPageTemplate.is_active == True
        ).first()

        # Get demo data
        demo_data = {}
        if landing_template and landing_template.demo_data:
            try:
                import json
                demo_data = json.loads(landing_template.demo_data)
            except:
                pass

        # Default demo data if none configured
        if not demo_data:
            demo_data = {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "company": "MyTypist Demo",
                "date": datetime.utcnow().strftime("%B %d, %Y"),
                "address": "123 Main Street, City, State 12345"
            }

        # Generate preview (this would use your document generation service)
        preview_result = LandingPageService._generate_template_preview(
            db, template, demo_data
        )

        return {
            "success": True,
            "template": {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "price_tokens": template.price or 0,
                "is_free": template.price == 0 or template.price is None,
                "estimated_time_minutes": LandingPageService._estimate_completion_time(template)
            },
            "preview": {
                "image_url": landing_template.preview_image_url if landing_template else f"/api/templates/{template_id}/preview-image",
                "demo_data": demo_data,
                "placeholders": preview_result.get("placeholders", []),
                "preview_content": preview_result.get("content", "Preview not available")
            },
            "call_to_action": {
                "primary_text": "Create This Document for FREE",
                "secondary_text": "No credit card required • Takes 2 minutes",
                "action_url": f"/api/landing/create-free/{template_id}"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get template preview: {str(e)}"
        )


@router.post("/create-free/{template_id}", response_model=Dict[str, Any])
async def create_free_document(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Start free document creation process"""
    try:
        session_info = get_session_info(request)

        result = LandingPageService.initiate_free_document_creation(
            db=db,
            template_id=template_id,
            session_id=session_info["session_id"],
            ip_address=session_info["ip_address"],
            device_fingerprint=session_info["device_fingerprint"],
            user_agent=session_info["user_agent"]
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create free document: {str(e)}"
        )


@router.post("/complete-registration", response_model=Dict[str, Any])
async def complete_guest_registration(
    registration_request: CompleteRegistrationRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Complete registration after document creation"""
    try:
        session_info = get_session_info(request)

        user_data = {
            "email": registration_request.email,
            "password": registration_request.password,
            "first_name": registration_request.first_name or "",
            "last_name": registration_request.last_name or "",
            "phone_number": registration_request.phone_number
        }

        device_info = {
            "device_fingerprint": session_info["device_fingerprint"],
            "ip_address": session_info["ip_address"],
            "user_agent": session_info["user_agent"]
        }

        result = LandingPageService.complete_guest_registration(
            db=db,
            draft_id=registration_request.draft_id,
            session_id=session_info["session_id"],
            user_data=user_data,
            device_info=device_info
        )

        if result["success"]:
            # Log successful conversion
            AuditService.log_activity(
                db,
                "LANDING_PAGE_CONVERSION",
                {
                    "draft_id": registration_request.draft_id,
                    "user_id": result["user_id"],
                    "session_id": session_info["session_id"]
                }
            )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete registration: {str(e)}"
        )


@router.get("/analytics", response_model=Dict[str, Any])
async def get_landing_analytics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get landing page analytics (admin only)"""
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        result = LandingPageService.get_landing_analytics(
            db=db,
            days=days
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics: {str(e)}"
        )


@router.get("/admin/templates", response_model=Dict[str, Any])
async def get_admin_landing_templates(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get landing page template configuration (admin only)"""
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        from app.services.landing_page_service import LandingPageTemplate
        from app.models.template import Template

        # Get all landing page templates
        landing_templates = db.query(LandingPageTemplate).order_by(
            LandingPageTemplate.display_order
        ).all()

        templates_data = []
        for lt in landing_templates:
            template = db.query(Template).filter(Template.id == lt.template_id).first()
            if template:
                templates_data.append({
                    "landing_template_id": lt.id,
                    "template_id": lt.template_id,
                    "template_name": template.name,
                    "landing_title": lt.landing_title,
                    "landing_description": lt.landing_description,
                    "display_order": lt.display_order,
                    "is_featured": lt.is_featured,
                    "is_active": lt.is_active,
                    "views_count": lt.views_count,
                    "conversions_count": lt.conversions_count,
                    "conversion_rate": round((lt.conversions_count / max(lt.views_count, 1)) * 100, 1),
                    "preview_image_url": lt.preview_image_url,
                    "has_demo_data": bool(lt.demo_data)
                })

        return {
            "success": True,
            "templates": templates_data,
            "total_count": len(templates_data)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get admin templates: {str(e)}"
        )


@router.post("/admin/templates/{template_id}/configure", response_model=Dict[str, Any])
async def configure_landing_template(
    template_id: int,
    config_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Configure template for landing page display (admin only)"""
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        from app.services.landing_page_service import LandingPageTemplate
        import json

        # Get or create landing template
        landing_template = db.query(LandingPageTemplate).filter(
            LandingPageTemplate.template_id == template_id
        ).first()

        if not landing_template:
            landing_template = LandingPageTemplate(template_id=template_id)
            db.add(landing_template)

        # Update configuration
        if "landing_title" in config_data:
            landing_template.landing_title = config_data["landing_title"]

        if "landing_description" in config_data:
            landing_template.landing_description = config_data["landing_description"]

        if "display_order" in config_data:
            landing_template.display_order = config_data["display_order"]

        if "is_featured" in config_data:
            landing_template.is_featured = config_data["is_featured"]

        if "is_active" in config_data:
            landing_template.is_active = config_data["is_active"]

        if "preview_image_url" in config_data:
            landing_template.preview_image_url = config_data["preview_image_url"]

        if "demo_data" in config_data:
            landing_template.demo_data = json.dumps(config_data["demo_data"])

        landing_template.updated_at = datetime.utcnow()
        db.commit()

        # Log configuration change
        AuditService.log_user_activity(
            db,
            current_user.id,
            "LANDING_TEMPLATE_CONFIGURED",
            {
                "template_id": template_id,
                "landing_template_id": landing_template.id,
                "changes": list(config_data.keys())
            }
        )

        return {
            "success": True,
            "landing_template_id": landing_template.id,
            "message": "Landing page template configured successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure template: {str(e)}"
        )


@router.get("/conversion-funnel", response_model=Dict[str, Any])
async def get_conversion_funnel(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get conversion funnel analytics (admin only)"""
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        from datetime import datetime, timedelta
        from app.services.landing_page_service import LandingPageVisit
        from sqlalchemy import func

        start_date = datetime.utcnow() - timedelta(days=days)

        # Funnel stages
        total_visits = db.query(LandingPageVisit).filter(
            LandingPageVisit.created_at >= start_date
        ).count()

        template_views = db.query(LandingPageVisit).filter(
            LandingPageVisit.created_at >= start_date,
            LandingPageVisit.templates_viewed_count > 0
        ).count()

        document_creations = db.query(LandingPageVisit).filter(
            LandingPageVisit.created_at >= start_date,
            LandingPageVisit.created_document == True
        ).count()

        registrations = db.query(LandingPageVisit).filter(
            LandingPageVisit.created_at >= start_date,
            LandingPageVisit.registered == True
        ).count()

        downloads = db.query(LandingPageVisit).filter(
            LandingPageVisit.created_at >= start_date,
            LandingPageVisit.downloaded_document == True
        ).count()

        # Calculate conversion rates
        funnel_data = [
            {
                "stage": "Landing Page Visit",
                "count": total_visits,
                "percentage": 100.0,
                "conversion_rate": 100.0
            },
            {
                "stage": "Template Preview",
                "count": template_views,
                "percentage": round((template_views / max(total_visits, 1)) * 100, 1),
                "conversion_rate": round((template_views / max(total_visits, 1)) * 100, 1)
            },
            {
                "stage": "Document Creation Started",
                "count": document_creations,
                "percentage": round((document_creations / max(total_visits, 1)) * 100, 1),
                "conversion_rate": round((document_creations / max(template_views, 1)) * 100, 1)
            },
            {
                "stage": "Registration Completed",
                "count": registrations,
                "percentage": round((registrations / max(total_visits, 1)) * 100, 1),
                "conversion_rate": round((registrations / max(document_creations, 1)) * 100, 1)
            },
            {
                "stage": "Document Downloaded",
                "count": downloads,
                "percentage": round((downloads / max(total_visits, 1)) * 100, 1),
                "conversion_rate": round((downloads / max(registrations, 1)) * 100, 1)
            }
        ]

        return {
            "success": True,
            "period_days": days,
            "funnel": funnel_data,
            "overall_conversion_rate": round((registrations / max(total_visits, 1)) * 100, 1),
            "completion_rate": round((downloads / max(registrations, 1)) * 100, 1)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversion funnel: {str(e)}"
        )


# Helper function to add to LandingPageService
def _generate_template_preview(db: Session, template, demo_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate secure template preview with demo data and watermark"""
    try:
        # Get document service and cache service
        from app.services.document_service import DocumentService
        from app.services.cache_service import CacheService
        from app.services.thumbnail_service import ThumbnailService

        # Try to get from cache first
        cache_key = f"preview:{template.id}:{hash(frozenset(demo_data.items()))}"
        cached_preview = CacheService.get(cache_key)
        if cached_preview:
            return cached_preview

        # Extract placeholders with validation and sanitization
        placeholders = DocumentService.extract_template_placeholders(
            template_file=template.file_path,
            validate=True,
            sanitize=True
        )

        # Enhance placeholders with smart suggestions and validation
        enhanced_placeholders = []
        for placeholder in placeholders:
            placeholder_data = {
                "name": placeholder["name"],
                "type": placeholder["type"],
                "label": placeholder.get("label", placeholder["name"].title()),
                "required": placeholder.get("required", True),
                "demo_value": demo_data.get(placeholder["name"], DocumentService.get_default_value(placeholder["type"])),
                "validation": DocumentService.get_placeholder_validation(placeholder["type"]),
                "suggestions": DocumentService.get_placeholder_suggestions(placeholder["name"], placeholder["type"]),
                "auto_format": True,
                "help_text": placeholder.get("help_text"),
                "examples": DocumentService.get_placeholder_examples(placeholder["name"], placeholder["type"]),
                "max_length": placeholder.get("max_length"),
                "pattern": placeholder.get("pattern"),
            }

        return {
            "success": True,
            "placeholders": placeholders,
            "content": f"Preview of {template.name} with demo data",
            "estimated_fields": len(placeholders)
        }

    except Exception as e:
        logger.error(f"Failed to generate template preview: {e}")
        return {
            "success": False,
            "placeholders": [],
            "content": "Preview not available"
        }

# Add the helper function to the service
LandingPageService._generate_template_preview = staticmethod(_generate_template_preview)
