"""
Shared analytics services
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import Request

from app.models.analytics.visit import BaseVisit, DocumentVisit, LandingVisit, PageVisit
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class VisitTrackingService:
    """Unified analytics and visit tracking service"""
    
    CACHE_PREFIX = "analytics:"
    RATE_LIMIT_PREFIX = "rate_limit:"
    
    def __init__(self, cache_service: Optional[CacheService] = None):
        self.cache = cache_service or CacheService()
    
    @staticmethod
    def enrich_visit_data(request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich raw visit data with derived fields"""
        enriched = request_data.copy()
        
        # Parse referrer domain
        if referrer := request_data.get('referrer'):
            from urllib.parse import urlparse
            try:
                enriched['referrer_domain'] = urlparse(referrer).netloc
            except:
                pass
        
        # Parse user agent
        if user_agent := request_data.get('user_agent'):
            ua_info = VisitTrackingService._parse_user_agent(user_agent)
            enriched.update(ua_info)
        
        # Add timestamp
        enriched['created_at'] = datetime.utcnow()
        
        return enriched
    
    @staticmethod
    def _parse_user_agent(user_agent: str) -> Dict[str, str]:
        """Extract browser and OS info from user agent string"""
        try:
            from user_agents import parse
            ua = parse(user_agent)
            
            return {
                'browser_name': ua.browser.family,
                'browser_version': ua.browser.version_string,
                'os_name': ua.os.family,
                'os_version': ua.os.version_string,
                'device_type': ('mobile' if ua.is_mobile else 
                              'tablet' if ua.is_tablet else 'desktop')
            }
        except ImportError:
            # Fallback to basic parsing if user-agents package not available
            ua_lower = user_agent.lower()
            
            browser = "Unknown"
            if "chrome" in ua_lower:
                browser = "Chrome"
            elif "firefox" in ua_lower:
                browser = "Firefox"
            elif "safari" in ua_lower:
                browser = "Safari"
            elif "edge" in ua_lower:
                browser = "Edge"
            
            device_type = "desktop"
            if any(x in ua_lower for x in ["mobile", "android", "iphone"]):
                device_type = "mobile"
            elif any(x in ua_lower for x in ["ipad", "tablet"]):
                device_type = "tablet"
            
            return {
                'browser_name': browser,
                'browser_version': None,
                'os_name': None,
                'os_version': None,
                'device_type': device_type
            }
    
    @staticmethod
    def update_session_metrics(visit: BaseVisit, current_time: datetime) -> None:
        """Update session-based metrics for a visit"""
        if not visit.first_interaction_at:
            visit.first_interaction_at = current_time
            visit.bounce = False
        
        # Update active time
        if visit.last_interaction_at:
            time_diff = (current_time - visit.last_interaction_at).total_seconds()
            if time_diff <= 1800:  # 30 minute timeout
                visit.active_time_seconds += int(time_diff)
        
        visit.last_interaction_at = current_time
        
        # Calculate session quality score
        visit.session_quality_score = VisitTrackingService._calculate_session_quality(visit)
    
    @staticmethod
    def _calculate_session_quality(visit: BaseVisit) -> float:
        """Calculate overall session quality score"""
        score = 0.0
        
        # Base engagement factors
        if not visit.bounce:
            score += 0.3
        
        # Time-based factors
        time_factor = min(visit.active_time_seconds / 300, 1.0)  # Cap at 5 minutes
        score += time_factor * 0.3
        
        # Interaction factors
        interaction_score = min(visit.clicks_count / 10, 1.0)  # Cap at 10 clicks
        score += interaction_score * 0.2
        
        # Scroll depth factor
        scroll_factor = visit.scroll_depth / 100  # Convert percentage to 0-1
        score += scroll_factor * 0.2
        
        return min(score, 1.0)  # Ensure score is between 0 and 1
    
    @staticmethod
    def _classify_bounce_type(created_at: datetime, 
                            last_interaction: datetime,
                            engagement_depth: int) -> str:
        """Classify the type of bounce based on engagement"""
        if engagement_depth > 2:
            return None  # Not a bounce
            
        duration = (last_interaction - created_at).total_seconds()
        
        if duration < 10:
            return "quick"
        elif duration < 30:
            return "normal"
        else:
            return "delayed"
            
    def track_document_visit(
        self,
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
                    "ip_address": self._get_client_ip(request),
                    "user_agent": request.headers.get("user-agent"),
                    "referrer": request.headers.get("referer")
                }
            
            # Enrich visit data
            visit_data = self.enrich_visit_data(request_data)
            
            # Create visit record
            visit = DocumentVisit(
                document_id=document_id,
                visit_type=visit_type,
                **visit_data
            )
            
            db.add(visit)
            db.commit()
            
            return visit
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error tracking document visit: {str(e)}")
            raise
            
    @staticmethod
    def process_document_analytics(visits: List[DocumentVisit]) -> Dict[str, Any]:
        """Process analytics data from document visits"""
        analytics = {
            "total_visits": len(visits),
            "unique_visitors": len(set(v.ip_address for v in visits if v.ip_address)),
            "browser_stats": {},
            "device_stats": {},
            "os_stats": {},
            "avg_session_quality": 0.0,
            "bounce_rate": 0.0,
            "avg_active_time": 0.0
        }
        
        if not visits:
            return analytics
        
        # Device, browser and OS stats
        device_counts = {}
        browser_counts = {}
        os_counts = {}
        total_session_quality = 0
        total_active_time = 0
        bounce_count = 0
        
        for visit in visits:
            # Device stats
            device = visit.device_type or "unknown"
            device_counts[device] = device_counts.get(device, 0) + 1
            
            # Browser stats    
            browser = visit.browser_name or "unknown"
            browser_counts[browser] = browser_counts.get(browser, 0) + 1
            
            # OS stats
            os_name = visit.os_name or "unknown"
            os_counts[os_name] = os_counts.get(os_name, 0) + 1
            
            # Quality metrics
            total_session_quality += visit.session_quality_score
            total_active_time += visit.active_time_seconds
            
            if visit.bounce:
                bounce_count += 1
                
        total = len(visits)
        analytics.update({
            "browser_stats": {k: v/total for k, v in browser_counts.items()},
            "device_stats": {k: v/total for k, v in device_counts.items()},
            "os_stats": {k: v/total for k, v in os_counts.items()},
            "avg_session_quality": total_session_quality / total,
            "bounce_rate": bounce_count / total if total > 0 else 0,
            "avg_active_time": total_active_time / total
        })
        
        return analytics
    
    @staticmethod
    def _get_client_ip(request: Request) -> Optional[str]:
        """Extract the client IP from a request, handling proxies"""
        if forwarded := request.headers.get("x-forwarded-for"):
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else None
    
    @staticmethod
    def _get_location_from_ip(ip_address: Optional[str]) -> Dict[str, Optional[str]]:
        """Get location data from an IP address using GeoIP"""
        if not ip_address:
            return {
                "country": "Nigeria",  # Default to Nigeria for MVP since it's Nigerian-focused platform
                "region": None,
                "city": None
            }
            
        try:
            import geoip2.database
            from pathlib import Path
            
            db_path = Path("/usr/share/GeoIP/GeoLite2-City.mmdb")
            if not db_path.exists():
                return {"country": "Nigeria", "region": None, "city": None}
                
            with geoip2.database.Reader(db_path) as reader:
                response = reader.city(ip_address)
                return {
                    "country": response.country.name,
                    "region": response.subdivisions.most_specific.name if response.subdivisions else None,
                    "city": response.city.name
                }
        except:
            return {"country": "Nigeria", "region": None, "city": None}
    
    @staticmethod
    def _calculate_growth(current: int, previous: int) -> float:
        """Calculate growth rate between two periods"""
        if previous == 0:
            return 100 if current > 0 else 0
        return ((current - previous) / previous) * 100

    def export_analytics_data(
        self,
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
                    "session_quality_score": visit.session_quality_score,
                    "active_time_seconds": visit.active_time_seconds,
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
                        "session_quality_score": visit.session_quality_score,
                        "active_time_seconds": visit.active_time_seconds,
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
    
    def anonymize_user_analytics(
        self,
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
        
        try:
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
            
            # Remove any cached analytics for this user
            self.cache.delete(f"{self.CACHE_PREFIX}user:{user_id}:visit_metrics")
            
            db.commit()
            return anonymized_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error anonymizing analytics data: {str(e)}")
            raise

    def get_dashboard_analytics(self, db: Session, user_id: int) -> Dict[str, Any]:
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
        
        # Add visit metrics from cache if available
        visit_metrics = self.cache.get(f"{self.CACHE_PREFIX}user:{user_id}:visit_metrics")
        if visit_metrics:
            visit_metrics = json.loads(visit_metrics)
        else:
            visit_metrics = {}
        
        return {
            "overview": {
                "total_documents": total_documents,
                "total_visits": total_visits,
                "documents_today": documents_today,
                "visits_today": visits_today,
                "documents_this_week": documents_this_week,
                "visit_growth": self._calculate_growth(visits_today, visits_yesterday),
                "avg_session_quality": visit_metrics.get("avg_session_quality", 0),
                "avg_active_time": visit_metrics.get("avg_active_time", 0),
                "bounce_rate": visit_metrics.get("bounce_rate", 0)
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
            ],
            "device_stats": visit_metrics.get("device_stats", {}),
            "browser_stats": visit_metrics.get("browser_stats", {}),
            "os_stats": visit_metrics.get("os_stats", {})
        }