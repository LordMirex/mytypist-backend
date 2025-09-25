"""
Real-time Analytics Routes
Handles real-time analytics tracking and reporting endpoints
"""

from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.dependencies import get_db, rate_limit, validate_analytics_request
from app.services.realtime_analytics_service import RealtimeAnalyticsService
from app.middleware.security import SecurityHeaders
from app.schemas.analytics import EventData

router = APIRouter(
    prefix="/api/analytics/realtime",
    tags=["analytics"],
    dependencies=[Depends(SecurityHeaders)]
)

@router.post("/track", 
    response_model=Dict[str, Any],
    dependencies=[
        Depends(rate_limit),
        Depends(validate_analytics_request)
    ]
)
async def track_interaction(
    event_data: EventData,
    session_id: str,
    db: Session = Depends(get_db),
    timestamp: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Track real-time user interaction
    """
    try:
        result = await RealtimeAnalyticsService.track_user_interaction(
            db=db,
            session_id=session_id,
            event_type=event_data.event_type,
            event_data=event_data.dict(),
            timestamp=timestamp
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/metrics",
    response_model=Dict[str, Any],
    dependencies=[Depends(rate_limit)]
)
async def get_realtime_metrics(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get real-time analytics metrics
    """
    try:
        return await RealtimeAnalyticsService.get_realtime_metrics(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
