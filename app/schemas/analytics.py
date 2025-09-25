"""
Analytics Schemas
Pydantic models for analytics data validation
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, validator
from enum import Enum

class TimePeriod(str, Enum):
    """Time period for analytics queries"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"

class EventType(str, Enum):
    PAGE_VIEW = "page_view"
    TEMPLATE_INTERACTION = "template_interaction"
    FORM_INTERACTION = "form_interaction"
    SCROLL = "scroll"
    CONVERSION = "conversion"

class BaseEventData(BaseModel):
    """Base model for all event data"""
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    session_id: str = Field(..., description="Unique session identifier")
    client_id: Optional[str] = Field(None, description="Client-side generated ID")
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    referrer: Optional[str] = None
    
    @validator('session_id')
    def validate_session_id(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Invalid session ID')
        return v

class PageViewData(BaseEventData):
    """Data specific to page view events"""
    page: str = Field(..., description="Page URL or identifier")
    time_on_page: Optional[int] = Field(0, description="Time spent on page in seconds")
    entry_point: Optional[bool] = Field(False, description="Whether this is the first page")
    exit_point: Optional[bool] = Field(False, description="Whether this is the last page")

class TemplateInteractionData(BaseEventData):
    """Data specific to template interaction events"""
    template_id: str = Field(..., description="Template identifier")
    action: str = Field(..., description="Action performed on template")
    duration: Optional[int] = Field(0, description="Duration of interaction in seconds")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class FormInteractionData(BaseEventData):
    """Data specific to form interaction events"""
    field_id: str = Field(..., description="Form field identifier")
    action: str = Field(..., description="Action performed on field")
    form_completion: Optional[float] = Field(0.0, description="Form completion percentage")
    validation_status: Optional[bool] = None

class ScrollData(BaseEventData):
    """Data specific to scroll events"""
    scroll_depth: float = Field(..., ge=0, le=100, description="Scroll depth percentage")
    time_to_depth: Optional[int] = Field(None, description="Time to reach depth in seconds")

class ConversionData(BaseEventData):
    """Data specific to conversion events"""
    conversion_type: str = Field(..., description="Type of conversion")
    value: Optional[float] = Field(None, description="Conversion value if applicable")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class EventData(BaseModel):
    """Combined event data model"""
    event_type: EventType
    data: Dict[str, Any] = Field(..., description="Event specific data")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @validator('data')
    def validate_event_data(cls, v, values):
        event_type = values.get('event_type')
        if event_type == EventType.PAGE_VIEW:
            PageViewData(**v)
        elif event_type == EventType.TEMPLATE_INTERACTION:
            TemplateInteractionData(**v)
        elif event_type == EventType.FORM_INTERACTION:
            FormInteractionData(**v)
        elif event_type == EventType.SCROLL:
            ScrollData(**v)
        elif event_type == EventType.CONVERSION:
            ConversionData(**v)
        return v

class AnalyticsResponse(BaseModel):
    """Standard response model for analytics endpoints"""
    success: bool
    event_tracked: Optional[bool] = None
    session_quality_score: Optional[float] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class RealtimeMetrics(BaseModel):
    """Model for real-time analytics metrics"""
    timestamp: datetime
    active_sessions: int
    conversions_per_minute: int
    page_views_per_minute: int
    top_active_templates: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None
