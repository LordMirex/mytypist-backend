"""
Unified Visit Models for Analytics
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, JSON
from sqlalchemy.orm import relationship, declared_attr
from sqlalchemy.sql import func

from database import Base


class BaseVisit(Base):
    """Base visit tracking model with common fields for all visit types"""
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)

    # Core visitor tracking
    session_id = Column(String(100), nullable=False, index=True)
    device_fingerprint = Column(String(64), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Enhanced device info
    browser_name = Column(String(100), nullable=True)
    browser_version = Column(String(50), nullable=True)
    os_name = Column(String(100), nullable=True)
    os_version = Column(String(50), nullable=True)
    device_type = Column(String(50), nullable=True)  # mobile, tablet, desktop
    screen_resolution = Column(String(50), nullable=True)

    # Traffic source and campaign tracking
    referrer = Column(String(500), nullable=True)
    referrer_domain = Column(String(255), nullable=True, index=True)
    utm_source = Column(String(100), nullable=True, index=True)
    utm_medium = Column(String(100), nullable=True, index=True)
    utm_campaign = Column(String(100), nullable=True, index=True)
    utm_term = Column(String(100), nullable=True)
    utm_content = Column(String(100), nullable=True)

    # Geo-location data
    country = Column(String(2), nullable=True, index=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    timezone = Column(String(50), nullable=True)

    # Core metrics
    duration = Column(Integer, nullable=True)  # seconds
    bounce = Column(Boolean, default=True)  # True if left without meaningful interaction
    bounce_type = Column(String(20), nullable=True)  # quick, normal, delayed

    # Engagement metrics
    time_on_page_seconds = Column(Integer, default=0)
    active_time_seconds = Column(Integer, default=0)  # Time with active interactions
    scroll_depth = Column(Integer, default=0)  # Maximum scroll percentage
    clicks_count = Column(Integer, default=0)  # Total click interactions
    session_quality_score = Column(Float, default=0)  # Calculated engagement score
    engagement_depth = Column(Integer, default=0)  # How deep into the funnel

    # A/B Testing
    ab_test_group = Column(String(50), nullable=True, index=True)
    ab_test_variant = Column(String(50), nullable=True)
    ab_test_performance = Column(Float, default=0)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), index=True)
    last_interaction_at = Column(DateTime, nullable=True)

    # Additional data
    visit_metadata = Column(JSON, nullable=True)  # For extensible properties


class DocumentVisit(BaseVisit):
    """Visit tracking for document views and interactions"""
    __tablename__ = "document_visits"

    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    document = relationship("Document", back_populates="visits")
    visit_type = Column(String(20), nullable=False, default="view")  # view, download, share

    # Document-specific tracking
    download_completed = Column(Boolean, default=False)
    time_reading = Column(Integer, default=0)  # Time spent actually reading
    scroll_coverage = Column(Float, default=0)  # % of document scrolled
    interactions = Column(JSON, nullable=True)  # Clicks, highlights, etc.


class LandingVisit(BaseVisit):
    """Enhanced tracking for landing page visits and conversions"""
    __tablename__ = "landing_visits"

    # Page tracking
    entry_page = Column(String(500), nullable=True)
    exit_page = Column(String(500), nullable=True)
    pages_viewed = Column(JSON, nullable=True)  # Array of viewed pages with timestamps

    # Template interaction tracking
    viewed_templates = Column(JSON, nullable=True)  # Array of {template_id, timestamp, view_duration}
    searched_terms = Column(JSON, nullable=True)  # Array of {term, timestamp, results_count}
    template_interactions = Column(JSON, nullable=True)  # Array of {template_id, action_type, timestamp}
    templates_viewed_count = Column(Integer, default=0)
    searches_performed = Column(Integer, default=0)

    # Form interaction tracking
    form_interactions = Column(JSON, nullable=True)  # Array of {field_id, action, timestamp}
    form_completion = Column(Float, default=0)
    form_abandonment = Column(Boolean, default=False)
    last_interaction_field = Column(String(100), nullable=True)

    # Conversion funnel
    funnel_stage = Column(String(50), nullable=True, index=True)
    created_document = Column(Boolean, default=False)
    registered = Column(Boolean, default=False)
    downloaded_document = Column(Boolean, default=False)
    converted_to_paid = Column(Boolean, default=False)
    conversion_probability = Column(Float, default=0)


class PageVisit(BaseVisit):
    """General page visit tracking for the admin dashboard"""
    __tablename__ = "page_visits"

    path = Column(String(500), nullable=False)
    query_params = Column(JSON, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="page_visits")

    # Page-specific metrics
    page_load_time = Column(Integer, nullable=True)  # milliseconds
    dom_interactive_time = Column(Integer, nullable=True)
    first_paint_time = Column(Integer, nullable=True)
    navigation_type = Column(String(20), nullable=True)  # navigate, reload, back_forward
    was_cached = Column(Boolean, default=False)
