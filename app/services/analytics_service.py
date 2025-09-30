"""
Analytics and tracking service
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from fastapi import Request

from app.models.document import Document
from app.models.template import Template
from app.models.user import User
from app.models.analytics.visit import DocumentVisit, LandingPageVisit, PageVisit
from app.services.analytics.visit_tracking import VisitTrackingService


class AnalyticsService:
    """Analytics and tracking service"""
    
    @staticmethod
    def track_document_visit(
        db: Session,
        document_id: int,
        visit_type: str,
        request: Optional[Request] = None
    ) -> DocumentVisit:
        """Track a document visit"""
        try:
            # Get request data
            request_data = {}
            if request:
                request_data = {
                    "ip_address": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                    "referrer": request.headers.get("referer")
                }
            
            # Enrich visit data
            visit_data = VisitTrackingService.enrich_visit_data(request_data)
            
            # Create visit record
            visit = DocumentVisit(
                document_id=document_id,
                visit_type=visit_type,
                **visit_data
            )
            
            db.add(visit)
            db.commit()
            db.refresh(visit)
            
            return visit
            
        except Exception as e:
            logger.error(f"Failed to track document visit: {e}")
            raise
            visitor_country = location.get("country")
            visitor_city = location.get("city")
        
        # Create visit record
        visit = Visit(
            document_id=document_id,
            visitor_ip=visitor_ip,
            visitor_user_agent=visitor_user_agent,
            visitor_country=visitor_country,
            visitor_city=visitor_city,
            visit_type=visit_type,
            device_type=device_type,
            browser=browser,
            os=os,
            tracking_consent=True,  # Would be determined by cookie/consent
            analytics_consent=True,
            gdpr_compliant=True
        )
        
        db.add(visit)
        db.commit()
        db.refresh(visit)
        
        return visit
    
    @staticmethod
    def process_document_analytics(visits: List[DocumentVisit]) -> Dict[str, Any]:
        """Process document visit analytics"""
        if not visits:
            return {
                "total_visits": 0,
                "unique_visitors": 0,
                "visit_types": {},
                "device_breakdown": {},
                "browser_breakdown": {},
                "country_breakdown": {},
                "daily_visits": [],
                "bounce_rate": 0,
                "average_time_reading": 0
            }
        
        # Basic metrics
        total_visits = len(visits)
        unique_visitors = len(set(v.device_fingerprint for v in visits if v.device_fingerprint))
        
        # Visit types
        visit_types = {}
        for visit in visits:
            visit_types[visit.visit_type] = visit_types.get(visit.visit_type, 0) + 1
        
        # Device breakdown
        device_breakdown = {}
        for visit in visits:
            if visit.device_type:
                device_breakdown[visit.device_type] = device_breakdown.get(visit.device_type, 0) + 1
        
        # Browser breakdown
        browser_breakdown = {}
        for visit in visits:
            if visit.browser_name:
                browser_breakdown[visit.browser_name] = browser_breakdown.get(visit.browser_name, 0) + 1
        
        # Country breakdown
        country_breakdown = {}
        for visit in visits:
            if visit.country:
                country_breakdown[visit.country] = country_breakdown.get(visit.country, 0) + 1
        
        # Daily visits
        daily_visits = {}
        for visit in visits:
            date_key = visit.created_at.date().isoformat()
            daily_visits[date_key] = daily_visits.get(date_key, 0) + 1
        
        daily_visits_list = [
            {"date": date, "visits": count}
            for date, count in sorted(daily_visits.items())
        ]
        
        # Reading metrics
        total_reading_time = sum(v.time_reading for v in visits if v.time_reading)
        average_time_reading = total_reading_time / total_visits if total_visits > 0 else 0
        
        # Calculate bounce rate
        bounced_visits = len([v for v in visits if v.bounce])
        bounce_rate = (bounced_visits / total_visits * 100) if total_visits > 0 else 0
        
        return {
            "total_visits": total_visits,
            "unique_visitors": unique_visitors,
            "visit_types": visit_types,
            "device_breakdown": device_breakdown,
            "browser_breakdown": browser_breakdown,
            "country_breakdown": country_breakdown,
            "daily_visits": daily_visits_list,
            "bounce_rate": bounce_rate,
            "average_time_reading": average_time_reading
        }
    
    @staticmethod
    def get_dashboard_analytics(db: Session, user_id: int) -> Dict[str, Any]:
        """Get comprehensive analytics dashboard data"""
        
        # Time periods
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)
        
        # Document statistics
        user_documents = db.query(Document).filter(Document.user_id == user_id)
        
        total_documents = user_documents.count()
        documents_today = user_documents.filter(
            func.date(Document.created_at) == today
        ).count()
        documents_this_week = user_documents.filter(
            Document.created_at >= last_7_days
        ).count()
        
        # Visit statistics
        user_visits = db.query(DocumentVisit).join(Document).filter(Document.user_id == user_id)
        
        total_visits = user_visits.count()
        visits_today = user_visits.filter(
            func.date(DocumentVisit.created_at) == today
        ).count()
        visits_yesterday = user_visits.filter(
            func.date(DocumentVisit.created_at) == yesterday
        ).count()
        
        # Top documents
        top_documents = db.query(
            Document.id,
            Document.title,
            func.count(DocumentVisit.id).label('visit_count')
        ).join(
            DocumentVisit, DocumentVisit.document_id == Document.id
        ).filter(
            Document.user_id == user_id,
            DocumentVisit.created_at >= last_30_days
        ).group_by(
            Document.id, Document.title
        ).order_by(
            desc('visit_count')
        ).limit(5).all()
        
        # Template usage
        template_usage = db.query(
            Template.id,
            Template.name,
            func.count(Document.id).label('usage_count')
        ).join(
            Document, Document.template_id == Template.id
        ).filter(
            Document.user_id == user_id,
            Document.created_at >= last_30_days
        ).group_by(
            Template.id, Template.name
        ).order_by(
            desc('usage_count')
        ).limit(5).all()
        
        return {
            "overview": {
                "total_documents": total_documents,
                "total_visits": total_visits,
                "documents_today": documents_today,
                "visits_today": visits_today,
                "documents_this_week": documents_this_week,
                "visit_growth": AnalyticsService._calculate_growth(visits_today, visits_yesterday)
            },
            "top_documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "visits": doc.visit_count
                }
                for doc in top_documents
            ],
            "template_usage": [
                {
                    "id": template.id,
                    "name": template.name,
                    "usage_count": template.usage_count
                }
                for template in template_usage
            ]
        }
    
    @staticmethod
    def export_analytics_data(
        db: Session,
        user_id: int,
        document_id: Optional[int],
        days: int,
        format: str
    ) -> Dict[str, Any]:
        """Export analytics data in specified format"""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Build query
        query = db.query(DocumentVisit).join(Document).filter(
            Document.user_id == user_id,
            DocumentVisit.created_at >= start_date
        )
        
        if document_id:
            query = query.filter(DocumentVisit.document_id == document_id)
        
        visits = query.all()
        
        if format == "csv":
            # Prepare CSV data
            csv_data = []
            for visit in visits:
                csv_data.append({
                    "visit_id": visit.id,
                    "document_id": visit.document_id,
                    "visit_type": visit.visit_type,
                    "country": visit.country,
                    "city": visit.city,
                    "device_type": visit.device_type,
                    "browser_name": visit.browser_name,
                    "os_name": visit.os_name,
                    "created_at": visit.created_at.isoformat(),
                    "time_reading": visit.time_reading,
                    "bounce": visit.bounce,
                    "device_fingerprint": visit.device_fingerprint
                })
            
            return {
                "format": "csv",
                "data": csv_data,
                "total_records": len(csv_data)
            }
        
        else:  # JSON format
            json_data = []
            for visit in visits:
                json_data.append({
                    "visit_id": visit.id,
                    "document_id": visit.document_id,
                    "visit_type": visit.visit_type,
                    "visitor_info": {
                        "country": visit.country,
                        "city": visit.city,
                        "device_type": visit.device_type,
                        "browser": visit.browser_name,
                        "os": visit.os_name,
                        "device_fingerprint": visit.device_fingerprint
                    },
                    "engagement": {
                        "time_reading": visit.time_reading,
                        "bounce": visit.bounce
                    },
                    "created_at": visit.created_at.isoformat(),
                    "metadata": visit.metadata
                })
            
            return {
                "format": "json",
                "export_date": datetime.utcnow().isoformat(),
                "period_days": days,
                "total_records": len(json_data),
                "visits": json_data
            }
    
    @staticmethod
    def anonymize_user_analytics(
        db: Session,
        user_id: int,
        document_id: Optional[int] = None
    ) -> int:
        """Anonymize analytics data for GDPR compliance"""
        
        query = db.query(DocumentVisit).join(Document).filter(Document.user_id == user_id)
        
        if document_id:
            query = query.filter(DocumentVisit.document_id == document_id)
        
        visits = query.all()
        anonymized_count = 0
        
        for visit in visits:
            # Anonymize IP address
            if visit.ip_address:
                visit.ip_address = "XXX.XXX.XXX.XXX"
            
            # Remove precise location data
            visit.city = None
            visit.latitude = None
            visit.longitude = None
            
            # Anonymize user agent and device fingerprint
            visit.user_agent = "[ANONYMIZED]"
            visit.device_fingerprint = "[ANONYMIZED]"
            
            # Clear metadata that might contain PII
            if visit.metadata:
                visit.metadata = {"anonymized": True}
            
            anonymized_count += 1
        
        db.commit()
        return anonymized_count
    
    @staticmethod
    def _get_client_ip(request: Request) -> Optional[str]:
        """Extract client IP from request"""
        
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        return request.client.host if request.client else None
    
    @staticmethod
    def _parse_user_agent(user_agent: Optional[str]) -> Dict[str, str]:
        """Parse user agent string for device information - simplified without user_agents library"""
        
        if not user_agent:
            return {"device_type": "unknown", "browser": "unknown", "os": "unknown"}
        
        # Simplified user agent parsing without external dependency
        user_agent_lower = user_agent.lower()
        
        # Basic browser detection
        browser = "Unknown"
        if "chrome" in user_agent_lower:
            browser = "Chrome"
        elif "firefox" in user_agent_lower:
            browser = "Firefox"
        elif "safari" in user_agent_lower:
            browser = "Safari"
        elif "edge" in user_agent_lower:
            browser = "Edge"
        
        # Basic device type detection
        device_type = "desktop"
        if any(x in user_agent_lower for x in ["mobile", "android", "iphone"]):
            device_type = "mobile"
        elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
            device_type = "tablet"
        
        # Basic OS detection
        os = "Unknown"
        if "windows" in user_agent_lower:
            os = "Windows"
        elif "mac os" in user_agent_lower:
            os = "macOS"
        elif "linux" in user_agent_lower:
            os = "Linux"
        elif "android" in user_agent_lower:
            os = "Android"
        elif "ios" in user_agent_lower:
            os = "iOS"
        
        return {
            "device_type": device_type,
            "browser": browser,
            "os": os
        }
    
    @staticmethod
    def _get_location_from_ip(ip_address: Optional[str]) -> Dict[str, Optional[str]]:
        """Get location information from IP address"""
        
        # Implement basic GeoIP lookup for production
        if not ip_address or ip_address in ["127.0.0.1", "localhost", "::1"]:
            return {"country": None, "city": None}
        
        # Basic IP analysis for Nigerian market focus
        # In future versions, integrate with MaxMind GeoIP2 service
        try:
            # Default to Nigeria for MVP since it's Nigerian-focused platform
            return {"country": "Nigeria", "city": None}
        except Exception:
            return {"country": None, "city": None}
    
    @staticmethod
    def _calculate_growth(current: int, previous: int) -> float:
        """Calculate growth percentage"""
        
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        
        return ((current - previous) / previous) * 100

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
