"""
Realtime Analytics Service
Handles real-time analytics tracking and metrics
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_

from app.models.analytics.visit import PageVisit, DocumentVisit
from app.models.user import User


class RealtimeAnalyticsService:
    """Real-time analytics service for tracking user interactions"""

    @staticmethod
    async def track_user_interaction(
        db: Session,
        session_id: str,
        event_type: str,
        user_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Track a real-time user interaction"""
        try:
            # Create a page visit record for the interaction
            visit = PageVisit(
                session_id=session_id,
                path=kwargs.get('path', '/'),
                user_id=user_id,
                visit_metadata={
                    'event_type': event_type,
                    'timestamp': datetime.utcnow().isoformat(),
                    **kwargs
                }
            )
            
            db.add(visit)
            db.commit()
            db.refresh(visit)
            
            return {
                'success': True,
                'visit_id': visit.id,
                'event_type': event_type,
                'timestamp': visit.created_at.isoformat()
            }
            
        except Exception as e:
            db.rollback()
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    async def get_realtime_metrics(db: Session) -> Dict[str, Any]:
        """Get real-time analytics metrics"""
        try:
            # Get metrics for the last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            # Active sessions in the last hour
            active_sessions = db.query(PageVisit.session_id).filter(
                PageVisit.created_at >= one_hour_ago
            ).distinct().count()
            
            # Total page views in the last hour
            page_views = db.query(PageVisit).filter(
                PageVisit.created_at >= one_hour_ago
            ).count()
            
            # Most active pages
            popular_pages = (
                db.query(
                    PageVisit.path,
                    func.count(PageVisit.id).label('count')
                )
                .filter(PageVisit.created_at >= one_hour_ago)
                .group_by(PageVisit.path)
                .order_by(desc('count'))
                .limit(5)
                .all()
            )
            
            # User activity (registered users only)
            active_users = db.query(PageVisit.user_id).filter(
                and_(
                    PageVisit.created_at >= one_hour_ago,
                    PageVisit.user_id.isnot(None)
                )
            ).distinct().count()
            
            return {
                'active_sessions': active_sessions,
                'page_views_last_hour': page_views,
                'active_users': active_users,
                'popular_pages': [
                    {'path': page, 'views': count} 
                    for page, count in popular_pages
                ],
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    @staticmethod
    async def get_live_user_count(db: Session) -> int:
        """Get count of users active in the last 5 minutes"""
        try:
            five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
            
            return db.query(PageVisit.session_id).filter(
                PageVisit.created_at >= five_minutes_ago
            ).distinct().count()
            
        except Exception:
            return 0

    @staticmethod
    async def get_session_activity(
        db: Session, 
        session_id: str
    ) -> List[Dict[str, Any]]:
        """Get activity for a specific session"""
        try:
            visits = (
                db.query(PageVisit)
                .filter(PageVisit.session_id == session_id)
                .order_by(desc(PageVisit.created_at))
                .limit(50)
                .all()
            )
            
            return [
                {
                    'id': visit.id,
                    'path': visit.path,
                    'timestamp': visit.created_at.isoformat(),
                    'metadata': visit.visit_metadata or {}
                }
                for visit in visits
            ]
            
        except Exception as e:
            return []
