"""
Support Ticket System Routes
Handle support tickets for both logged-in users and guests with tracking IDs
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from database import get_db
from app.models.user import User
from app.services.support_ticket_service import SupportTicketService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user

router = APIRouter()


class CreateTicketRequest(BaseModel):
    """Request model for creating support ticket"""
    subject: str
    description: str
    category: Optional[str] = "support"
    priority: str = "medium"
    guest_email: Optional[EmailStr] = None
    guest_name: Optional[str] = None


class AddReplyRequest(BaseModel):
    """Request model for adding reply to ticket"""
    message: str


class UpdateTicketStatusRequest(BaseModel):
    """Request model for updating ticket status"""
    status: str
    resolution_note: Optional[str] = None


@router.post("/create-ticket", response_model=Dict[str, Any])
async def create_support_ticket(
    ticket_request: CreateTicketRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new support ticket for logged-in user"""
    try:
        result = SupportTicketService.create_ticket(
            db=db,
            subject=ticket_request.subject,
            description=ticket_request.description,
            category=ticket_request.category,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            priority=ticket_request.priority
        )

        if result["success"]:
            # Log ticket creation
            AuditService.log_user_activity(
                db,
                current_user.id,
                "SUPPORT_TICKET_CREATED",
                {
                    "ticket_id": result["ticket_id"],
                    "category": ticket_request.category,
                    "priority": ticket_request.priority
                }
            )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create support ticket: {str(e)}"
        )


