"""Support ticket service"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from fastapi import HTTPException, status

from app.models.ticket import Ticket, TicketResponse, TicketStatus
from app.models.user import User
from app.schemas.ticket import TicketCreate, TicketUpdate, TicketResponseCreate
from app.services.email_service import email_service
from app.services.audit_service import AuditService


class TicketService:
    """Service for managing support tickets"""
    
    @staticmethod
    def create_ticket(
        db: Session,
        ticket_data: TicketCreate,
        user_id: Optional[int] = None,
        guest_session_id: Optional[str] = None
    ) -> Ticket:
        """Create a new support ticket"""
        
        # Validate at least one identifier is provided
        if not user_id and not ticket_data.guest_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either user_id or guest_email is required"
            )
            
        # Create ticket
        ticket = Ticket(
            title=ticket_data.title,
            description=ticket_data.description,
            category=ticket_data.category,
            priority=ticket_data.priority,
            user_id=user_id,
            guest_email=ticket_data.guest_email,
            guest_session_id=guest_session_id,
            document_id=ticket_data.document_id,
            template_id=ticket_data.template_id,
            metadata=ticket_data.metadata,
            browser_info=ticket_data.browser_info,
            error_details=ticket_data.error_details
        )
        
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        
        # Send confirmation email
        if ticket.guest_email:
            email_service.send_ticket_confirmation(
                ticket.guest_email,
                ticket.id,
                ticket.title
            )
            
        return ticket

    @staticmethod
    def get_ticket(
        db: Session,
        ticket_id: int,
        user_id: Optional[int] = None,
        guest_email: Optional[str] = None
    ) -> Optional[Ticket]:
        """Get a ticket by ID with access control"""
        
        query = db.query(Ticket).filter(Ticket.id == ticket_id)
        
        # Add access control
        if user_id:
            query = query.filter(Ticket.user_id == user_id)
        elif guest_email:
            query = query.filter(Ticket.guest_email == guest_email)
        else:
            return None
            
        return query.first()

    @staticmethod
    def list_tickets(
        db: Session,
        user_id: Optional[int] = None,
        guest_email: Optional[str] = None,
        status: Optional[TicketStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Ticket], int]:
        """List tickets with filtering"""
        
        query = db.query(Ticket)
        
        # Apply filters
        if user_id:
            query = query.filter(Ticket.user_id == user_id)
        if guest_email:
            query = query.filter(Ticket.guest_email == guest_email)
        if status:
            query = query.filter(Ticket.status == status)
            
        total = query.count()
        tickets = query.order_by(desc(Ticket.created_at)).offset(skip).limit(limit).all()
        
        return tickets, total

    @staticmethod
    def update_ticket(
        db: Session,
        ticket_id: int,
        ticket_data: TicketUpdate,
        user_id: Optional[int] = None,
        is_staff: bool = False
    ) -> Optional[Ticket]:
        """Update a ticket"""
        
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id)
        
        # Check access
        if not is_staff:
            if not user_id or ticket.first().user_id != user_id:
                return None
        
        # Update fields
        update_data = ticket_data.dict(exclude_unset=True)
        if update_data.get('status') == TicketStatus.CLOSED:
            update_data['closed_at'] = datetime.utcnow()
            
        ticket.update(update_data)
        db.commit()
        
        return ticket.first()

    @staticmethod
    def add_response(
        db: Session,
        ticket_id: int,
        response_data: TicketResponseCreate,
        user_id: Optional[int] = None,
        is_staff: bool = False,
        guest_email: Optional[str] = None
    ) -> TicketResponse:
        """Add a response to a ticket"""
        
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
            
        # Create response
        response = TicketResponse(
            ticket_id=ticket_id,
            message=response_data.message,
            user_id=user_id,
            is_staff_response=is_staff,
            guest_email=guest_email,
            attachments=response_data.attachments,
            metadata=response_data.metadata
        )
        
        db.add(response)
        
        # Update ticket timestamps
        ticket.updated_at = datetime.utcnow()
        ticket.last_response_at = datetime.utcnow()
        
        if is_staff:
            if not ticket.first_response_at:
                ticket.first_response_at = datetime.utcnow()
                if ticket.created_at:
                    ticket.response_time_seconds = int(
                        (ticket.first_response_at - ticket.created_at).total_seconds()
                    )
            
            # Update status if needed
            if ticket.status == TicketStatus.OPEN:
                ticket.status = TicketStatus.IN_PROGRESS
                
        else:
            # User/guest response moves ticket back to open if it was waiting
            if ticket.status == TicketStatus.WAITING:
                ticket.status = TicketStatus.IN_PROGRESS
        
        db.commit()
        db.refresh(response)
        
        # Send notification
        if ticket.user_id and is_staff:
            # Notify user of staff response
            user = db.query(User).get(ticket.user_id)
            if user and user.email:
                email_service.send_ticket_update(
                    user.email,
                    ticket.id,
                    ticket.title,
                    response.message
                )
        elif ticket.guest_email and is_staff:
            # Notify guest of staff response
            email_service.send_ticket_update(
                ticket.guest_email,
                ticket.id,
                ticket.title,
                response.message
            )
            
        return response