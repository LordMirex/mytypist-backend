"""
Routes for social media analytics
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from database import get_db
from app.services.social_analytics import SocialAnalytics

router = APIRouter()
analytics = SocialAnalytics()

@router.get("/engagement/{document_id}")
async def get_document_engagement(
    document_id: int,
    days: Optional[int] = Query(None, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get engagement metrics for a specific document
    """
    return analytics.get_document_engagement(db, document_id, days)

@router.get("/overall")
async def get_overall_engagement(
    days: Optional[int] = Query(None, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get overall social engagement metrics
    """
    return analytics.get_overall_engagement(db, days)

@router.get("/top-documents")
async def get_top_documents(
    limit: int = Query(10, ge=1, le=100),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get top performing documents by social engagement
    """
    return analytics.get_top_performing_documents(db, limit, days)

@router.get("/traffic-sources")
async def get_traffic_sources(
    days: Optional[int] = Query(None, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get breakdown of traffic sources
    """
    return analytics.get_traffic_sources(db, days)