@router.post("/guest/create-ticket", response_model=Dict[str, Any])
async def create_guest_support_ticket(
    ticket_request: CreateTicketRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a new support ticket for guest user"""
    try:
        if not ticket_request.guest_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required for guest tickets"
            )

        result = SupportTicketService.create_ticket(
            db=db,
            subject=ticket_request.subject,
            description=ticket_request.description,
            category=ticket_request.category,
            user_id=None,
            guest_email=ticket_request.guest_email,
            guest_name=ticket_request.guest_name,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            priority=ticket_request.priority
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create guest support ticket: {str(e)}"
        )


@router.get("/ticket/{ticket_id}", response_model=Dict[str, Any])
async def get_ticket_details(
    ticket_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get ticket details for logged-in user"""
    try:
        result = SupportTicketService.get_ticket_by_id(
            db=db,
            ticket_id=ticket_id,
            user_id=current_user.id
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get ticket details: {str(e)}"
        )


@router.get("/guest/ticket/{ticket_id}", response_model=Dict[str, Any])
async def get_guest_ticket_details(
    ticket_id: str,
    db: Session = Depends(get_db)
):
    """Get ticket details for guest (no authentication required)"""
    try:
        result = SupportTicketService.get_ticket_by_id(
            db=db,
            ticket_id=ticket_id,
            user_id=None
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get guest ticket details: {str(e)}"
        )


@router.post("/ticket/{ticket_id}/reply", response_model=Dict[str, Any])
async def add_ticket_reply(
    ticket_id: str,
    reply_request: AddReplyRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add a reply to support ticket"""
    try:
        result = SupportTicketService.add_reply(
            db=db,
            ticket_id=ticket_id,
            message=reply_request.message,
            reply_from="user",
            user_id=current_user.id
        )

        if result["success"]:
            # Log reply
            AuditService.log_user_activity(
                db,
                current_user.id,
                "SUPPORT_TICKET_REPLIED",
                {
                    "ticket_id": ticket_id,
                    "reply_id": result["reply_id"]
                }
            )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add reply: {str(e)}"
        )


@router.get("/my-tickets", response_model=Dict[str, Any])
async def get_my_tickets(
    status: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all tickets for current user"""
    try:
        result = SupportTicketService.get_user_tickets(
            db=db,
            user_id=current_user.id,
            status=status,
            limit=limit
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user tickets: {str(e)}"
        )


@router.get("/admin/tickets", response_model=Dict[str, Any])
async def get_admin_tickets(
    status: Optional[str] = None,
    assigned_only: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get tickets for admin/moderator management"""
    try:
        if not (current_user.is_admin or current_user.is_moderator):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or moderator access required"
            )

        result = SupportTicketService.get_admin_tickets(
            db=db,
            admin_user_id=current_user.id,
            status=status,
            assigned_only=assigned_only,
            limit=limit
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get admin tickets: {str(e)}"
        )


@router.post("/admin/ticket/{ticket_id}/reply", response_model=Dict[str, Any])
async def add_admin_reply(
    ticket_id: str,
    reply_request: AddReplyRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add admin/moderator reply to ticket"""
    try:
        if not (current_user.is_admin or current_user.is_moderator):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or moderator access required"
            )

        reply_from = "admin" if current_user.is_admin else "moderator"

        result = SupportTicketService.add_reply(
            db=db,
            ticket_id=ticket_id,
            message=reply_request.message,
            reply_from=reply_from,
            user_id=current_user.id
        )

        if result["success"]:
            # Log admin reply
            AuditService.log_user_activity(
                db,
                current_user.id,
                "ADMIN_TICKET_REPLIED",
                {
                    "ticket_id": ticket_id,
                    "reply_id": result["reply_id"],
                    "reply_from": reply_from
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add admin reply: {str(e)}"
        )


@router.post("/admin/ticket/{ticket_id}/internal-note", response_model=Dict[str, Any])
async def add_internal_note(
    ticket_id: str,
    reply_request: AddReplyRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add internal note to ticket (not visible to user)"""
    try:
        if not (current_user.is_admin or current_user.is_moderator):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or moderator access required"
            )

        reply_from = "admin" if current_user.is_admin else "moderator"

        result = SupportTicketService.add_reply(
            db=db,
            ticket_id=ticket_id,
            message=reply_request.message,
            reply_from=reply_from,
            user_id=current_user.id,
            is_internal=True
        )

        if result["success"]:
            # Log internal note
            AuditService.log_user_activity(
                db,
                current_user.id,
                "INTERNAL_NOTE_ADDED",
                {
                    "ticket_id": ticket_id,
                    "reply_id": result["reply_id"]
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add internal note: {str(e)}"
        )


@router.put("/admin/ticket/{ticket_id}/status", response_model=Dict[str, Any])
async def update_ticket_status(
    ticket_id: str,
    status_request: UpdateTicketStatusRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update ticket status (admin/moderator only)"""
    try:
        if not (current_user.is_admin or current_user.is_moderator):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or moderator access required"
            )

        # Validate status
        valid_statuses = ["open", "in_progress", "resolved", "closed"]
        if status_request.status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )

        result = SupportTicketService.update_ticket_status(
            db=db,
            ticket_id=ticket_id,
            new_status=status_request.status,
            admin_user_id=current_user.id,
            resolution_note=status_request.resolution_note
        )

        if result["success"]:
            # Log status update
            AuditService.log_user_activity(
                db,
                current_user.id,
                "TICKET_STATUS_UPDATED",
                {
                    "ticket_id": ticket_id,
                    "old_status": result["old_status"],
                    "new_status": result["new_status"]
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update ticket status: {str(e)}"
        )


@router.get("/admin/statistics", response_model=Dict[str, Any])
async def get_support_statistics(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get support system statistics"""
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        from datetime import datetime, timedelta
        from app.services.support_ticket_service import SupportTicket, TicketReply
        from sqlalchemy import func, desc

        start_date = datetime.utcnow() - timedelta(days=days)

        # Total tickets
        total_tickets = db.query(SupportTicket).count()

        # Recent tickets
        recent_tickets = db.query(SupportTicket).filter(
            SupportTicket.created_at >= start_date
        ).count()

        # Status breakdown
        status_counts = db.query(
            SupportTicket.status,
            func.count(SupportTicket.id).label('count')
        ).group_by(SupportTicket.status).all()

        status_breakdown = {status: count for status, count in status_counts}

        # Category breakdown
        category_counts = db.query(
            SupportTicket.category,
            func.count(SupportTicket.id).label('count')
        ).filter(
            SupportTicket.created_at >= start_date
        ).group_by(SupportTicket.category).all()

        category_breakdown = {category or "uncategorized": count for category, count in category_counts}

        # Response time analysis
        resolved_tickets = db.query(SupportTicket).filter(
            SupportTicket.status.in_(["resolved", "closed"]),
            SupportTicket.created_at >= start_date,
            SupportTicket.resolved_at.isnot(None)
        ).all()

        if resolved_tickets:
            resolution_times = []
            for ticket in resolved_tickets:
                resolution_time = (ticket.resolved_at - ticket.created_at).total_seconds() / 3600  # Hours
                resolution_times.append(resolution_time)

            avg_resolution_time = sum(resolution_times) / len(resolution_times)
        else:
            avg_resolution_time = 0

        # Guest vs User tickets
        guest_tickets = db.query(SupportTicket).filter(
            SupportTicket.user_id.is_(None),
            SupportTicket.created_at >= start_date
        ).count()

        user_tickets = db.query(SupportTicket).filter(
            SupportTicket.user_id.isnot(None),
            SupportTicket.created_at >= start_date
        ).count()

        return {
            "success": True,
            "period_days": days,
            "statistics": {
                "total_tickets": total_tickets,
                "recent_tickets": recent_tickets,
                "tickets_per_day": round(recent_tickets / max(days, 1), 1),
                "status_breakdown": status_breakdown,
                "category_breakdown": category_breakdown,
                "average_resolution_time_hours": round(avg_resolution_time, 1),
                "guest_tickets": guest_tickets,
                "user_tickets": user_tickets,
                "guest_percentage": round((guest_tickets / max(recent_tickets, 1)) * 100, 1),
                "resolution_rate": round((len(resolved_tickets) / max(recent_tickets, 1)) * 100, 1)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get support statistics: {str(e)}"
        )


@router.get("/categories", response_model=Dict[str, Any])
async def get_support_categories():
    """Get available support ticket categories"""
    categories = [
        {"id": "support", "name": "General Support", "description": "General help and questions"},
        {"id": "bug", "name": "Bug Report", "description": "Report technical issues or bugs"},
        {"id": "feature", "name": "Feature Request", "description": "Request new features or improvements"},
        {"id": "billing", "name": "Billing & Payments", "description": "Questions about payments, tokens, or subscriptions"},
        {"id": "account", "name": "Account Issues", "description": "Login, registration, or account management"},
        {"id": "document", "name": "Document Issues", "description": "Problems with document generation or templates"},
        {"id": "feedback", "name": "Feedback", "description": "General feedback and suggestions"}
    ]

    return {
        "success": True,
        "categories": categories
    }


@router.get("/priorities", response_model=Dict[str, Any])
async def get_support_priorities():
    """Get available support ticket priorities"""
    priorities = [
        {"id": "low", "name": "Low", "description": "Minor issues, suggestions"},
        {"id": "medium", "name": "Medium", "description": "Standard support requests"},
        {"id": "high", "name": "High", "description": "Important issues affecting functionality"},
        {"id": "urgent", "name": "Urgent", "description": "Critical issues requiring immediate attention"}
    ]

    return {
        "success": True,
        "priorities": priorities
    }
