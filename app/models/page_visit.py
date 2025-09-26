"""
Page Visit Model
Tracks page visits and user interactions for analytics
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from database import Base


class PageVisit(Base):
    """Page visit tracking model"""
    __tablename__ = "page_visits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    page_url = Column(String(500), nullable=False)
    page_title = Column(String(200), nullable=True)
    referrer = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    visit_duration = Column(Integer, nullable=True)  # seconds
    metadata = Column(JSON, nullable=True)  # Additional visit data
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)

    def __repr__(self):
        return f"<PageVisit(id={self.id}, url={self.page_url}, session={self.session_id})>"
