"""
Test admin dashboard business intelligence metrics
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.services.admin_dashboard_service import AdminDashboardService
from app.models.user import User
from app.models.payment import Payment, Subscription
from app.models.page_visit import PageVisit
from app.models.template import Template
from app.models.document import Document

@pytest.fixture
def test_data(db: Session):
    """Create test data for BI metrics"""
    # Create test users
    users = [
        User(
            email=f"user{i}@test.com",
            password="test",
            is_active=True
        ) for i in range(5)
    ]
    db.add_all(users)
    db.commit()
    
    # Create visits
    now = datetime.utcnow()
    visits = []
    for user in users:
        for day in range(7):
            visits.append(PageVisit(
                user_id=user.id,
                url="/test",
                created_at=now - timedelta(days=day),
                time_on_page_seconds=60
            ))
    db.add_all(visits)
    
    # Create payments
    payments = [
        Payment(
            user_id=users[0].id,
            amount=100,
            status="completed",
            created_at=now - timedelta(days=1)
        ),
        Payment(
            user_id=users[1].id,
            amount=200,
            status="completed",
            created_at=now - timedelta(days=2)
        )
    ]
    db.add_all(payments)
    
    # Create subscription
    subscription = Subscription(
        user_id=users[0].id,
        status="active",
        monthly_amount=50,
        created_at=now - timedelta(days=30)
    )
    db.add(subscription)
    
    db.commit()
    return users

@pytest.mark.asyncio
async def test_retention_metrics(db: Session, test_data):
    """Test retention metrics calculation"""
    now = datetime.utcnow()
    retention = await AdminDashboardService.calculate_retention_metrics(db, now)
    
    assert retention.daily is not None
    assert retention.weekly is not None
    assert retention.monthly is not None
    
    # Check daily retention
    for date, metrics in retention.daily.items():
        assert 'new_users' in metrics
        assert 'retention' in metrics
        assert isinstance(metrics['retention'], dict)

@pytest.mark.asyncio
async def test_cohort_analysis(db: Session, test_data):
    """Test cohort analysis"""
    now = datetime.utcnow()
    start_date = now - timedelta(days=30)
    
    cohorts = await AdminDashboardService.get_cohort_analysis(db, start_date, now)
    
    assert isinstance(cohorts, dict)
    for date, metrics in cohorts.items():
        assert 'size' in metrics
        assert 'conversion_rate' in metrics
        assert 'retention' in metrics
        assert 'revenue' in metrics

@pytest.mark.asyncio
async def test_revenue_metrics(db: Session, test_data):
    """Test revenue metrics calculation"""
    now = datetime.utcnow()
    start_time = now - timedelta(days=7)
    end_time = now
    
    metrics = await AdminDashboardService._calculate_revenue_metrics(db, start_time, end_time)
    
    assert 'total_revenue' in metrics
    assert 'product_revenue' in metrics
    assert 'subscription_metrics' in metrics
    assert 'customer_value' in metrics
    
    sub_metrics = metrics['subscription_metrics']
    assert 'active_subscriptions' in sub_metrics
    assert 'mrr' in sub_metrics

@pytest.mark.asyncio
async def test_business_metrics(db: Session, test_data):
    """Test business metrics calculation"""
    now = datetime.utcnow()
    start_time = now - timedelta(days=7)
    end_time = now
    
    metrics = await AdminDashboardService._calculate_business_metrics(db, start_time, end_time)
    
    assert 'engagement' in metrics
    assert 'templates' in metrics
    assert 'documents' in metrics
    
    engagement = metrics['engagement']
    assert 'active_users' in engagement
    assert 'average_session_duration' in engagement
    assert 'bounce_rate' in engagement

@pytest.mark.asyncio
async def test_daily_summary_with_bi(db: Session, test_data):
    """Test daily summary with new BI metrics"""
    now = datetime.utcnow()
    summary = await AdminDashboardService.get_daily_summary(db, now)
    
    assert summary is not None
    # Verify new BI metrics are included
    assert 'retention' in summary
    assert 'revenue' in summary
    assert 'business_metrics' in summary