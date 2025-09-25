"""
Analytics and tracking routes
"""

from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from database import get_db
from config import settings
from app.models.document import Document
from app.models.user import User
from app.models.analytics.visit import DocumentVisit, PageVisit
from app.services.analytics.visit_tracking import VisitTrackingService
from app.services.audit_service import AuditService
from app.services.performance_service import PerformanceService
from app.schemas.analytics import TimePeriod
from app.utils.security import get_current_active_user

router = APIRouter()


@router.post("/track")
async def track_document_visit(
    document_id: int,
    visit_type: str = "view",
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Track document visit (public endpoint for shared documents)"""
    
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Create visit record using shared tracking service
    visit_tracking = VisitTrackingService()
    visit = visit_tracking.track_document_visit(db, document_id, visit_type, request)
    
    # Return visit metrics
    return {
        "success": True,
        "message": "Visit tracked successfully",
        "visit_id": visit.id,
        "visit_metrics": {
            "time_reading": visit.time_reading if visit.time_reading else 0,
            "bounce": visit.bounce,
            "session_id": visit.session_id,
            "created_at": visit.created_at.isoformat()
        }
    }


@router.get("/performance/time-saved")
async def get_time_savings(
    time_period: TimePeriod = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get time savings analytics for the current user"""
    metrics = PerformanceService.get_user_time_savings(
        db,
        current_user.id,
        time_period.start_date if time_period else None,
        time_period.end_date if time_period else None
    )
    return metrics


@router.get("/performance/batch/{batch_id}")
async def get_batch_analytics(
    batch_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get analytics for a batch processing job"""
    # Verify batch belongs to user
    document = db.query(Document).filter(
        Document.batch_id == batch_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    analytics = PerformanceService.get_batch_analytics(db, batch_id)
    return analytics


@router.get("/performance/dashboard")
async def get_performance_dashboard(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get performance dashboard data"""
    # Get last 30 days metrics
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    time_saved = PerformanceService.get_user_time_savings(
        db,
        current_user.id,
        thirty_days_ago
    )
    
    # Get recent batches
    recent_batches = db.query(Document.batch_id).filter(
        Document.user_id == current_user.id,
        Document.batch_id.isnot(None),
        Document.created_at >= thirty_days_ago
    ).distinct().limit(5).all()
    
    batch_analytics = [
        PerformanceService.get_batch_analytics(db, batch_id)
        for (batch_id,) in recent_batches
        if batch_id
    ]
    
    return {
        "time_saved": time_saved,
        "recent_batches": batch_analytics,
        "total_documents": db.query(Document).filter(
            Document.user_id == current_user.id,
            Document.created_at >= thirty_days_ago
        ).count(),
        "period_start": thirty_days_ago,
        "period_end": datetime.utcnow()
    }


@router.get("/visits")
async def get_visit_analytics(
    document_id: Optional[int] = None,
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get visit analytics for user's documents"""
    
    # Build query for user's documents
    query = db.query(Visit).join(Document).filter(Document.user_id == current_user.id)
    
    # Filter by document if specified
    if document_id:
        # Verify user owns the document
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == current_user.id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        query = query.filter(Visit.document_id == document_id)
    
    # Filter by date range
    start_date = datetime.utcnow() - timedelta(days=days)
    query = query.filter(Visit.visited_at >= start_date)
    
    visits = query.order_by(desc(Visit.visited_at)).all()
    
    # Process analytics data
    visit_tracking = VisitTrackingService()
    analytics_data = visit_tracking.process_document_analytics(visits)
    
    return analytics_data


@router.get("/dashboard-data")
async def get_analytics_dashboard_data(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive analytics dashboard data"""
    
    visit_tracking = VisitTrackingService()
    dashboard_data = visit_tracking.get_dashboard_analytics(db, current_user.id)
    
    return dashboard_data


@router.get("/documents/performance")
async def get_document_performance(
    days: int = 30,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get top performing documents by views/downloads"""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Query for document performance
    document_performance = db.query(
        Document.id,
        Document.title,
        Document.view_count,
        Document.download_count,
        func.count(Visit.id).label('recent_visits')
    ).outerjoin(
        Visit, and_(
            Visit.document_id == Document.id,
            Visit.visited_at >= start_date
        )
    ).filter(
        Document.user_id == current_user.id,
        Document.status == "completed"
    ).group_by(
        Document.id, Document.title, Document.view_count, Document.download_count
    ).order_by(
        desc('recent_visits')
    ).limit(limit).all()
    
    performance_data = []
    for perf in document_performance:
        performance_data.append({
            "document_id": perf[0],
            "title": perf[1],
            "total_views": perf[2],
            "total_downloads": perf[3],
            "recent_visits": perf[4]
        })
    
    return {
        "period_days": days,
        "top_documents": performance_data
    }


@router.get("/traffic/sources")
async def get_traffic_sources(
    document_id: Optional[int] = None,
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get traffic sources analytics"""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Build query
    query = db.query(
        Visit.referrer,
        Visit.utm_source,
        Visit.utm_medium,
        func.count(Visit.id).label('visits')
    ).join(Document).filter(
        Document.user_id == current_user.id,
        Visit.visited_at >= start_date
    )
    
    if document_id:
        query = query.filter(Visit.document_id == document_id)
    
    traffic_sources = query.group_by(
        Visit.referrer, Visit.utm_source, Visit.utm_medium
    ).order_by(desc('visits')).all()
    
    sources_data = []
    for source in traffic_sources:
        source_name = "Direct"
        if source.utm_source:
            source_name = source.utm_source
        elif source.referrer:
            source_name = source.referrer
        
        sources_data.append({
            "source": source_name,
            "medium": source.utm_medium,
            "visits": source.visits
        })
    
    return {
        "period_days": days,
        "traffic_sources": sources_data
    }


@router.get("/geographic")
async def get_geographic_analytics(
    document_id: Optional[int] = None,
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get geographic distribution of visits"""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(
        Visit.visitor_country,
        Visit.visitor_city,
        func.count(Visit.id).label('visits')
    ).join(Document).filter(
        Document.user_id == current_user.id,
        Visit.visited_at >= start_date,
        Visit.visitor_country.isnot(None)
    )
    
    if document_id:
        query = query.filter(Visit.document_id == document_id)
    
    geographic_data = query.group_by(
        Visit.visitor_country, Visit.visitor_city
    ).order_by(desc('visits')).all()
    
    countries = {}
    cities = []
    
    for geo in geographic_data:
        country = geo.visitor_country
        city = geo.visitor_city
        visits = geo.visits
        
        # Aggregate by country
        if country in countries:
            countries[country] += visits
        else:
            countries[country] = visits
        
        # Top cities
        if city:
            cities.append({
                "city": city,
                "country": country,
                "visits": visits
            })
    
    return {
        "period_days": days,
        "countries": [{"country": k, "visits": v} for k, v in countries.items()],
        "top_cities": sorted(cities, key=lambda x: x["visits"], reverse=True)[:10]
    }


@router.get("/devices")
async def get_device_analytics(
    document_id: Optional[int] = None,
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get device and browser analytics"""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(
        Visit.device_type,
        Visit.browser,
        Visit.os,
        func.count(Visit.id).label('visits')
    ).join(Document).filter(
        Document.user_id == current_user.id,
        Visit.visited_at >= start_date
    )
    
    if document_id:
        query = query.filter(Visit.document_id == document_id)
    
    device_data = query.group_by(
        Visit.device_type, Visit.browser, Visit.os
    ).order_by(desc('visits')).all()
    
    devices = {}
    browsers = {}
    operating_systems = {}
    
    for device in device_data:
        device_type = device.device_type or "Unknown"
        browser = device.browser or "Unknown"
        os = device.os or "Unknown"
        visits = device.visits
        
        # Aggregate by device type
        if device_type in devices:
            devices[device_type] += visits
        else:
            devices[device_type] = visits
        
        # Aggregate by browser
        if browser in browsers:
            browsers[browser] += visits
        else:
            browsers[browser] = visits
        
        # Aggregate by OS
        if os in operating_systems:
            operating_systems[os] += visits
        else:
            operating_systems[os] = visits
    
    return {
        "period_days": days,
        "devices": [{"type": k, "visits": v} for k, v in devices.items()],
        "browsers": [{"browser": k, "visits": v} for k, v in browsers.items()],
        "operating_systems": [{"os": k, "visits": v} for k, v in operating_systems.items()]
    }


@router.get("/realtime")
async def get_realtime_analytics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get real-time analytics (last 24 hours)"""
    
    last_24h = datetime.utcnow() - timedelta(hours=24)
    
    # Recent visits
    recent_visits = db.query(Visit).join(Document).filter(
        Document.user_id == current_user.id,
        Visit.visited_at >= last_24h
    ).order_by(desc(Visit.visited_at)).limit(50).all()
    
    # Active documents (documents with visits in last hour)
    last_hour = datetime.utcnow() - timedelta(hours=1)
    active_documents = db.query(
        Document.id,
        Document.title,
        func.count(Visit.id).label('recent_visits')
    ).join(Visit).filter(
        Document.user_id == current_user.id,
        Visit.visited_at >= last_hour
    ).group_by(Document.id, Document.title).all()
    
    return {
        "total_visits_24h": len(recent_visits),
        "active_documents": [
            {
                "id": doc.id,
                "title": doc.title,
                "visits": doc.recent_visits
            }
            for doc in active_documents
        ],
        "recent_visits": [
            {
                "document_id": visit.document_id,
                "visit_type": visit.visit_type,
                "country": visit.visitor_country,
                "device": visit.device_type,
                "visited_at": visit.visited_at
            }
            for visit in recent_visits[:10]
        ]
    }


@router.get("/export")
async def export_analytics(
    format: str = "csv",
    document_id: Optional[int] = None,
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Export analytics data"""
    
    if format not in ["csv", "json"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported export format"
        )
    
    # Get analytics data
    visit_tracking = VisitTrackingService()
    analytics_data = visit_tracking.export_analytics_data(
        db, current_user.id, document_id, days, format
    )
    
    # Log data export
    AuditService.log_analytics_event(
        "ANALYTICS_EXPORTED",
        current_user.id,
        None,
        {
            "format": format,
            "document_id": document_id,
            "days": days,
            "record_count": len(analytics_data.get("visits", []))
        }
    )
    
    return analytics_data


@router.delete("/visits/{visit_id}")
async def delete_visit(
    visit_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete visit record (GDPR compliance)"""
    
    visit = db.query(Visit).join(Document).filter(
        Visit.id == visit_id,
        Document.user_id == current_user.id
    ).first()
    
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit record not found"
        )
    
    db.delete(visit)
    db.commit()
    
    # Log visit deletion
    AuditService.log_analytics_event(
        "VISIT_DELETED",
        current_user.id,
        request,
        {
            "visit_id": visit_id,
            "document_id": visit.document_id
        }
    )
    
    return {"message": "Visit record deleted successfully"}


@router.post("/gdpr/anonymize")
async def anonymize_analytics_data(
    document_id: Optional[int] = None,
    request: Request = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Anonymize analytics data (GDPR compliance)"""
    
    visit_tracking = VisitTrackingService()
    anonymized_count = visit_tracking.anonymize_user_analytics(
        db, current_user.id, document_id
    )
    
    # Log anonymization
    AuditService.log_analytics_event(
        "ANALYTICS_ANONYMIZED",
        current_user.id,
        request,
        {
            "document_id": document_id,
            "anonymized_count": anonymized_count
        }
    )
    
    return {
        "message": f"Anonymized {anonymized_count} analytics records",
        "anonymized_count": anonymized_count
    }
