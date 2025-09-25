"""
Feedback Routes - User feedback collection and management
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from database import get_db
from app.services.feedback_service import (
    FeedbackService, FeedbackCategory, FeedbackPriority, 
    FeedbackStatus, Feedback
)
from app.models.user import User
from app.utils.security import get_current_user, get_current_active_user
# from app.middleware.rate_limit import rate_limit  # Not available

router = APIRouter()

class FeedbackCreate(BaseModel):
    """Feedback creation schema"""
    category: FeedbackCategory
    subject: str = Field(..., min_length=5, max_length=200)
    message: str = Field(..., min_length=10, max_length=2000)
    
    # For anonymous feedback
    contact_email: Optional[EmailStr] = None
    contact_name: Optional[str] = Field(None, max_length=100)
    
    # Optional context
    page_url: Optional[str] = Field(None, max_length=500)
    requires_response: bool = True
    priority: FeedbackPriority = FeedbackPriority.MEDIUM

class FeedbackResponse(BaseModel):
    """Feedback response schema"""
    id: int
    feedback_id: str
    category: FeedbackCategory
    priority: FeedbackPriority
    status: FeedbackStatus
    subject: str
    message: str
    contact_email: Optional[str] = None
    contact_name: Optional[str] = None
    page_url: Optional[str] = None
    is_anonymous: bool
    requires_response: bool
    created_at: str
    updated_at: str
    resolved_at: Optional[str] = None
    
    class Config:
        from_attributes = True

class FeedbackUpdate(BaseModel):
    """Admin feedback update schema"""
    status: Optional[FeedbackStatus] = None
    priority: Optional[FeedbackPriority] = None
    admin_notes: Optional[str] = Field(None, max_length=1000)
    resolution: Optional[str] = Field(None, max_length=1000)
    assigned_to: Optional[int] = None

class FeedbackAnalytics(BaseModel):
    """Feedback analytics schema"""
    total_feedback: int
    pending_feedback: int
    resolved_feedback: int
    avg_resolution_hours: float
    resolution_rate: float
    category_breakdown: Dict[str, int]
    priority_breakdown: Dict[str, int]
    status_breakdown: Dict[str, int]

@router.post("/submit", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
# @rate_limit(max_requests=5, window_seconds=300)  # Rate limiting handled by middleware
async def submit_feedback(
    feedback_data: FeedbackCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Submit new feedback"""
    
    try:
        # Extract browser information
        user_agent = request.headers.get("user-agent")
        
        # For anonymous feedback, email is required
        if not current_user and not feedback_data.contact_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required for anonymous feedback"
            )
        
        # Create feedback
        feedback = FeedbackService.create_feedback(
            db=db,
            category=feedback_data.category,
            subject=feedback_data.subject,
            message=feedback_data.message,
            user_id=current_user.id if current_user else None,
            contact_email=feedback_data.contact_email,
            contact_name=feedback_data.contact_name,
            page_url=feedback_data.page_url,
            user_agent=user_agent,
            priority=feedback_data.priority,
            requires_response=feedback_data.requires_response
        )
        
        return {
            "success": True,
            "message": "Feedback submitted successfully",
            "feedback_id": feedback.feedback_id,
            "estimated_response_time": "1-2 business days" if feedback.requires_response else None,
            "status": feedback.status.value,
            "priority": feedback.priority.value
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )

