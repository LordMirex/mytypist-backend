"""
Advanced Search Routes
API endpoints for enhanced search functionality
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from database import get_db
from app.models.user import User
from app.utils.security import get_current_active_user
from app.services.search_service import SearchService

router = APIRouter()


@router.get("/templates")
async def search_templates(
    query: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
    rating: Optional[float] = Query(None, ge=1, le=5, description="Minimum rating filter"),
    language: Optional[str] = Query(None, description="Filter by language"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    sort_by: str = Query("relevance", description="Sort by: relevance, price_low, price_high, rating, popularity, newest"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Advanced template search with full-text search and ranking"""

    search_results = SearchService.search_templates(
        db, query, current_user.id, category, min_price, max_price,
        rating, language, tags, sort_by, page, per_page
    )

    return search_results


@router.get("/documents")
async def search_documents(
    query: str = Query(..., min_length=1, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by document status"),
    template_id: Optional[int] = Query(None, description="Filter by template ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    sort_by: str = Query("relevance", description="Sort by: relevance, created_at, updated_at, title, status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Advanced document search for user's documents"""

    search_results = SearchService.search_documents(
        db, current_user.id, query, status, template_id,
        start_date, end_date, sort_by, page, per_page
    )

    return search_results


@router.get("/recommendations")
async def get_search_recommendations(
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get personalized search recommendations"""

    recommendations = SearchService.get_search_recommendations(db, current_user.id, limit)
    return recommendations


@router.get("/analytics")
async def get_search_analytics(
    days: int = Query(30, ge=1, le=365, description="Number of days for analytics"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get search analytics for the user"""

    analytics = SearchService.get_search_analytics(db, current_user.id, days)
    return analytics


@router.get("/global/analytics")
async def get_global_search_analytics(
    days: int = Query(30, ge=1, le=365, description="Number of days for analytics"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get global search analytics (admin only)"""

    # Admin permission check
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin access required for search analytics"
        )

    analytics = SearchService.get_search_analytics(db, None, days)
    return analytics
