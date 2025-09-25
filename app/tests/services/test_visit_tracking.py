"""
Tests for the unified VisitTrackingService
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from fastapi import Request

from app.models.document import Document
from app.models.template import Template
from app.models.analytics.visit import DocumentVisit, LandingVisit, PageVisit
from app.services.analytics.visit_tracking import VisitTrackingService
from app.services.cache_service import CacheService


@pytest.fixture
def mock_cache_service():
    """Mock cache service for testing"""
    cache = Mock(spec=CacheService)
    cache.get.return_value = None
    cache.set.return_value = True
    return cache


@pytest.fixture
def tracking_service(mock_cache_service):
    """Create VisitTrackingService instance with mocked cache"""
    return VisitTrackingService(cache_service=mock_cache_service)


@pytest.fixture
def mock_request():
    """Create a mock request with typical headers"""
    request = Mock(spec=Request)
    request.client.host = "192.168.1.1"
    request.headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124",
        "referer": "https://example.com/landing",
    }
    return request


def test_enrich_visit_data(tracking_service, mock_request):
    """Test visit data enrichment with device detection"""
    request_data = {
        "ip_address": mock_request.client.host,
        "user_agent": mock_request.headers["user-agent"],
        "referrer": mock_request.headers["referer"]
    }
    
    enriched = tracking_service.enrich_visit_data(request_data)
    
    assert enriched["browser_name"] == "Chrome"
    assert enriched["device_type"] == "desktop"
    assert enriched["referrer_domain"] == "example.com"
    assert "created_at" in enriched


def test_track_document_visit(tracking_service, mock_request):
    """Test document visit tracking with analytics"""
    db = Mock(spec=Session)
    document_id = 123
    visit_type = "view"
    
    # Mock document query
    db.query.return_value.filter.return_value.first.return_value = Mock(
        Document, id=document_id
    )
    
    visit = tracking_service.track_document_visit(db, document_id, visit_type, mock_request)
    
    assert visit.document_id == document_id
    assert visit.visit_type == visit_type
    assert not visit.bounce  # Should not be marked as bounce initially
    assert visit.browser_name == "Chrome"
    assert visit.device_type == "desktop"
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_process_document_analytics(tracking_service):
    """Test analytics processing for document visits"""
    # Create test visits
    visits = [
        DocumentVisit(
            document_id=1,
            browser_name="Chrome",
            device_type="desktop",
            os_name="Windows",
            session_quality_score=0.8,
            active_time_seconds=300,
            bounce=False,
            ip_address="192.168.1.1"
        ),
        DocumentVisit(
            document_id=1,
            browser_name="Safari",
            device_type="mobile",
            os_name="iOS",
            session_quality_score=0.4,
            active_time_seconds=60,
            bounce=True,
            ip_address="192.168.1.2"
        )
    ]
    
    analytics = tracking_service.process_document_analytics(visits)
    
    assert analytics["total_visits"] == 2
    assert analytics["unique_visitors"] == 2
    assert analytics["bounce_rate"] == 0.5  # 1 out of 2 visits bounced
    assert analytics["avg_session_quality"] == 0.6  # (0.8 + 0.4) / 2
    assert analytics["avg_active_time"] == 180  # (300 + 60) / 2
    assert "Chrome" in analytics["browser_stats"]
    assert "Safari" in analytics["browser_stats"]
    assert "desktop" in analytics["device_stats"]
    assert "mobile" in analytics["device_stats"]


@pytest.mark.asyncio
async def test_dashboard_analytics(tracking_service):
    """Test dashboard analytics generation"""
    db = Mock(spec=Session)
    user_id = 456
    
    # Mock document queries
    db.query.return_value.filter.return_value.count.return_value = 10
    
    # Mock visit queries with sample data
    visits_query = db.query.return_value.join.return_value.filter.return_value
    visits_query.count.return_value = 100
    
    # Mock top documents query
    top_docs = [Mock(id=1, title="Doc 1", visit_count=50),
                Mock(id=2, title="Doc 2", visit_count=30)]
    db.query.return_value.join.return_value.filter.return_value\
        .group_by.return_value.order_by.return_value.limit.return_value.all\
        .return_value = top_docs
    
    # Mock template usage query
    template_usage = [Mock(id=1, name="Template 1", usage_count=20),
                     Mock(id=2, name="Template 2", usage_count=15)]
    db.query.return_value.join.return_value.filter.return_value\
        .group_by.return_value.order_by.return_value.limit.return_value.all\
        .return_value = template_usage
    
    dashboard = tracking_service.get_dashboard_analytics(db, user_id)
    
    assert dashboard["overview"]["total_documents"] == 10
    assert dashboard["overview"]["total_visits"] == 100
    assert len(dashboard["top_documents"]) == 2
    assert len(dashboard["template_usage"]) == 2
    assert dashboard["top_documents"][0]["visits"] == 50
    assert dashboard["template_usage"][0]["usage_count"] == 20


def test_calculate_session_quality(tracking_service):
    """Test session quality score calculation"""
    visit = DocumentVisit(
        bounce=False,
        active_time_seconds=300,  # 5 minutes
        clicks_count=15,
        scroll_depth=80
    )
    
    score = tracking_service._calculate_session_quality(visit)
    
    assert 0 <= score <= 1  # Score should be normalized
    assert score > 0.5  # Good engagement should have high score


def test_anonymize_user_analytics(tracking_service):
    """Test analytics data anonymization"""
    db = Mock(spec=Session)
    user_id = 789
    
    visits = [
        DocumentVisit(
            document_id=1,
            ip_address="192.168.1.1",
            user_agent="Chrome",
            device_fingerprint="abc123",
            city="New York",
            metadata={"user_data": "sensitive"}
        ),
        DocumentVisit(
            document_id=2,
            ip_address="192.168.1.2",
            user_agent="Safari",
            device_fingerprint="def456",
            city="London",
            metadata={"user_data": "private"}
        )
    ]
    
    db.query.return_value.join.return_value.filter.return_value.all.return_value = visits
    
    count = tracking_service.anonymize_user_analytics(db, user_id)
    
    assert count == 2
    for visit in visits:
        assert visit.ip_address == "XXX.XXX.XXX.XXX"
        assert visit.user_agent == "[ANONYMIZED]"
        assert visit.device_fingerprint == "[ANONYMIZED]"
        assert visit.city is None
        assert visit.metadata == {"anonymized": True}
    
    db.commit.assert_called_once()


def test_export_analytics_data(tracking_service):
    """Test analytics data export in different formats"""
    db = Mock(spec=Session)
    user_id = 101
    document_id = 1
    days = 30
    
    visits = [
        DocumentVisit(
            id=1,
            document_id=document_id,
            visit_type="view",
            country="US",
            city="New York",
            device_type="desktop",
            browser_name="Chrome",
            os_name="Windows",
            created_at=datetime.utcnow(),
            time_reading=300,
            bounce=False,
            device_fingerprint="abc123",
            metadata={"source": "direct"}
        )
    ]
    
    db.query.return_value.join.return_value.filter.return_value.all.return_value = visits
    
    # Test CSV export
    csv_data = tracking_service.export_analytics_data(db, user_id, document_id, days, "csv")
    assert csv_data["format"] == "csv"
    assert len(csv_data["data"]) == 1
    assert csv_data["data"][0]["visit_id"] == 1
    assert csv_data["data"][0]["document_id"] == document_id
    
    # Test JSON export
    json_data = tracking_service.export_analytics_data(db, user_id, document_id, days, "json")
    assert json_data["format"] == "json"
    assert len(json_data["visits"]) == 1
    assert json_data["visits"][0]["visit_id"] == 1
    assert "visitor_info" in json_data["visits"][0]
    assert "engagement" in json_data["visits"][0]