@router.get("/my-feedback", response_model=Dict[str, Any])
async def get_my_feedback(
    page: int = 1,
    per_page: int = 10,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's feedback history"""
    
    if per_page > 50:
        per_page = 50
    
    feedbacks, total = FeedbackService.get_user_feedback_history(
        db=db,
        user_id=current_user.id,
        page=page,
        per_page=per_page
    )
    
    return {
        "feedbacks": [
            {
                "feedback_id": fb.feedback_id,
                "category": fb.category.value,
                "subject": fb.subject,
                "status": fb.status.value,
                "priority": fb.priority.value,
                "created_at": fb.created_at.isoformat(),
                "resolved_at": fb.resolved_at.isoformat() if fb.resolved_at else None,
                "resolution": fb.resolution
            }
            for fb in feedbacks
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }

@router.get("/track/{feedback_id}", response_model=Dict[str, Any])
async def track_feedback(
    feedback_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Track feedback status by ID"""
    
    feedback = FeedbackService.get_feedback_by_id(db, feedback_id)
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found"
        )
    
    # Check permission (user can see their own feedback or anonymous with correct ID)
    if feedback.user_id and current_user and feedback.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own feedback"
        )
    
    return {
        "feedback_id": feedback.feedback_id,
        "category": feedback.category.value,
        "subject": feedback.subject,
        "status": feedback.status.value,
        "priority": feedback.priority.value,
        "created_at": feedback.created_at.isoformat(),
        "updated_at": feedback.updated_at.isoformat(),
        "resolved_at": feedback.resolved_at.isoformat() if feedback.resolved_at else None,
        "resolution": feedback.resolution,
        "estimated_response_time": "1-2 business days" if feedback.requires_response and feedback.status == FeedbackStatus.PENDING else None
    }

# Admin endpoints (require admin role)
@router.get("/admin/list", response_model=Dict[str, Any])
async def admin_get_feedback_list(
    page: int = 1,
    per_page: int = 20,
    category: Optional[FeedbackCategory] = None,
    status: Optional[FeedbackStatus] = None,
    priority: Optional[FeedbackPriority] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get feedback list for admin review"""
    
    # Check admin permission
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    if per_page > 100:
        per_page = 100
    
    feedbacks, total = FeedbackService.get_feedback_list(
        db=db,
        page=page,
        per_page=per_page,
        category=category,
        status=status,
        priority=priority,
        search_query=search
    )
    
    return {
        "feedbacks": [
            {
                "id": fb.id,
                "feedback_id": fb.feedback_id,
                "category": fb.category.value,
                "priority": fb.priority.value,
                "status": fb.status.value,
                "subject": fb.subject,
                "message": fb.message[:200] + "..." if len(fb.message) > 200 else fb.message,
                "contact_email": fb.contact_email,
                "contact_name": fb.contact_name,
                "user_id": fb.user_id,
                "is_anonymous": fb.is_anonymous,
                "requires_response": fb.requires_response,
                "created_at": fb.created_at.isoformat(),
                "updated_at": fb.updated_at.isoformat(),
                "admin_notes": fb.admin_notes,
                "assigned_to": fb.assigned_to
            }
            for fb in feedbacks
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }

@router.put("/admin/{feedback_id}", response_model=Dict[str, Any])
async def admin_update_feedback(
    feedback_id: str,
    update_data: FeedbackUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update feedback (admin only)"""
    
    # Check admin permission
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    feedback = FeedbackService.get_feedback_by_id(db, feedback_id)
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found"
        )
    
    # Update feedback
    updated_feedback = FeedbackService.update_feedback_status(
        db=db,
        feedback=feedback,
        new_status=update_data.status or feedback.status,
        admin_notes=update_data.admin_notes,
        resolution=update_data.resolution,
        assigned_to=update_data.assigned_to or feedback.assigned_to
    )
    
    return {
        "success": True,
        "message": "Feedback updated successfully",
        "feedback": {
            "feedback_id": updated_feedback.feedback_id,
            "status": updated_feedback.status.value,
            "admin_notes": updated_feedback.admin_notes,
            "resolution": updated_feedback.resolution,
            "updated_at": updated_feedback.updated_at.isoformat(),
            "resolved_at": updated_feedback.resolved_at.isoformat() if updated_feedback.resolved_at else None
        }
    }

@router.get("/admin/analytics", response_model=FeedbackAnalytics)
async def get_feedback_analytics(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get feedback analytics (admin only)"""
    
    # Check admin permission
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    analytics = FeedbackService.get_feedback_analytics(db, days=days)
    
    return FeedbackAnalytics(**analytics)

@router.get("/admin/urgent", response_model=Dict[str, Any])
async def get_urgent_feedback(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get urgent feedback requiring immediate attention"""
    
    # Check admin permission
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    urgent_feedback = FeedbackService.get_urgent_feedback(db)
    
    return {
        "urgent_feedback": [
            {
                "feedback_id": fb.feedback_id,
                "category": fb.category.value,
                "priority": fb.priority.value,
                "subject": fb.subject,
                "created_at": fb.created_at.isoformat(),
                "requires_response": fb.requires_response,
                "is_anonymous": fb.is_anonymous,
                "contact_email": fb.contact_email
            }
            for fb in urgent_feedback
        ],
        "count": len(urgent_feedback)
    }

@router.post("/admin/{feedback_id}/spam", response_model=Dict[str, Any])
async def mark_feedback_as_spam(
    feedback_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Mark feedback as spam (admin only)"""
    
    # Check admin permission
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    feedback = FeedbackService.get_feedback_by_id(db, feedback_id)
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found"
        )
    
    spam_feedback = FeedbackService.mark_as_spam(db, feedback)
    
    return {
        "success": True,
        "message": "Feedback marked as spam",
        "feedback_id": spam_feedback.feedback_id,
        "status": spam_feedback.status.value
    }

@router.get("/categories", response_model=Dict[str, Any])
async def get_feedback_categories():
    """Get available feedback categories"""
    
    return {
        "categories": [
            {
                "value": category.value,
                "label": category.value.replace("_", " ").title(),
                "description": {
                    FeedbackCategory.BUG_REPORT: "Report technical issues or bugs",
                    FeedbackCategory.FEATURE_REQUEST: "Suggest new features or improvements",
                    FeedbackCategory.GENERAL_FEEDBACK: "General comments or feedback",
                    FeedbackCategory.COMPLAINT: "Report problems or complaints",
                    FeedbackCategory.COMPLIMENT: "Share positive feedback or compliments",
                    FeedbackCategory.SUGGESTION: "Suggest improvements or ideas"
                }[category]
            }
            for category in FeedbackCategory
        ]
    }