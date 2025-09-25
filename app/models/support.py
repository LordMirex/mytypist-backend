"""
Support Ticket System Models
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

from database import Base


class TicketPriority(str, enum.Enum):
    """Ticket priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(str, enum.Enum):
    """Ticket status states"""
    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketCategory(str, enum.Enum):
    """Ticket category types"""
    GENERAL = "general"
    TECHNICAL = "technical"
    BILLING = "billing"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"


class SupportTicket(Base):
    """Support ticket model"""
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Ticket details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(Enum(TicketCategory), nullable=False)
    priority = Column(Enum(TicketPriority), nullable=False, default=TicketPriority.MEDIUM)
    status = Column(Enum(TicketStatus), nullable=False, default=TicketStatus.NEW)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # System details
    browser_info = Column(String(500), nullable=True)
    os_info = Column(String(200), nullable=True)
    url = Column(String(500), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="support_tickets")
    responses = relationship("TicketResponse", back_populates="ticket", cascade="all, delete-orphan")


class TicketResponse(Base):
    """Support ticket responses"""
    __tablename__ = "ticket_responses"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey('support_tickets.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Can be support staff or user
    
    message = Column(Text, nullable=False)
    is_internal = Column(Boolean, nullable=False, default=False)  # For staff notes
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    ticket = relationship("SupportTicket", back_populates="responses")
    user = relationship("User")