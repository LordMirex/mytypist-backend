"""
Social media engagement analytics service
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.visit import Visit
from app.models.document import Document

class SocialAnalytics:
    """Service for analyzing social media engagement"""
    
    def get_document_engagement(
        self,
        db: Session,
        document_id: int,
        days: Optional[int] = None
    ) -> Dict:
        """Get engagement metrics for a specific document"""
        query = db.query(Visit).filter(Visit.document_id == document_id)
        
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(Visit.visited_at >= cutoff)
        
        visits = query.all()
        
        return self._calculate_engagement_metrics(visits)
    
    def get_overall_engagement(
        self,
        db: Session,
        days: Optional[int] = None
    ) -> Dict:
        """Get overall social engagement metrics"""
        query = db.query(Visit)
        
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(Visit.visited_at >= cutoff)
        
        visits = query.all()
        
        return self._calculate_engagement_metrics(visits)
    
    def get_top_performing_documents(
        self,
        db: Session,
        limit: int = 10,
        days: Optional[int] = 30
    ) -> List[Dict]:
        """Get top performing documents by social engagement"""
        query = db.query(
            Document,
            func.count(Visit.id).label("visit_count"),
            func.count(func.distinct(Visit.visitor_ip)).label("unique_visitors")
        ).join(Visit)
        
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(Visit.visited_at >= cutoff)
        
        results = query.group_by(Document.id).order_by(
            func.count(Visit.id).desc()
        ).limit(limit).all()
        
        return [{
            "document_id": doc.id,
            "title": doc.title,
            "visits": visit_count,
            "unique_visitors": unique_visitors,
            "engagement_rate": round((unique_visitors / visit_count * 100), 2) if visit_count > 0 else 0
        } for doc, visit_count, unique_visitors in results]
    
    def get_traffic_sources(
        self,
        db: Session,
        days: Optional[int] = None
    ) -> Dict[str, int]:
        """Get breakdown of traffic sources"""
        query = db.query(
            Visit.utm_source,
            func.count(Visit.id).label("count")
        )
        
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(Visit.visited_at >= cutoff)
        
        results = query.group_by(Visit.utm_source).all()
        
        return {
            source or "direct": count
            for source, count in results
        }
    
    def _calculate_engagement_metrics(self, visits: List[Visit]) -> Dict:
        """Calculate engagement metrics from visits"""
        total_visits = len(visits)
        unique_visitors = len(set(v.visitor_ip for v in visits if v.visitor_ip))
        social_shares = len([v for v in visits if v.visit_type == "share"])
        
        platforms = {}
        countries = {}
        daily_visits = {}
        
        for visit in visits:
            # Track platforms
            platform = visit.utm_source or "direct"
            platforms[platform] = platforms.get(platform, 0) + 1
            
            # Track countries
            if visit.visitor_country:
                countries[visit.visitor_country] = countries.get(visit.visitor_country, 0) + 1
            
            # Track daily visits
            date = visit.visited_at.date().isoformat()
            daily_visits[date] = daily_visits.get(date, 0) + 1
        
        return {
            "total_visits": total_visits,
            "unique_visitors": unique_visitors,
            "social_shares": social_shares,
            "engagement_rate": round((unique_visitors / total_visits * 100), 2) if total_visits > 0 else 0,
            "platforms": platforms,
            "countries": countries,
            "daily_visits": daily_visits
        }