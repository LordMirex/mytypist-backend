"""
Support Ticket System Service
Handle support tickets for both logged-in users and guests with tracking IDs
"""

import json
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, desc
from database import Base

logger = logging.getLogger(__name__)


class SupportTicket(Base):
    """Support tickets for users and guests"""
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(20), unique=True, nullable=False, index=True)  # Public tracking ID

    # User information
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)  # Null for guests
    guest_email = Column(String(255), nullable=True, index=True)  # For guest tickets
    guest_name = Column(String(255), nullable=True)

    # Ticket details
    subject = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)  # bug, feature, support, billing
    priority = Column(String(20), default="medium")  # low, medium, high, urgent

    # Status and assignment
    status = Column(String(20), default="open", index=True)  # open, in_progress, resolved, closed
    assigned_to = Column(Integer, ForeignKey('users.id'), nullable=True)  # Admin/moderator

    # Metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    attachments = Column(Text, nullable=True)  # JSON array of file paths

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # Auto-close settings
    last_user_reply = Column(DateTime, nullable=True)
    auto_close_at = Column(DateTime, nullable=True)


class TicketReply(Base):
    """Replies to support tickets"""
    __tablename__ = "ticket_replies"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey('support_tickets.id'), nullable=False, index=True)

    # Reply details
    reply_from = Column(String(20), nullable=False)  # user, admin, system
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Null for guest replies
    message = Column(Text, nullable=False)
    attachments = Column(Text, nullable=True)  # JSON array of file paths

    # Metadata
    is_internal = Column(Boolean, default=False)  # Internal admin notes
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SupportTicketService:
    """Service for managing support tickets and feedback"""

    @staticmethod
    def create_ticket(
        db: Session,
        subject: str,
        description: str,
        category: Optional[str] = None,
        user_id: Optional[int] = None,
        guest_email: Optional[str] = None,
        guest_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        priority: str = "medium"
    ) -> Dict[str, Any]:
        """Create a new support ticket"""
        try:
            # Generate unique ticket ID
            ticket_id = SupportTicketService._generate_ticket_id(db)

            # Create ticket
            ticket = SupportTicket(
                ticket_id=ticket_id,
                user_id=user_id,
                guest_email=guest_email,
                guest_name=guest_name,
                subject=subject,
                description=description,
                category=category or "support",
                priority=priority,
                ip_address=ip_address,
                user_agent=user_agent,
                last_user_reply=datetime.utcnow(),
                auto_close_at=datetime.utcnow() + timedelta(days=30)  # Auto-close after 30 days
            )

            db.add(ticket)
            db.commit()
            db.refresh(ticket)

            # Send notification email if guest
            if guest_email and not user_id:
                SupportTicketService._send_guest_ticket_confirmation(
                    guest_email, guest_name, ticket_id, subject
                )

            logger.info(f"Support ticket created: {ticket_id}")

            return {
                "success": True,
                "ticket_id": ticket_id,
                "internal_id": ticket.id,
                "status": "open",
                "message": "Support ticket created successfully",
                "tracking_info": {
                    "ticket_id": ticket_id,
                    "created_at": ticket.created_at.isoformat(),
                    "status": "open",
                    "category": category or "support"
                }
            }

        except Exception as e:
            logger.error(f"Failed to create support ticket: {e}")
            raise

    @staticmethod
    def get_ticket_by_id(
        db: Session,
        ticket_id: str,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get ticket details by tracking ID"""
        try:
            ticket = db.query(SupportTicket).filter(
                SupportTicket.ticket_id == ticket_id
            ).first()

            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            # Verify access for logged-in users
            if user_id and ticket.user_id and ticket.user_id != user_id:
                return {"success": False, "error": "Access denied"}

            # Get replies with user info using join to avoid N+1 queries
            from app.models.user import User
            replies = db.query(TicketReply, User).outerjoin(
                User, TicketReply.user_id == User.id
            ).filter(
                TicketReply.ticket_id == ticket.id,
                TicketReply.is_internal == False  # Don't show internal notes to users
            ).order_by(TicketReply.created_at).all()

            # Get assigned admin info
            assigned_admin = None
            if ticket.assigned_to:
                admin = db.query(User).filter(User.id == ticket.assigned_to).first()
                if admin:
                    assigned_admin = {
                        "name": f"{admin.first_name} {admin.last_name}",
                        "role": admin.role
                    }

            # Format replies
            reply_data = []
            for reply, user in replies:
                reply_user = None
                if user:
                        reply_user = {
                            "name": f"{user.first_name} {user.last_name}",
                            "role": user.role
                        }

                reply_data.append({
                    "id": reply.id,
                    "reply_from": reply.reply_from,
                    "user": reply_user,
                    "message": reply.message,
                    "created_at": reply.created_at.isoformat(),
                    "attachments": json.loads(reply.attachments) if reply.attachments else []
                })

            return {
                "success": True,
                "ticket": {
                    "ticket_id": ticket.ticket_id,
                    "subject": ticket.subject,
                    "description": ticket.description,
                    "category": ticket.category,
                    "priority": ticket.priority,
                    "status": ticket.status,
                    "created_at": ticket.created_at.isoformat(),
                    "updated_at": ticket.updated_at.isoformat(),
                    "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
                    "assigned_to": assigned_admin,
                    "is_guest_ticket": not bool(ticket.user_id),
                    "guest_email": ticket.guest_email if not ticket.user_id else None
                },
                "replies": reply_data,
                "reply_count": len(reply_data)
            }

        except Exception as e:
            logger.error(f"Failed to get ticket details: {e}")
            raise

    @staticmethod
    def add_reply(
        db: Session,
        ticket_id: str,
        message: str,
        reply_from: str = "user",
        user_id: Optional[int] = None,
        is_internal: bool = False
    ) -> Dict[str, Any]:
        """Add a reply to a support ticket"""
        try:
            # Get ticket
            ticket = db.query(SupportTicket).filter(
                SupportTicket.ticket_id == ticket_id
            ).first()

            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            # Verify access for user replies
            if reply_from == "user" and user_id and ticket.user_id != user_id:
                return {"success": False, "error": "Access denied"}

            # Create reply
            reply = TicketReply(
                ticket_id=ticket.id,
                reply_from=reply_from,
                user_id=user_id,
                message=message,
                is_internal=is_internal
            )

            db.add(reply)

            # Update ticket
            ticket.updated_at = datetime.utcnow()

            if reply_from == "user":
                ticket.last_user_reply = datetime.utcnow()
                # Reset auto-close timer
                ticket.auto_close_at = datetime.utcnow() + timedelta(days=30)

                # Reopen ticket if it was resolved
                if ticket.status == "resolved":
                    ticket.status = "open"

            elif reply_from in ["admin", "moderator"]:
                # Admin replied, mark as in progress
                if ticket.status == "open":
                    ticket.status = "in_progress"

            db.commit()

            # Send email notification
            if reply_from in ["admin", "moderator"] and ticket.guest_email:
                SupportTicketService._send_reply_notification(
                    ticket.guest_email, ticket_id, ticket.subject, message
                )

            logger.info(f"Reply added to ticket {ticket_id} by {reply_from}")

            return {
                "success": True,
                "reply_id": reply.id,
                "ticket_status": ticket.status,
                "message": "Reply added successfully"
            }

        except Exception as e:
            logger.error(f"Failed to add reply to ticket: {e}")
            raise

    @staticmethod
    def get_user_tickets(
        db: Session,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Get all tickets for a logged-in user"""
        try:
            query = db.query(SupportTicket).filter(
                SupportTicket.user_id == user_id
            )

            if status:
                query = query.filter(SupportTicket.status == status)

            tickets = query.order_by(desc(SupportTicket.updated_at)).limit(limit).all()

            ticket_data = []
            for ticket in tickets:
                # Get reply count
                reply_count = db.query(TicketReply).filter(
                    TicketReply.ticket_id == ticket.id,
                    TicketReply.is_internal == False
                ).count()

                # Get last reply
                last_reply = db.query(TicketReply).filter(
                    TicketReply.ticket_id == ticket.id,
                    TicketReply.is_internal == False
                ).order_by(desc(TicketReply.created_at)).first()

                ticket_data.append({
                    "ticket_id": ticket.ticket_id,
                    "subject": ticket.subject,
                    "category": ticket.category,
                    "priority": ticket.priority,
                    "status": ticket.status,
                    "created_at": ticket.created_at.isoformat(),
                    "updated_at": ticket.updated_at.isoformat(),
                    "reply_count": reply_count,
                    "last_reply_at": last_reply.created_at.isoformat() if last_reply else None,
                    "unread_replies": 0  # Would need additional tracking for this
                })

            return {
                "success": True,
                "tickets": ticket_data,
                "total_tickets": len(ticket_data),
                "status_counts": {
                    "open": len([t for t in ticket_data if t["status"] == "open"]),
                    "in_progress": len([t for t in ticket_data if t["status"] == "in_progress"]),
                    "resolved": len([t for t in ticket_data if t["status"] == "resolved"]),
                    "closed": len([t for t in ticket_data if t["status"] == "closed"])
                }
            }

        except Exception as e:
            logger.error(f"Failed to get user tickets: {e}")
            raise

    @staticmethod
    def get_admin_tickets(
        db: Session,
        admin_user_id: int,
        status: Optional[str] = None,
        assigned_only: bool = False,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get tickets for admin/moderator management"""
        try:
            query = db.query(SupportTicket)

            if status:
                query = query.filter(SupportTicket.status == status)

            if assigned_only:
                query = query.filter(SupportTicket.assigned_to == admin_user_id)

            tickets = query.order_by(desc(SupportTicket.updated_at)).limit(limit).all()

            ticket_data = []
            for ticket in tickets:
                # Get user info
                user_info = None
                if ticket.user_id:
                    from app.models.user import User
                    user = db.query(User).filter(User.id == ticket.user_id).first()
                    if user:
                        user_info = {
                            "id": user.id,
                            "name": f"{user.first_name} {user.last_name}",
                            "email": user.email
                        }

                # Get reply count
                reply_count = db.query(TicketReply).filter(
                    TicketReply.ticket_id == ticket.id
                ).count()

                ticket_data.append({
                    "ticket_id": ticket.ticket_id,
                    "internal_id": ticket.id,
                    "subject": ticket.subject,
                    "description": ticket.description[:200] + "..." if len(ticket.description) > 200 else ticket.description,
                    "category": ticket.category,
                    "priority": ticket.priority,
                    "status": ticket.status,
                    "user": user_info,
                    "guest_email": ticket.guest_email if not ticket.user_id else None,
                    "guest_name": ticket.guest_name if not ticket.user_id else None,
                    "is_guest_ticket": not bool(ticket.user_id),
                    "assigned_to": ticket.assigned_to,
                    "created_at": ticket.created_at.isoformat(),
                    "updated_at": ticket.updated_at.isoformat(),
                    "reply_count": reply_count,
                    "last_user_reply": ticket.last_user_reply.isoformat() if ticket.last_user_reply else None
                })

            return {
                "success": True,
                "tickets": ticket_data,
                "total_tickets": len(ticket_data)
            }

        except Exception as e:
            logger.error(f"Failed to get admin tickets: {e}")
            raise

    @staticmethod
    def update_ticket_status(
        db: Session,
        ticket_id: str,
        new_status: str,
        admin_user_id: int,
        resolution_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update ticket status (admin only)"""
        try:
            ticket = db.query(SupportTicket).filter(
                SupportTicket.ticket_id == ticket_id
            ).first()

            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            old_status = ticket.status
            ticket.status = new_status
            ticket.updated_at = datetime.utcnow()

            if new_status in ["resolved", "closed"]:
                ticket.resolved_at = datetime.utcnow()

            # Add system reply if resolution note provided
            if resolution_note:
                reply = TicketReply(
                    ticket_id=ticket.id,
                    reply_from="admin",
                    user_id=admin_user_id,
                    message=resolution_note,
                    is_internal=False
                )
                db.add(reply)

            db.commit()

            logger.info(f"Ticket {ticket_id} status updated from {old_status} to {new_status}")

            return {
                "success": True,
                "ticket_id": ticket_id,
                "old_status": old_status,
                "new_status": new_status,
                "message": f"Ticket status updated to {new_status}"
            }

        except Exception as e:
            logger.error(f"Failed to update ticket status: {e}")
            raise

    @staticmethod
    def _generate_ticket_id(db: Session) -> str:
        """Generate unique ticket ID"""
        while True:
            # Generate format: TKT-XXXXXX (6 alphanumeric characters)
            ticket_id = "TKT-" + ''.join(secrets.choice(
                string.ascii_uppercase + string.digits
            ) for _ in range(6))

            # Check if already exists
            existing = db.query(SupportTicket).filter(
                SupportTicket.ticket_id == ticket_id
            ).first()

            if not existing:
                return ticket_id

    @staticmethod
    def _send_guest_ticket_confirmation(
        email: str,
        name: Optional[str],
        ticket_id: str,
        subject: str
    ):
        """Send confirmation email to guest with tracking ID"""
        try:
            from app.services.email_service import EmailService

            template_data = {
                "name": name or "Guest",
                "ticket_id": ticket_id,
                "subject": subject,
                "tracking_url": f"https://mytypist.com/support/track/{ticket_id}",
                "support_email": "support@mytypist.com"
            }

            EmailService.send_email(
                to_email=email,
                subject=f"Support Ticket Created - {ticket_id}",
                template_name="support_ticket_created",
                template_data=template_data
            )

        except Exception as e:
            logger.error(f"Failed to send guest ticket confirmation: {e}")

    @staticmethod
    def _send_reply_notification(
        email: str,
        ticket_id: str,
        subject: str,
        reply_message: str
    ):
        """Send email notification for ticket reply"""
        try:
            from app.services.email_service import EmailService

            template_data = {
                "ticket_id": ticket_id,
                "subject": subject,
                "reply_message": reply_message[:500] + "..." if len(reply_message) > 500 else reply_message,
                "tracking_url": f"https://mytypist.com/support/track/{ticket_id}",
                "support_email": "support@mytypist.com"
            }

            EmailService.send_email(
                to_email=email,
                subject=f"Reply to Support Ticket - {ticket_id}",
                template_name="support_ticket_reply",
                template_data=template_data
            )

        except Exception as e:
            logger.error(f"Failed to send reply notification: {e}")
