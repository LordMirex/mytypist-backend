"""Tests for realtime analytics service"""
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.services.realtime_analytics_service import RealtimeAnalyticsService
from app.services.cache_service import CacheService
from app.models.user import User
from app.models.template import Template
from app.services.landing_page_service import LandingPageVisit, LandingPageTemplate

@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)

@pytest.fixture
def mock_cache():
    return MagicMock(spec=CacheService)

@pytest.mark.asyncio
async def test_track_user_interaction_success(mock_db):
    """Test successful tracking of user interaction"""
    # Setup
    session_id = "test_session_123"
    event_type = "page_view"
    event_data = {
        "page": "landing",
        "time_on_page": 30,
        "user_agent": "test_agent"
    }
    
    mock_visit = MagicMock(spec=LandingPageVisit)
    mock_visit.session_quality_score = 5.0
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_visit
    
    # Execute
    result = await RealtimeAnalyticsService.track_user_interaction(
        db=mock_db,
        session_id=session_id,
        event_type=event_type,
        event_data=event_data
    )
    
    # Assert
    assert result["success"] is True
    assert result["event_tracked"] is True
    assert result["session_quality_score"] == 5.0
    mock_db.commit.assert_called_once()

@pytest.mark.asyncio
async def test_track_user_interaction_rate_limit(mock_db):
    """Test rate limiting for user interactions"""
    # Setup
    session_id = "test_session_123"
    event_type = "page_view"
    event_data = {"page": "landing"}
    
    with patch('app.services.realtime_analytics_service.CacheService') as mock_cache:
        mock_cache.incr.return_value = 101  # Over rate limit
        
        # Execute
        result = await RealtimeAnalyticsService.track_user_interaction(
            db=mock_db,
            session_id=session_id,
            event_type=event_type,
            event_data=event_data
        )
        
        # Assert
        assert result["success"] is False
        assert result["error"] == "rate_limit_exceeded"

@pytest.mark.asyncio
async def test_get_realtime_metrics(mock_db):
    """Test getting realtime metrics"""
    # Setup
    current_time = datetime.utcnow()
    last_minute = current_time - timedelta(minutes=1)
    
    mock_db.query.return_value.filter.return_value.count.return_value = 10
    mock_db.query.return_value.filter.return_value.scalar.return_value = 100
    
    mock_templates = [
        MagicMock(template_id=1, active_viewers=50),
        MagicMock(template_id=2, active_viewers=30)
    ]
    mock_db.query.return_value.join.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = mock_templates
    
    # Execute
    result = await RealtimeAnalyticsService.get_realtime_metrics(db=mock_db)
    
    # Assert
    assert result["active_sessions"] == 10
    assert result["conversions_per_minute"] == 10
    assert result["page_views_per_minute"] == 100
    assert len(result["top_active_templates"]) == 2
    assert result["top_active_templates"][0]["active_viewers"] == 50

@pytest.mark.asyncio
async def test_calculate_session_quality():
    """Test session quality score calculation"""
    visit = MagicMock(spec=LandingPageVisit)
    visit.templates_viewed_count = 5
    visit.time_on_page_seconds = 300
    visit.scroll_depth = 80
    visit.form_completion = 0.5
    visit.created_document = True
    visit.registered = True
    visit.downloaded_document = False
    visit.converted_to_paid = False
    
    score = RealtimeAnalyticsService._calculate_session_quality(visit)
    
    # Assert score components
    assert score > 0
    assert score <= 10.0  # Max score cap

def test_track_page_view():
    """Test tracking page view interaction"""
    visit = MagicMock(spec=LandingPageVisit)
    visit.pages_viewed = "[]"
    
    data = {
        "page": "landing",
        "time_on_page": 60
    }
    
    RealtimeAnalyticsService._track_page_view(visit, data)
    
    pages = json.loads(visit.pages_viewed)
    assert len(pages) == 1
    assert pages[0]["page"] == "landing"
    assert pages[0]["time_on_page"] == 60

def test_track_template_interaction():
    """Test tracking template interaction"""
    visit = MagicMock(spec=LandingPageVisit)
    visit.template_interactions = "[]"
    visit.templates_viewed_count = 0
    
    data = {
        "template_id": 1,
        "action": "view",
        "duration": 30
    }
    
    RealtimeAnalyticsService._track_template_interaction(visit, data)
    
    interactions = json.loads(visit.template_interactions)
    assert len(interactions) == 1
    assert interactions[0]["template_id"] == 1
    assert interactions[0]["action"] == "view"
    assert visit.templates_viewed_count == 1

def test_track_form_interaction():
    """Test tracking form interaction"""
    visit = MagicMock(spec=LandingPageVisit)
    visit.form_interactions = "[]"
    
    data = {
        "field_id": "email",
        "action": "focus",
        "form_completion": 0.5
    }
    
    RealtimeAnalyticsService._track_form_interaction(visit, data)
    
    interactions = json.loads(visit.form_interactions)
    assert len(interactions) == 1
    assert interactions[0]["field_id"] == "email"
    assert visit.form_completion == 0.5

@pytest.mark.asyncio
async def test_update_realtime_metrics():
    """Test updating realtime metrics cache"""
    with patch('app.services.realtime_analytics_service.CacheService') as mock_cache:
        mock_cache.get.return_value = '{"page_view": 5}'
        
        await RealtimeAnalyticsService._update_realtime_metrics(
            db=MagicMock(),
            event_type="page_view",
            event_data={"template_id": 1}
        )
        
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args[0]
        updated_data = json.loads(call_args[1])
        assert updated_data["page_view"] == 6
