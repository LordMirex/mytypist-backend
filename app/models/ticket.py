"""Support ticket system models"""

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Enum, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class TicketPriority(str, enum.Enum):
    """Ticket priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(str, enum.Enum):
    """Ticket status states"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting_for_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketCategory(str, enum.Enum):
    """Ticket categories"""
    TECHNICAL = "technical"
    BILLING = "billing"
    FEATURE = "feature_request"
    DOCUMENT = "document_issue"
    ACCOUNT = "account"
    OTHER = "other"


class Ticket(Base):
    """Support ticket model"""
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(Enum(TicketCategory), nullable=False)
    priority = Column(Enum(TicketPriority), nullable=False, default=TicketPriority.MEDIUM)
    status = Column(Enum(TicketStatus), nullable=False, default=TicketStatus.OPEN)

    # User information (can be null for guest tickets)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="tickets")
    guest_email = Column(String(255), nullable=True)
    guest_session_id = Column(String(36), nullable=True)

    # Related entities
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    document = relationship("Document")
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    template = relationship("Template")

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    ticket_metadata = Column(JSON, nullable=True)
    
    # System info for debugging
    browser_info = Column(JSON, nullable=True)
    error_details = Column(JSON, nullable=True)

    # Response tracking
    first_response_at = Column(DateTime(timezone=True), nullable=True)
    last_response_at = Column(DateTime(timezone=True), nullable=True)
    response_time_seconds = Column(Integer, nullable=True)

    # Relations
    responses = relationship("TicketResponse", back_populates="ticket", cascade="all, delete-orphan")


class TicketResponse(Base):
    """Support ticket response model"""
    __tablename__ = "ticket_responses"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    message = Column(Text, nullable=False)
    
    # Can be from staff or user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_staff_response = Column(Boolean, nullable=False, default=False)
    
    # For guest responses
    guest_email = Column(String(255), nullable=True)
    
    # Attachments and metadata
    attachments = Column(JSON, nullable=True)  # List of file paths/URLs
    response_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relations
    ticket = relationship("Ticket", back_populates="responses")
    user = relationship("User")


# Update User model relation
from app.models.user import User
User.tickets = relationship("Ticket", back_populates="user")