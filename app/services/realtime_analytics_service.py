"""
Real-time Analytics Service
Handles real-time tracking and analytics for the landing page
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from fastapi import HTTPException, status

from app.services.cache_service import CacheService
from app.services.landing_page_service import LandingPageVisit, LandingPageTemplate
from app.utils.security import sanitize_user_input
from app.utils.validation import validate_analytics_data

logger = logging.getLogger(__name__)

class RealtimeAnalyticsService:
    """Service for real-time analytics tracking and reporting"""

    CACHE_PREFIX = "analytics:"
    RATE_LIMIT_PREFIX = "rate_limit:"
    
    @staticmethod
    async def track_user_interaction(
        db: Session,
        session_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Track real-time user interaction with enhanced analytics"""
        try:
            # Rate limiting with adaptive thresholds
            rate_limit_key = f"{RealtimeAnalyticsService.RATE_LIMIT_PREFIX}:{session_id}"
            if not RealtimeAnalyticsService._check_rate_limit(rate_limit_key):
                logger.warning(f"Rate limit exceeded for session {session_id}")
                return {"success": False, "error": "rate_limit_exceeded"}
                
            # Enhanced session tracking
            now = timestamp or datetime.utcnow()
            visit = db.query(LandingPageVisit).filter(
                LandingPageVisit.session_id == session_id
            ).first()
            
            if visit:
                # Update engagement metrics
                visit.active_time_seconds = RealtimeAnalyticsService._calculate_active_time(
                    visit.active_time_seconds,
                    visit.last_interaction_at,
                    now
                )
                
                # Update bounce classification
                visit.bounce = False
                visit.bounce_type = RealtimeAnalyticsService._classify_bounce_type(
                    visit.created_at,
                    now,
                    visit.engagement_depth
                )
                
                # Calculate conversion probability
                visit.conversion_probability = RealtimeAnalyticsService._calculate_conversion_probability(
                    visit.engagement_depth,
                    visit.session_quality_score,
                    visit.template_interactions
                )

            # Validate and sanitize
            sanitized_data = sanitize_user_input(event_data)
            validation_result = validate_analytics_data(sanitized_data)
            if not validation_result["valid"]:
                return {"success": False, "error": "invalid_data"}

            @staticmethod
            def _calculate_active_time(current_active_time: int, last_interaction: datetime, current_time: datetime) -> int:
                """Calculate active time based on interaction gaps"""
                if not last_interaction:
                    return current_active_time
                gap = (current_time - last_interaction).total_seconds()
                if gap < 300:  # Consider gaps less than 5 minutes as active time
                    return current_active_time + int(gap)
                return current_active_time

            @staticmethod
            def _classify_bounce_type(created_at: datetime, current_time: datetime, engagement_depth: int) -> str:
                """Classify bounce type based on session duration and engagement"""
                duration = (current_time - created_at).total_seconds()
                if duration < 10:
                    return "quick"
                elif duration < 30 and engagement_depth < 2:
                    return "normal"
                return "delayed"

            @staticmethod
            def _calculate_conversion_probability(engagement_depth: int, quality_score: float, interactions: str) -> float:
                """Calculate probability of conversion using engagement metrics"""
                base_score = min(quality_score * 0.4 + engagement_depth * 0.3, 1.0)
                
                if not interactions:
                    return base_score
                    
                interaction_data = json.loads(interactions)
                interaction_score = min(len(interaction_data) * 0.1, 0.3)
                
                return min(base_score + interaction_score, 1.0)

            # Get visit record
            visit = db.query(LandingPageVisit).filter(
                LandingPageVisit.session_id == session_id
            ).with_for_update().first()

            if not visit:
                return {"success": False, "error": "visit_not_found"}

            # Update metrics based on event type
            current_time = timestamp or datetime.utcnow()
            
            if visit.first_interaction_at is None:
                visit.first_interaction_at = current_time
                visit.bounce = False
            
            visit.last_interaction_at = current_time
            
            # Track interaction by type
            if event_type == "page_view":
                RealtimeAnalyticsService._track_page_view(visit, sanitized_data)
            elif event_type == "template_interaction":
                RealtimeAnalyticsService._track_template_interaction(visit, sanitized_data)
            elif event_type == "form_interaction":
                RealtimeAnalyticsService._track_form_interaction(visit, sanitized_data)
            elif event_type == "scroll":
                RealtimeAnalyticsService._track_scroll(visit, sanitized_data)
            
            # Update session quality score
            visit.session_quality_score = RealtimeAnalyticsService._calculate_session_quality(visit)
            
            # Commit changes
            db.commit()
            
            # Update real-time cache
            await RealtimeAnalyticsService._update_realtime_metrics(db, event_type, sanitized_data)

            return {
                "success": True,
                "event_tracked": True,
                "session_quality_score": visit.session_quality_score
            }

        except Exception as e:
            logger.error(f"Failed to track interaction: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to track interaction"
            )

    @staticmethod
    async def get_realtime_metrics(db: Session) -> Dict[str, Any]:
        """Get real-time analytics metrics with caching"""
        try:
            cache_key = f"{RealtimeAnalyticsService.CACHE_PREFIX}realtime_metrics"
            cached_data = await CacheService.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)

            current_time = datetime.utcnow()
            last_minute = current_time - timedelta(minutes=1)
            last_five_minutes = current_time - timedelta(minutes=5)

            # Get real-time metrics
            active_sessions = db.query(LandingPageVisit).filter(
                LandingPageVisit.last_interaction_at >= last_five_minutes
            ).count()

            conversions_last_minute = db.query(LandingPageVisit).filter(
                LandingPageVisit.converted_at >= last_minute
            ).count()

            page_views_last_minute = db.query(func.sum(LandingPageVisit.templates_viewed_count)).filter(
                LandingPageVisit.last_interaction_at >= last_minute
            ).scalar() or 0

            # Get top active templates
            top_templates = db.query(
                LandingPageTemplate.template_id,
                func.count(LandingPageVisit.id).label('active_viewers')
            ).join(
                LandingPageVisit,
                LandingPageVisit.viewed_templates.contains(str(LandingPageTemplate.template_id))
            ).filter(
                LandingPageVisit.last_interaction_at >= last_five_minutes
            ).group_by(
                LandingPageTemplate.template_id
            ).order_by(
                desc('active_viewers')
            ).limit(5).all()

            metrics = {
                "timestamp": current_time.isoformat(),
                "active_sessions": active_sessions,
                "conversions_per_minute": conversions_last_minute,
                "page_views_per_minute": page_views_last_minute,
                "top_active_templates": [{
                    "template_id": t.template_id,
                    "active_viewers": t.active_viewers
                } for t in top_templates]
            }

            # Cache for 30 seconds
            await CacheService.set(cache_key, json.dumps(metrics), expire_in=30)

            return metrics

        except Exception as e:
            logger.error(f"Failed to get realtime metrics: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get realtime metrics"
            )

    @staticmethod
    def _check_rate_limit(key: str) -> bool:
        """Check if request is within rate limits"""
        try:
            current = CacheService.incr(key)
            if current == 1:
                CacheService.expire(key, 60)  # Reset after 1 minute
            return current <= 100  # Max 100 events per minute per session
        except:
            return True  # Allow if Redis is down

    @staticmethod
    def _track_page_view(visit: LandingPageVisit, data: Dict[str, Any]):
        """Track page view interaction"""
        pages = json.loads(visit.pages_viewed or "[]")
        pages.append({
            "page": data["page"],
            "timestamp": datetime.utcnow().isoformat(),
            "time_on_page": data.get("time_on_page", 0)
        })
        visit.pages_viewed = json.dumps(pages)

    @staticmethod
    def _track_template_interaction(visit: LandingPageVisit, data: Dict[str, Any]):
        """Track template interaction"""
        interactions = json.loads(visit.template_interactions or "[]")
        interactions.append({
            "template_id": data["template_id"],
            "action": data["action"],
            "timestamp": datetime.utcnow().isoformat(),
            "duration": data.get("duration", 0)
        })
        visit.template_interactions = json.dumps(interactions)
        visit.templates_viewed_count += 1

    @staticmethod
    def _track_form_interaction(visit: LandingPageVisit, data: Dict[str, Any]):
        """Track form interaction"""
        interactions = json.loads(visit.form_interactions or "[]")
        interactions.append({
            "field_id": data["field_id"],
            "action": data["action"],
            "timestamp": datetime.utcnow().isoformat()
        })
        visit.form_interactions = json.dumps(interactions)
        visit.last_interaction_field = data["field_id"]
        visit.form_completion = data.get("form_completion", visit.form_completion)

    @staticmethod
    def _track_scroll(visit: LandingPageVisit, data: Dict[str, Any]):
        """Track scroll depth"""
        visit.scroll_depth = max(visit.scroll_depth, data.get("scroll_depth", 0))

    @staticmethod
    def _calculate_session_quality(visit: LandingPageVisit) -> float:
        """Calculate session quality score based on interactions"""
        score = 0.0
        
        # Base engagement metrics
        if visit.templates_viewed_count > 0:
            score += min(visit.templates_viewed_count * 0.2, 2.0)
        
        if visit.time_on_page_seconds > 0:
            score += min(visit.time_on_page_seconds / 60.0, 2.0)
        
        if visit.scroll_depth > 0:
            score += (visit.scroll_depth / 100.0)
        
        # Form engagement
        if visit.form_completion > 0:
            score += (visit.form_completion * 2.0)
        
        # Conversion actions
        if visit.created_document:
            score += 3.0
        if visit.registered:
            score += 4.0
        if visit.downloaded_document:
            score += 5.0
        if visit.converted_to_paid:
            score += 10.0
        
        return min(score, 10.0)  # Cap at 10.0

    @staticmethod
    async def _update_realtime_metrics(
        db: Session,
        event_type: str,
        event_data: Dict[str, Any]
    ):
        """Update real-time metrics in cache"""
        try:
            current_minute = datetime.utcnow().replace(second=0, microsecond=0)
            cache_key = f"{RealtimeAnalyticsService.CACHE_PREFIX}events:{current_minute.isoformat()}"
            
            events = json.loads(await CacheService.get(cache_key) or "{}")
            
            # Update event counts
            events[event_type] = events.get(event_type, 0) + 1
            
            # Track template-specific metrics
            if "template_id" in event_data:
                template_key = f"template:{event_data['template_id']}"
                events[template_key] = events.get(template_key, 0) + 1
            
            await CacheService.set(cache_key, json.dumps(events), expire_in=300)  # Keep for 5 minutes

        except Exception as e:
            logger.error(f"Failed to update realtime metrics: {e}")
            # Don't raise exception - this is a background operation
