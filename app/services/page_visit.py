"""
Page Visit Service
Handles page visit tracking and analytics
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_

from app.models.page_visit import PageVisit
from app.models.user import User


class PageVisitService:
    """Page visit tracking service"""

    @staticmethod
    def track_visit(
        db: Session,
        page_url: str,
        session_id: str,
        user_id: Optional[int] = None,
        **kwargs
    ) -> PageVisit:
        """Track a page visit"""
        visit = PageVisit(
            user_id=user_id,
            session_id=session_id,
            page_url=page_url,
            page_title=kwargs.get('page_title'),
            referrer=kwargs.get('referrer'),
            ip_address=kwargs.get('ip_address'),
            user_agent=kwargs.get('user_agent'),
            visit_duration=kwargs.get('visit_duration'),
            metadata=kwargs.get('metadata', {})
        )
        db.add(visit)
        db.commit()
        db.refresh(visit)
        return visit

    @staticmethod
    def get_user_visits(
        db: Session,
        user_id: int,
        limit: int = 50
    ) -> List[PageVisit]:
        """Get all visits for a user"""
        return (
            db.query(PageVisit)
            .filter(PageVisit.user_id == user_id)
            .order_by(desc(PageVisit.created_at))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_session_visits(
        db: Session,
        session_id: str
    ) -> List[PageVisit]:
        """Get all visits for a session"""
        return (
            db.query(PageVisit)
            .filter(PageVisit.session_id == session_id)
            .order_by(desc(PageVisit.created_at))
            .all()
        )

    @staticmethod
    def get_visit_analytics(
        db: Session,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get visit analytics for the specified period"""
        start_date = datetime.utcnow() - timedelta(days=days)

        # Total visits
        total_visits = db.query(PageVisit).filter(
            PageVisit.created_at >= start_date
        ).count()

        # Unique visitors
        unique_visitors = db.query(PageVisit.session_id).filter(
            PageVisit.created_at >= start_date
        ).distinct().count()

        # Most visited pages
        popular_pages = (
            db.query(
                PageVisit.page_url,
                func.count(PageVisit.id).label('visit_count')
            )
            .filter(PageVisit.created_at >= start_date)
            .group_by(PageVisit.page_url)
            .order_by(desc('visit_count'))
            .limit(10)
            .all()
        )

        # Visits by day
        daily_visits = (
            db.query(
                func.date(PageVisit.created_at).label('date'),
                func.count(PageVisit.id).label('count')
            )
            .filter(PageVisit.created_at >= start_date)
            .group_by(func.date(PageVisit.created_at))
            .order_by('date')
            .all()
        )

        return {
            'total_visits': total_visits,
            'unique_visitors': unique_visitors,
            'popular_pages': [{'url': page, 'count': count} for page, count in popular_pages],
            'daily_visits': [{'date': str(date), 'count': count} for date, count in daily_visits],
            'period_days': days
        }

    @staticmethod
    def cleanup_old_visits(
        db: Session,
        retention_days: int = 90
    ) -> int:
        """Clean up old visit records"""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        deleted_count = db.query(PageVisit).filter(
            PageVisit.created_at < cutoff_date
        ).delete()

        db.commit()
        return deleted_count
