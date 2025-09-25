"""
Document Editing Service
Handles document editing with placeholder change tracking and pricing logic
"""

from datetime import datetime
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
import json
import difflib

from database import Base
from app.models.document import Document, DocumentStatus
from app.models.template import Template
from app.services.audit_service import AuditService
from app.services.wallet_service import WalletService


class DocumentEdit(Base):
    """Document edit history"""
    __tablename__ = "document_edits"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    # Edit details
    edit_type = Column(String(50), nullable=False)  # placeholder_change, content_change, format_change
    changes_made = Column(JSON, nullable=False)  # Detailed changes
    placeholder_changes_count = Column(Integer, nullable=False, default=0)

    # Pricing information
    is_free_edit = Column(Boolean, nullable=False, default=True)
    charge_applied = Column(Float, nullable=False, default=0.0)
    payment_transaction_id = Column(Integer, nullable=True)

    # Edit metadata
    previous_version = Column(JSON, nullable=True)  # Previous document state
    new_version = Column(JSON, nullable=True)  # New document state
    edit_reason = Column(String(500), nullable=True)

    # Status
    is_applied = Column(Boolean, nullable=False, default=False)
    applied_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("Document", backref="edits")


class DocumentEditingService:
    """Document editing service with placeholder change tracking"""

    # Pricing configuration
    FREE_PLACEHOLDER_CHANGES = 3
    PAID_EDIT_PRICE = 100.0  # NGN per edit beyond free limit

    @staticmethod
    def analyze_placeholder_changes(original_data: Dict, new_data: Dict) -> Dict:
        """Analyze changes in placeholder data"""

        if not original_data:
            original_data = {}
        if not new_data:
            new_data = {}

        changes = {
            "added": [],
            "modified": [],
            "removed": [],
            "unchanged": []
        }

        all_keys = set(original_data.keys()) | set(new_data.keys())

        for key in all_keys:
            original_value = original_data.get(key)
            new_value = new_data.get(key)

            if key not in original_data:
                changes["added"].append({
                    "key": key,
                    "new_value": new_value
                })
            elif key not in new_data:
                changes["removed"].append({
                    "key": key,
                    "old_value": original_value
                })
            elif original_value != new_value:
                changes["modified"].append({
                    "key": key,
                    "old_value": original_value,
                    "new_value": new_value
                })
            else:
                changes["unchanged"].append({
                    "key": key,
                    "value": original_value
                })

        # Calculate total significant changes
        significant_changes = len(changes["added"]) + len(changes["modified"]) + len(changes["removed"])

        return {
            "changes": changes,
            "total_changes": significant_changes,
            "is_free_edit": significant_changes <= DocumentEditingService.FREE_PLACEHOLDER_CHANGES
        }

    @staticmethod
    def estimate_edit_cost(db: Session, document_id: int, new_placeholder_data: Dict) -> Dict:
        """Estimate the cost of editing a document"""

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"error": "Document not found"}

        # Analyze changes
        analysis = DocumentEditingService.analyze_placeholder_changes(
            document.placeholder_data or {}, new_placeholder_data
        )

        cost = 0.0
        requires_payment = False

        if not analysis["is_free_edit"]:
            cost = DocumentEditingService.PAID_EDIT_PRICE
            requires_payment = True

        return {
            "document_id": document_id,
            "total_changes": analysis["total_changes"],
            "free_changes_allowed": DocumentEditingService.FREE_PLACEHOLDER_CHANGES,
            "is_free_edit": analysis["is_free_edit"],
            "cost": cost,
            "currency": "NGN",
            "requires_payment": requires_payment,
            "changes_breakdown": analysis["changes"]
        }

    @staticmethod
    def apply_document_edit(db: Session, document_id: int, user_id: int,
                           new_placeholder_data: Dict, edit_reason: str = None,
                           force_payment: bool = False) -> Dict:
        """Apply edits to a document with automatic pricing"""

        document = db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == user_id
        ).first()

        if not document:
            return {"success": False, "error": "Document not found or access denied"}

        if document.status not in [DocumentStatus.COMPLETED, DocumentStatus.DRAFT]:
            return {"success": False, "error": "Document cannot be edited in current status"}

        # Analyze changes
        analysis = DocumentEditingService.analyze_placeholder_changes(
            document.placeholder_data or {}, new_placeholder_data
        )

        # Determine if payment is required
        requires_payment = not analysis["is_free_edit"] or force_payment
        charge_applied = 0.0
        payment_transaction_id = None

        if requires_payment:
            charge_applied = DocumentEditingService.PAID_EDIT_PRICE

            # Process payment from wallet
            payment_result = WalletService.deduct_funds(
                db, user_id, charge_applied,
                f"Document edit: {document.title}",
                reference=f"DOC_EDIT_{document_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                metadata={"document_id": document_id, "changes_count": analysis["total_changes"]},
                related_document_id=document_id
            )

            if not payment_result["success"]:
                return {"success": False, "error": f"Payment failed: {payment_result['error']}"}

            payment_transaction_id = payment_result["transaction_id"]

        # Create edit record
        edit_record = DocumentEdit(
            document_id=document_id,
            user_id=user_id,
            edit_type="placeholder_change",
            changes_made=analysis["changes"],
            placeholder_changes_count=analysis["total_changes"],
            is_free_edit=analysis["is_free_edit"],
            charge_applied=charge_applied,
            payment_transaction_id=payment_transaction_id,
            previous_version={
                "placeholder_data": document.placeholder_data,
                "updated_at": document.updated_at.isoformat() if document.updated_at else None
            },
            new_version={
                "placeholder_data": new_placeholder_data,
                "updated_at": datetime.utcnow().isoformat()
            },
            edit_reason=edit_reason,
            is_applied=True,
            applied_at=datetime.utcnow()
        )

        # Apply changes to document
        document.placeholder_data = new_placeholder_data
        document.updated_at = datetime.utcnow()

        # If this is a paid edit, create new document ID and treat as new creation
        new_document_id = document_id
        if requires_payment and not force_payment:
            # Create new document with new ID
            new_document = Document(
                title=f"{document.title} (Edited)",
                description=document.description,
                content=document.content,
                placeholder_data=new_placeholder_data,
                file_path=None,  # Will be regenerated
                file_format=document.file_format,
                access_level=document.access_level,
                requires_signature=document.requires_signature,
                required_signature_count=document.required_signature_count,
                auto_delete=document.auto_delete,
                user_id=user_id,
                template_id=document.template_id,
                status=DocumentStatus.DRAFT,
                parent_document_id=document_id  # Link to original
            )

            db.add(new_document)
            db.flush()  # Get new ID
            new_document_id = new_document.id

            # Update edit record to reference new document
            edit_record.document_id = new_document_id

        db.add(edit_record)
        db.commit()

        # Log edit action
        AuditService.log_document_event(
            "DOCUMENT_EDITED",
            user_id,
            None,
            {
                "original_document_id": document_id,
                "new_document_id": new_document_id,
                "changes_count": analysis["total_changes"],
                "is_free_edit": analysis["is_free_edit"],
                "charge_applied": charge_applied,
                "edit_id": edit_record.id
            }
        )

        return {
            "success": True,
            "document_id": new_document_id,
            "edit_id": edit_record.id,
            "changes_applied": analysis["total_changes"],
            "is_free_edit": analysis["is_free_edit"],
            "charge_applied": charge_applied,
            "payment_transaction_id": payment_transaction_id,
            "created_new_document": new_document_id != document_id,
            "message": "Document edited successfully" + (
                " (new document created due to paid edit)" if new_document_id != document_id else ""
            )
        }

    @staticmethod
    def get_document_edit_history(db: Session, document_id: int, user_id: int) -> List[Dict]:
        """Get edit history for a document"""

        # Verify user owns the document
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == user_id
        ).first()

        if not document:
            return []

        edits = db.query(DocumentEdit).filter(
            DocumentEdit.document_id == document_id
        ).order_by(DocumentEdit.created_at.desc()).all()

        return [DocumentEditingService._format_edit_record(edit) for edit in edits]

    @staticmethod
    def get_user_edit_statistics(db: Session, user_id: int, days: int = 30) -> Dict:
        """Get user's document editing statistics"""

        from sqlalchemy import func
        start_date = datetime.utcnow() - timedelta(days=days)

        # Total edits
        total_edits = db.query(DocumentEdit).filter(
            DocumentEdit.user_id == user_id,
            DocumentEdit.created_at >= start_date
        ).count()

        # Free vs paid edits
        free_edits = db.query(DocumentEdit).filter(
            DocumentEdit.user_id == user_id,
            DocumentEdit.created_at >= start_date,
            DocumentEdit.is_free_edit == True
        ).count()

        paid_edits = total_edits - free_edits

        # Total spent on edits
        total_spent = db.query(func.sum(DocumentEdit.charge_applied)).filter(
            DocumentEdit.user_id == user_id,
            DocumentEdit.created_at >= start_date
        ).scalar() or 0

        # Most edited documents
        most_edited = db.query(
            DocumentEdit.document_id,
            func.count(DocumentEdit.id).label('edit_count')
        ).filter(
            DocumentEdit.user_id == user_id,
            DocumentEdit.created_at >= start_date
        ).group_by(DocumentEdit.document_id).order_by(
            func.count(DocumentEdit.id).desc()
        ).limit(5).all()

        return {
            "period_days": days,
            "total_edits": total_edits,
            "free_edits": free_edits,
            "paid_edits": paid_edits,
            "total_spent": total_spent,
            "average_cost_per_paid_edit": total_spent / paid_edits if paid_edits > 0 else 0,
            "most_edited_documents": [
                {
                    "document_id": doc[0],
                    "edit_count": doc[1]
                }
                for doc in most_edited
            ]
        }

    @staticmethod
    def revert_document_edit(db: Session, edit_id: int, user_id: int) -> Dict:
        """Revert a document edit"""

        edit = db.query(DocumentEdit).filter(
            DocumentEdit.id == edit_id,
            DocumentEdit.user_id == user_id,
            DocumentEdit.is_applied == True
        ).first()

        if not edit:
            return {"success": False, "error": "Edit not found or cannot be reverted"}

        document = edit.document
        if not document or document.user_id != user_id:
            return {"success": False, "error": "Access denied"}

        # Restore previous version
        if edit.previous_version and edit.previous_version.get("placeholder_data"):
            document.placeholder_data = edit.previous_version["placeholder_data"]
            document.updated_at = datetime.utcnow()

            # Mark edit as reverted
            edit.is_applied = False

            # If this was a paid edit, issue refund
            if edit.charge_applied > 0 and edit.payment_transaction_id:
                refund_result = WalletService.refund_transaction(
                    db, edit.payment_transaction_id, "Document edit reverted"
                )

                if not refund_result["success"]:
                    return {"success": False, "error": f"Revert failed: {refund_result['error']}"}

            db.commit()

            # Log revert action
            AuditService.log_document_event(
                "DOCUMENT_EDIT_REVERTED",
                user_id,
                None,
                {
                    "document_id": document.id,
                    "edit_id": edit_id,
                    "refund_issued": edit.charge_applied > 0
                }
            )

            return {
                "success": True,
                "document_id": document.id,
                "refund_amount": edit.charge_applied,
                "message": "Edit reverted successfully"
            }

        return {"success": False, "error": "No previous version available to revert to"}

    @staticmethod
    def _format_edit_record(edit: DocumentEdit) -> Dict:
        """Format edit record for API response"""
        return {
            "id": edit.id,
            "document_id": edit.document_id,
            "edit_type": edit.edit_type,
            "changes_count": edit.placeholder_changes_count,
            "is_free_edit": edit.is_free_edit,
            "charge_applied": edit.charge_applied,
            "edit_reason": edit.edit_reason,
            "is_applied": edit.is_applied,
            "applied_at": edit.applied_at,
            "created_at": edit.created_at,
            "changes_summary": DocumentEditingService._summarize_changes(edit.changes_made)
        }

    @staticmethod
    def _summarize_changes(changes: Dict) -> Dict:
        """Create a summary of changes for display"""
        if not changes:
            return {}

        return {
            "placeholders_added": len(changes.get("added", [])),
            "placeholders_modified": len(changes.get("modified", [])),
            "placeholders_removed": len(changes.get("removed", [])),
            "total_significant_changes": len(changes.get("added", [])) +
                                      len(changes.get("modified", [])) +
                                      len(changes.get("removed", []))
        }

    @staticmethod
    def get_edit_pricing_info() -> Dict:
        """Get current edit pricing information"""
        return {
            "free_placeholder_changes": DocumentEditingService.FREE_PLACEHOLDER_CHANGES,
            "paid_edit_price": DocumentEditingService.PAID_EDIT_PRICE,
            "currency": "NGN",
            "policy": {
                "free_edits": f"Up to {DocumentEditingService.FREE_PLACEHOLDER_CHANGES} placeholder changes are free",
                "paid_edits": f"Changes beyond {DocumentEditingService.FREE_PLACEHOLDER_CHANGES} placeholders cost {DocumentEditingService.PAID_EDIT_PRICE} NGN",
                "new_document": "Paid edits create a new document with a new ID",
                "refund_policy": "Edits can be reverted with full refund within 24 hours"
            }
        }
