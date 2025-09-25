"""
Test Landing Page Service
Tests for enhanced analytics functionality
"""

import json
from datetime import datetime, timedelta
import pytest
from sqlalchemy.orm import Session
from app.services.landing_page_service import LandingPageVisit
from app.services.realtime_analytics_service import RealtimeAnalyticsService

def test_calculate_active_time():
    """Test active time calculation"""
    now = datetime.utcnow()
    last_interaction = now - timedelta(seconds=30)
    active_time = RealtimeAnalyticsService._calculate_active_time(100, last_interaction, now)
    assert active_time == 130  # Previous 100 seconds + 30 seconds gap

    # Test with long gap (should not add time)
    last_interaction = now - timedelta(minutes=10)
    active_time = RealtimeAnalyticsService._calculate_active_time(100, last_interaction, now)
    assert active_time == 100

def test_classify_bounce_type():
    """Test bounce type classification"""
    now = datetime.utcnow()
    
    # Test quick bounce
    created = now - timedelta(seconds=5)
    assert RealtimeAnalyticsService._classify_bounce_type(created, now, 0) == "quick"
    
    # Test normal bounce
    created = now - timedelta(seconds=20)
    assert RealtimeAnalyticsService._classify_bounce_type(created, now, 1) == "normal"
    
    # Test delayed bounce
    created = now - timedelta(minutes=5)
    assert RealtimeAnalyticsService._classify_bounce_type(created, now, 1) == "delayed"

def test_calculate_conversion_probability():
    """Test conversion probability calculation"""
    # Test with no interactions
    prob = RealtimeAnalyticsService._calculate_conversion_probability(2, 0.5, None)
    assert 0 <= prob <= 1.0
    
    # Test with interactions
    interactions = json.dumps([
        {"template_id": 1, "action": "view", "timestamp": "2025-09-14T10:00:00"},
        {"template_id": 2, "action": "click", "timestamp": "2025-09-14T10:01:00"}
    ])
    prob = RealtimeAnalyticsService._calculate_conversion_probability(2, 0.5, interactions)
    assert prob > 0.5  # Should be higher with interactions

@pytest.mark.asyncio
async def test_track_user_interaction(db: Session):
    """Test enhanced user interaction tracking"""
    session_id = "test_session"
    event_type = "page_view"
    event_data = {
        "url": "/landing",
        "duration": 30
    }
    
    result = await RealtimeAnalyticsService.track_user_interaction(
        db=db,
        session_id=session_id,
        event_type=event_type,
        event_data=event_data
    )
    
    assert result["success"] is True
    
    visit = db.query(LandingPageVisit).filter(
        LandingPageVisit.session_id == session_id
    ).first()
    
    assert visit is not None
    assert visit.bounce is False
    assert visit.bounce_type in ["quick", "normal", "delayed"]
    assert visit.conversion_probability >= 0
    assert visit.active_time_seconds >= 0