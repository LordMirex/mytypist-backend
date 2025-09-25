"""
Validation tests for analytics metrics calculations
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.models.analytics.visit import DocumentVisit, LandingVisit, PageVisit
from app.services.analytics.visit_tracking import VisitTrackingService
from app.services.cache_service import CacheService


def create_test_visits():
    """Create a set of test visits with known metrics for validation"""
    now = datetime.utcnow()
    return [
        # Regular engaged visit
        DocumentVisit(
            document_id=1,
            created_at=now - timedelta(hours=2),
            first_interaction_at=now - timedelta(hours=2),
            last_interaction_at=now - timedelta(hours=1),
            active_time_seconds=3600,
            clicks_count=20,
            scroll_depth=90,
            bounce=False,
            device_type="desktop",
            browser_name="Chrome",
            os_name="Windows",
            session_quality_score=0.85
        ),
        # Bounced visit
        DocumentVisit(
            document_id=1,
            created_at=now - timedelta(hours=1),
            first_interaction_at=now - timedelta(hours=1),
            last_interaction_at=now - timedelta(hours=1),
            active_time_seconds=5,
            clicks_count=0,
            scroll_depth=10,
            bounce=True,
            device_type="mobile",
            browser_name="Safari",
            os_name="iOS",
            session_quality_score=0.1
        ),
        # Medium engagement visit
        DocumentVisit(
            document_id=1,
            created_at=now - timedelta(minutes=30),
            first_interaction_at=now - timedelta(minutes=30),
            last_interaction_at=now - timedelta(minutes=10),
            active_time_seconds=1200,
            clicks_count=8,
            scroll_depth=60,
            bounce=False,
            device_type="desktop",
            browser_name="Firefox",
            os_name="macOS",
            session_quality_score=0.6
        )
    ]


def test_session_quality_score_validation(tracking_service):
    """Validate session quality score calculation"""
    visits = create_test_visits()
    
    # Test individual components of quality score
    for visit in visits:
        score = tracking_service._calculate_session_quality(visit)
        
        # Base engagement factor (0.3 for non-bounce)
        base_score = 0.3 if not visit.bounce else 0.0
        
        # Time factor (0.3 max for 5+ minutes)
        time_factor = min(visit.active_time_seconds / 300, 1.0) * 0.3
        
        # Click factor (0.2 max for 10+ clicks)
        click_factor = min(visit.clicks_count / 10, 1.0) * 0.2
        
        # Scroll factor (0.2 max for 100% scroll)
        scroll_factor = (visit.scroll_depth / 100) * 0.2
        
        expected_score = min(base_score + time_factor + click_factor + scroll_factor, 1.0)
        assert abs(score - expected_score) < 0.01, f"Score {score} doesn't match expected {expected_score}"


def test_bounce_rate_calculation_validation(tracking_service):
    """Validate bounce rate calculation"""
    visits = create_test_visits()
    analytics = tracking_service.process_document_analytics(visits)
    
    # We know one out of three visits is a bounce
    expected_bounce_rate = 1/3
    assert abs(analytics["bounce_rate"] - expected_bounce_rate) < 0.01


def test_engagement_metrics_validation(tracking_service):
    """Validate engagement metrics calculations"""
    visits = create_test_visits()
    analytics = tracking_service.process_document_analytics(visits)
    
    # Average active time
    total_time = sum(v.active_time_seconds for v in visits)
    expected_avg_time = total_time / len(visits)
    assert abs(analytics["avg_active_time"] - expected_avg_time) < 1
    
    # Average session quality
    total_quality = sum(v.session_quality_score for v in visits)
    expected_avg_quality = total_quality / len(visits)
    assert abs(analytics["avg_session_quality"] - expected_avg_quality) < 0.01


def test_device_browser_stats_validation(tracking_service):
    """Validate device and browser statistics calculations"""
    visits = create_test_visits()
    analytics = tracking_service.process_document_analytics(visits)
    
    # Device stats (2 desktop, 1 mobile)
    assert abs(analytics["device_stats"]["desktop"] - 0.667) < 0.01
    assert abs(analytics["device_stats"]["mobile"] - 0.333) < 0.01
    
    # Browser stats (1 each of Chrome, Safari, Firefox)
    for browser in ["Chrome", "Safari", "Firefox"]:
        assert abs(analytics["browser_stats"][browser] - 0.333) < 0.01


def test_growth_calculation_validation(tracking_service):
    """Validate growth rate calculations"""
    test_cases = [
        (100, 50, 100.0),    # 100% growth
        (50, 100, -50.0),    # 50% decline
        (100, 0, 100.0),     # From zero
        (0, 100, -100.0),    # To zero
        (0, 0, 0.0),         # Zero to zero
        (150, 100, 50.0),    # 50% growth
    ]
    
    for current, previous, expected in test_cases:
        growth = tracking_service._calculate_growth(current, previous)
        assert abs(growth - expected) < 0.01


@pytest.mark.asyncio
async def test_dashboard_metrics_validation(tracking_service):
    """Validate dashboard metrics calculations"""
    db = Mock(spec=Session)
    user_id = 123
    
    # Create test data
    now = datetime.utcnow()
    today = now.date()
    yesterday = today - timedelta(days=1)
    
    # Mock document counts
    db.query.return_value.filter.return_value.count.side_effect = [
        100,  # total_documents
        5,    # documents_today
        25    # documents_this_week
    ]
    
    # Mock visit counts
    visits_query = db.query.return_value.join.return_value.filter.return_value
    visits_query.count.side_effect = [
        1000,  # total_visits
        80,    # visits_today
        50     # visits_yesterday
    ]
    
    dashboard = tracking_service.get_dashboard_analytics(db, user_id)
    
    # Validate counts
    assert dashboard["overview"]["total_documents"] == 100
    assert dashboard["overview"]["documents_today"] == 5
    assert dashboard["overview"]["documents_this_week"] == 25
    assert dashboard["overview"]["total_visits"] == 1000
    assert dashboard["overview"]["visits_today"] == 80
    
    # Validate growth calculation
    expected_growth = tracking_service._calculate_growth(80, 50)  # today vs yesterday
    assert abs(dashboard["overview"]["visit_growth"] - expected_growth) < 0.01


def test_data_anonymization_validation(tracking_service):
    """Validate data anonymization process"""
    db = Mock(spec=Session)
    user_id = 123
    visits = create_test_visits()
    
    # Add sensitive data to visits
    for visit in visits:
        visit.ip_address = "192.168.1.1"
        visit.city = "New York"
        visit.latitude = 40.7128
        visit.longitude = -74.0060
        visit.device_fingerprint = "abc123"
        visit.metadata = {"user_info": "sensitive"}
    
    db.query.return_value.join.return_value.filter.return_value.all.return_value = visits
    
    # Run anonymization
    count = tracking_service.anonymize_user_analytics(db, user_id)
    
    assert count == len(visits)
    for visit in visits:
        # Check all sensitive fields are properly anonymized
        assert visit.ip_address == "XXX.XXX.XXX.XXX"
        assert visit.city is None
        assert visit.latitude is None
        assert visit.longitude is None
        assert visit.device_fingerprint == "[ANONYMIZED]"
        assert visit.metadata == {"anonymized": True}
        
        # Verify non-sensitive analytics are preserved
        assert isinstance(visit.active_time_seconds, (int, float))
        assert isinstance(visit.session_quality_score, float)
        assert isinstance(visit.bounce, bool)