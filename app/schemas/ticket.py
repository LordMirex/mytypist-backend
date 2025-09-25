"""Support ticket schemas"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field

from app.models.ticket import TicketCategory, TicketPriority, TicketStatus


class TicketResponseBase(BaseModel):
    """Base ticket response schema"""
    message: str = Field(..., min_length=1)
    attachments: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class TicketResponseCreate(TicketResponseBase):
    """Ticket response creation schema"""
    pass


class TicketResponseUpdate(TicketResponseBase):
    """Ticket response update schema"""
    message: Optional[str] = None


class TicketResponseOut(TicketResponseBase):
    """Ticket response output schema"""
    id: int
    ticket_id: int
    user_id: Optional[int]
    is_staff_response: bool
    guest_email: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class TicketBase(BaseModel):
    """Base ticket schema"""
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    category: TicketCategory
    priority: Optional[TicketPriority] = TicketPriority.MEDIUM
    document_id: Optional[int] = None
    template_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    browser_info: Optional[Dict[str, Any]] = None
    error_details: Optional[Dict[str, Any]] = None


class TicketCreate(TicketBase):
    """Ticket creation schema"""
    guest_email: Optional[EmailStr] = None


class TicketUpdate(BaseModel):
    """Ticket update schema"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[TicketCategory] = None
    priority: Optional[TicketPriority] = None
    status: Optional[TicketStatus] = None
    metadata: Optional[Dict[str, Any]] = None


class TicketOut(TicketBase):
    """Ticket output schema"""
    id: int
    status: TicketStatus
    user_id: Optional[int]
    guest_email: Optional[str]
    guest_session_id: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    closed_at: Optional[datetime]
    first_response_at: Optional[datetime]
    last_response_at: Optional[datetime]
    response_time_seconds: Optional[int]
    responses: List[TicketResponseOut]

    class Config:
        orm_mode = True


class TicketList(BaseModel):
    """Ticket list response"""
    tickets: List[TicketOut]
    total: int
    page: int
    per_page: int
    pages: int