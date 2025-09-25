"""
Feedback Service - User feedback collection and management
Handles feedback submission, categorization, and admin review workflows
"""

import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func

from app.models.user import User
from config import settings
from app.services.email_service import email_service

logger = logging.getLogger(__name__)

# Create feedback table model
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from database import Base
import enum

class FeedbackCategory(str, enum.Enum):
    """Feedback categories"""
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    GENERAL_FEEDBACK = "general_feedback"
    COMPLAINT = "complaint"
    COMPLIMENT = "compliment"
    SUGGESTION = "suggestion"

class FeedbackPriority(str, enum.Enum):
    """Feedback priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class FeedbackStatus(str, enum.Enum):
    """Feedback status"""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ARCHIVED = "archived"

class Feedback(Base):
    """Feedback model"""
    __tablename__ = "feedbacks"
    
    id = Column(Integer, primary_key=True, index=True)
    feedback_id = Column(String, unique=True, index=True)  # Public facing ID
    user_id = Column(Integer, nullable=True)  # Nullable for anonymous feedback
    
    # Feedback content
    category = Column(SQLEnum(FeedbackCategory), nullable=False)
    priority = Column(SQLEnum(FeedbackPriority), default=FeedbackPriority.MEDIUM)
    status = Column(SQLEnum(FeedbackStatus), default=FeedbackStatus.PENDING)
    
    subject = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    
    # Contact information (for anonymous feedback)
    contact_email = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)
    
    # Browser/device information
    user_agent = Column(String, nullable=True)
    page_url = Column(String, nullable=True)
    browser_info = Column(Text, nullable=True)  # JSON string
    
    # Admin fields
    admin_notes = Column(Text, nullable=True)
    assigned_to = Column(Integer, nullable=True)  # Admin user ID
    resolution = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    # Flags
    is_anonymous = Column(Boolean, default=False)
    requires_response = Column(Boolean, default=True)
    is_spam = Column(Boolean, default=False)

class FeedbackService:
    """Comprehensive feedback management service"""
    
    @staticmethod
    def create_feedback(
        db: Session,
        category: FeedbackCategory,
        subject: str,
        message: str,
        user_id: Optional[int] = None,
        contact_email: Optional[str] = None,
        contact_name: Optional[str] = None,
        page_url: Optional[str] = None,
        user_agent: Optional[str] = None,
        browser_info: Optional[Dict[str, Any]] = None,
        priority: FeedbackPriority = FeedbackPriority.MEDIUM,
        requires_response: bool = True
    ) -> Feedback:
        """Create new feedback entry"""
        
        # Generate unique feedback ID
        feedback_id = f"FB-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # Auto-detect priority based on category and keywords
        detected_priority = FeedbackService._detect_priority(category, subject, message)
        if detected_priority and priority == FeedbackPriority.MEDIUM:  # Only upgrade if default
            priority = detected_priority
        
        feedback = Feedback(
            feedback_id=feedback_id,
            user_id=user_id,
            category=category,
            priority=priority,
            subject=subject,
            message=message,
            contact_email=contact_email,
            contact_name=contact_name,
            page_url=page_url,
            user_agent=user_agent,
            browser_info=str(browser_info) if browser_info else None,
            is_anonymous=user_id is None,
            requires_response=requires_response
        )
        
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        
        # Send acknowledgment email if email provided
        if contact_email or user_id:
            try:
                # Get user details if logged in
                user_name = contact_name or "User"
                user_email = contact_email
                
                if user_id:
                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        user_name = user.first_name or user.username or "User"
                        user_email = user.email
                
                if user_email:
                    # Send acknowledgment email asynchronously
                    import asyncio
                    asyncio.create_task(
                        email_service.send_feedback_acknowledgment(
                            user_email, user_name, feedback_id
                        )
                    )
            except Exception as e:
                logger.error(f"Failed to send feedback acknowledgment email: {e}")
        
        # Log for admin attention if high priority
        if priority in [FeedbackPriority.HIGH, FeedbackPriority.CRITICAL]:
            logger.warning(f"High priority feedback received: {feedback_id} - {subject}")
        
        return feedback
    
    @staticmethod
    def _detect_priority(category: FeedbackCategory, subject: str, message: str) -> Optional[FeedbackPriority]:
        """Auto-detect feedback priority based on content"""
        
        text_content = f"{subject} {message}".lower()
        
        # Critical keywords
        critical_keywords = [
            'critical', 'urgent', 'emergency', 'broken', 'not working', 'error',
            'crash', 'bug', 'issue', 'problem', 'failed', 'unable to', 'cannot'
        ]
        
        # High priority keywords
        high_keywords = [
            'important', 'asap', 'quickly', 'soon', 'help', 'support needed',
            'frustrated', 'disappointed', 'angry', 'unacceptable'
        ]
        
        if category == FeedbackCategory.BUG_REPORT:
            return FeedbackPriority.HIGH
        
        if any(keyword in text_content for keyword in critical_keywords):
            return FeedbackPriority.CRITICAL
        
        if any(keyword in text_content for keyword in high_keywords):
            return FeedbackPriority.HIGH
        
        if category == FeedbackCategory.COMPLAINT:
            return FeedbackPriority.HIGH
        
        return None
    
    @staticmethod
    def get_feedback_list(
        db: Session,
        page: int = 1,
        per_page: int = 20,
        category: Optional[FeedbackCategory] = None,
        status: Optional[FeedbackStatus] = None,
        priority: Optional[FeedbackPriority] = None,
        user_id: Optional[int] = None,
        assigned_to: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search_query: Optional[str] = None
    ) -> Tuple[List[Feedback], int]:
        """Get paginated feedback list with filters"""
        
        query = db.query(Feedback)
        
        # Apply filters
        if category:
            query = query.filter(Feedback.category == category)
        
        if status:
            query = query.filter(Feedback.status == status)
        
        if priority:
            query = query.filter(Feedback.priority == priority)
        
        if user_id:
            query = query.filter(Feedback.user_id == user_id)
        
        if assigned_to:
            query = query.filter(Feedback.assigned_to == assigned_to)
        
        if date_from:
            query = query.filter(Feedback.created_at >= date_from)
        
        if date_to:
            query = query.filter(Feedback.created_at <= date_to)
        
        if search_query:
            search = f"%{search_query}%"
            query = query.filter(
                or_(
                    Feedback.subject.ilike(search),
                    Feedback.message.ilike(search),
                    Feedback.contact_name.ilike(search),
                    Feedback.feedback_id.ilike(search)
                )
            )
        
        # Exclude spam
        query = query.filter(Feedback.is_spam == False)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        feedbacks = query.order_by(desc(Feedback.created_at)).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        return feedbacks, total
    
    @staticmethod
    def get_feedback_by_id(db: Session, feedback_id: str) -> Optional[Feedback]:
        """Get feedback by public ID"""
        return db.query(Feedback).filter(Feedback.feedback_id == feedback_id).first()
    
    @staticmethod
    def update_feedback_status(
        db: Session,
        feedback: Feedback,
        new_status: FeedbackStatus,
        admin_notes: Optional[str] = None,
        resolution: Optional[str] = None,
        assigned_to: Optional[int] = None
    ) -> Feedback:
        """Update feedback status and admin fields"""
        
        feedback.status = new_status
        feedback.updated_at = datetime.utcnow()
        
        if admin_notes:
            feedback.admin_notes = admin_notes
        
        if resolution:
            feedback.resolution = resolution
        
        if assigned_to:
            feedback.assigned_to = assigned_to
        
        if new_status == FeedbackStatus.RESOLVED:
            feedback.resolved_at = datetime.utcnow()
        
        db.commit()
        db.refresh(feedback)
        
        return feedback
    
    @staticmethod
    def get_feedback_analytics(
        db: Session,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get feedback analytics for dashboard"""
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Total feedback in period
        total_feedback = db.query(Feedback).filter(
            Feedback.created_at >= cutoff_date,
            Feedback.is_spam == False
        ).count()
        
        # By category
        category_stats = db.query(
            Feedback.category,
            func.count(Feedback.id).label('count')
        ).filter(
            Feedback.created_at >= cutoff_date,
            Feedback.is_spam == False
        ).group_by(Feedback.category).all()
        
        # By priority
        priority_stats = db.query(
            Feedback.priority,
            func.count(Feedback.id).label('count')
        ).filter(
            Feedback.created_at >= cutoff_date,
            Feedback.is_spam == False
        ).group_by(Feedback.priority).all()
        
        # By status
        status_stats = db.query(
            Feedback.status,
            func.count(Feedback.id).label('count')
        ).filter(
            Feedback.created_at >= cutoff_date,
            Feedback.is_spam == False
        ).group_by(Feedback.status).all()
        
        # Response time analysis (pending vs resolved)
        pending_count = db.query(Feedback).filter(
            Feedback.status == FeedbackStatus.PENDING,
            Feedback.is_spam == False
        ).count()
        
        resolved_count = db.query(Feedback).filter(
            Feedback.status == FeedbackStatus.RESOLVED,
            Feedback.created_at >= cutoff_date,
            Feedback.is_spam == False
        ).count()
        
        # Average resolution time
        resolved_feedback = db.query(Feedback).filter(
            Feedback.status == FeedbackStatus.RESOLVED,
            Feedback.resolved_at.isnot(None),
            Feedback.created_at >= cutoff_date,
            Feedback.is_spam == False
        ).all()
        
        if resolved_feedback:
            resolution_times = [
                (fb.resolved_at - fb.created_at).total_seconds() / 3600  # Hours
                for fb in resolved_feedback
            ]
            avg_resolution_hours = sum(resolution_times) / len(resolution_times)
        else:
            avg_resolution_hours = 0
        
        return {
            "total_feedback": total_feedback,
            "pending_feedback": pending_count,
            "resolved_feedback": resolved_count,
            "avg_resolution_hours": round(avg_resolution_hours, 2),
            "category_breakdown": {cat.value: count for cat, count in category_stats},
            "priority_breakdown": {pri.value: count for pri, count in priority_stats},
            "status_breakdown": {status.value: count for status, count in status_stats},
            "resolution_rate": round((resolved_count / total_feedback * 100), 2) if total_feedback > 0 else 0
        }
    
    @staticmethod
    def mark_as_spam(db: Session, feedback: Feedback) -> Feedback:
        """Mark feedback as spam"""
        feedback.is_spam = True
        feedback.status = FeedbackStatus.CLOSED
        feedback.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(feedback)
        return feedback
    
    @staticmethod
    def get_user_feedback_history(
        db: Session,
        user_id: int,
        page: int = 1,
        per_page: int = 10
    ) -> Tuple[List[Feedback], int]:
        """Get user's feedback history"""
        
        query = db.query(Feedback).filter(
            Feedback.user_id == user_id,
            Feedback.is_spam == False
        )
        
        total = query.count()
        
        feedbacks = query.order_by(desc(Feedback.created_at)).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        return feedbacks, total
    
    @staticmethod
    def get_urgent_feedback(db: Session) -> List[Feedback]:
        """Get urgent feedback requiring immediate attention"""
        
        return db.query(Feedback).filter(
            Feedback.priority.in_([FeedbackPriority.HIGH, FeedbackPriority.CRITICAL]),
            Feedback.status.in_([FeedbackStatus.PENDING, FeedbackStatus.IN_REVIEW]),
            Feedback.is_spam == False
        ).order_by(
            Feedback.priority.desc(),
            Feedback.created_at
        ).limit(50).all()