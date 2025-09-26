"""
Comprehensive Draft System Service
Auto-save documents with pay-later options and seamless user experience
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, desc
from database import Base

logger = logging.getLogger(__name__)


class DocumentDraft(Base):
    """Document drafts with auto-save functionality"""
    __tablename__ = "document_drafts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)  # Nullable for guest drafts
    template_id = Column(Integer, ForeignKey('templates.id'), nullable=False, index=True)

    # Draft content
    title = Column(String(255), nullable=False)
    placeholder_data = Column(Text, nullable=True)  # JSON of user inputs
    document_content = Column(Text, nullable=True)  # Generated document content

    # Draft metadata
    draft_name = Column(String(255), nullable=True)  # User-defined name for draft
    completion_percentage = Column(Float, default=0.0)  # 0-100%
    auto_save_data = Column(Text, nullable=True)  # JSON of auto-save state

    # Payment and status
    requires_payment = Column(Boolean, default=True)
    token_cost = Column(Integer, nullable=True)
    is_free_eligible = Column(Boolean, default=False)
    payment_status = Column(String(20), default="pending")  # pending, paid, expired

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_modified = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_auto_save = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Auto-delete old drafts

    # Session tracking for guests
    session_id = Column(String(100), nullable=True, index=True)
    device_fingerprint = Column(String(64), nullable=True, index=True)


class DraftAutoSave(Base):
    """Track auto-save events for analytics"""
    __tablename__ = "draft_auto_saves"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey('document_drafts.id'), nullable=False, index=True)

    # Auto-save details
    save_trigger = Column(String(50), nullable=False)  # typing_pause, page_blur, manual
    field_name = Column(String(100), nullable=True)  # Which field was being edited
    content_length = Column(Integer, default=0)

    # Performance
    save_duration_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class DraftSystemService:
    """Service for managing document drafts with auto-save and payment options"""

    @staticmethod
    def create_draft(
        db: Session,
        template_id: int,
        title: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
        is_free_eligible: bool = False
    ) -> Dict[str, Any]:
        """Create a new document draft"""
        try:
            # Get template info for pricing
            from app.models.template import Template
            template = db.query(Template).filter(Template.id == template_id).first()

            if not template:
                return {"success": False, "error": "Template not found"}

            # Calculate expiration (30 days for registered users, 7 days for guests)
            expires_in_days = 30 if user_id else 7
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

            # Create draft
            draft = DocumentDraft(
                user_id=user_id,
                template_id=template_id,
                title=title,
                draft_name=f"Draft - {title}",
                token_cost=template.price or 0,
                is_free_eligible=is_free_eligible,
                requires_payment=not is_free_eligible and (template.price or 0) > 0,
                session_id=session_id,
                device_fingerprint=device_fingerprint,
                expires_at=expires_at
            )

            db.add(draft)
            db.commit()
            db.refresh(draft)

            logger.info(f"Draft created: {draft.id} for template {template_id}")

            return {
                "success": True,
                "draft_id": draft.id,
                "template_id": template_id,
                "title": title,
                "token_cost": draft.token_cost,
                "requires_payment": draft.requires_payment,
                "is_free_eligible": is_free_eligible,
                "expires_at": expires_at.isoformat(),
                "auto_save_enabled": True
            }

        except Exception as e:
            logger.error(f"Failed to create draft: {e}")
            raise

    @staticmethod
    def auto_save_draft(
        db: Session,
        draft_id: int,
        placeholder_data: Dict[str, Any],
        save_trigger: str = "typing_pause",
        field_name: Optional[str] = None,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Auto-save draft content"""
        try:
            start_time = datetime.utcnow()

            # Get draft
            draft = db.query(DocumentDraft).filter(DocumentDraft.id == draft_id).first()

            if not draft:
                return {"success": False, "error": "Draft not found"}

            # Verify access
            if user_id and draft.user_id != user_id:
                return {"success": False, "error": "Access denied"}

            if not user_id and draft.session_id != session_id:
                return {"success": False, "error": "Session mismatch"}

            # Update draft content
            current_data = json.loads(draft.placeholder_data) if draft.placeholder_data else {}
            current_data.update(placeholder_data)

            draft.placeholder_data = json.dumps(current_data)
            draft.last_auto_save = datetime.utcnow()
            draft.last_modified = datetime.utcnow()

            # Calculate completion percentage
            draft.completion_percentage = DraftSystemService._calculate_completion_percentage(
                current_data, draft.template_id, db
            )

            # Store auto-save state
            auto_save_state = {
                "last_field": field_name,
                "save_trigger": save_trigger,
                "total_fields": len(current_data),
                "completion": draft.completion_percentage,
                "timestamp": datetime.utcnow().isoformat()
            }
            draft.auto_save_data = json.dumps(auto_save_state)

            db.commit()

            # Log auto-save event
            save_duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            auto_save_log = DraftAutoSave(
                draft_id=draft_id,
                save_trigger=save_trigger,
                field_name=field_name,
                content_length=len(json.dumps(current_data)),
                save_duration_ms=save_duration
            )
            db.add(auto_save_log)
            db.commit()

            logger.debug(f"Auto-saved draft {draft_id} ({save_trigger}) in {save_duration}ms")

            return {
                "success": True,
                "draft_id": draft_id,
                "completion_percentage": draft.completion_percentage,
                "last_auto_save": draft.last_auto_save.isoformat(),
                "save_duration_ms": save_duration,
                "auto_save_trigger": save_trigger
            }

        except Exception as e:
            logger.error(f"Failed to auto-save draft: {e}")
            return {"success": False, "error": "Auto-save failed"}

    @staticmethod
    def get_user_drafts(
        db: Session,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Get drafts for user or session"""
        try:
            query = db.query(DocumentDraft)

            if user_id:
                query = query.filter(DocumentDraft.user_id == user_id)
            elif session_id:
                query = query.filter(DocumentDraft.session_id == session_id)
            else:
                return {"success": False, "error": "User ID or session ID required"}

            # Only get non-expired drafts
            query = query.filter(
                (DocumentDraft.expires_at.is_(None)) |
                (DocumentDraft.expires_at > datetime.utcnow())
            )

            # Use join to avoid N+1 query for template info
            from app.models.template import Template
            drafts_with_templates = db.query(DocumentDraft, Template).outerjoin(
                Template, DocumentDraft.template_id == Template.id
            ).filter(query.whereclause).order_by(desc(DocumentDraft.last_modified)).limit(limit).all()

            draft_data = []
            for draft, template in drafts_with_templates:

                # Parse auto-save data
                auto_save_info = {}
                if draft.auto_save_data:
                    try:
                        auto_save_info = json.loads(draft.auto_save_data)
                    except:
                        pass

                draft_data.append({
                    "draft_id": draft.id,
                    "title": draft.title,
                    "draft_name": draft.draft_name,
                    "template_name": template.name if template else "Unknown",
                    "template_id": draft.template_id,
                    "completion_percentage": draft.completion_percentage,
                    "token_cost": draft.token_cost,
                    "requires_payment": draft.requires_payment,
                    "is_free_eligible": draft.is_free_eligible,
                    "payment_status": draft.payment_status,
                    "created_at": draft.created_at.isoformat(),
                    "last_modified": draft.last_modified.isoformat(),
                    "last_auto_save": draft.last_auto_save.isoformat(),
                    "expires_at": draft.expires_at.isoformat() if draft.expires_at else None,
                    "auto_save_info": auto_save_info
                })

            return {
                "success": True,
                "drafts": draft_data,
                "total_drafts": len(draft_data)
            }

        except Exception as e:
            logger.error(f"Failed to get user drafts: {e}")
            raise

    @staticmethod
    def get_draft_details(
        db: Session,
        draft_id: int,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get detailed draft information"""
        try:
            draft = db.query(DocumentDraft).filter(DocumentDraft.id == draft_id).first()

            if not draft:
                return {"success": False, "error": "Draft not found"}

            # Verify access
            if user_id and draft.user_id != user_id:
                return {"success": False, "error": "Access denied"}

            if not user_id and draft.session_id != session_id:
                return {"success": False, "error": "Session mismatch"}

            # Get template info
            from app.models.template import Template
            template = db.query(Template).filter(Template.id == draft.template_id).first()

            if not template:
                return {"success": False, "error": "Template not found"}

            # Parse placeholder data
            placeholder_data = {}
            if draft.placeholder_data:
                try:
                    placeholder_data = json.loads(draft.placeholder_data)
                except:
                    pass

            # Parse auto-save data
            auto_save_info = {}
            if draft.auto_save_data:
                try:
                    auto_save_info = json.loads(draft.auto_save_data)
                except:
                    pass

            return {
                "success": True,
                "draft": {
                    "id": draft.id,
                    "title": draft.title,
                    "draft_name": draft.draft_name,
                    "template_id": draft.template_id,
                    "template_name": template.name,
                    "placeholder_data": placeholder_data,
                    "document_content": draft.document_content,
                    "completion_percentage": draft.completion_percentage,
                    "token_cost": draft.token_cost,
                    "requires_payment": draft.requires_payment,
                    "is_free_eligible": draft.is_free_eligible,
                    "payment_status": draft.payment_status,
                    "created_at": draft.created_at.isoformat(),
                    "last_modified": draft.last_modified.isoformat(),
                    "last_auto_save": draft.last_auto_save.isoformat(),
                    "expires_at": draft.expires_at.isoformat() if draft.expires_at else None,
                    "auto_save_info": auto_save_info
                }
            }

        except Exception as e:
            logger.error(f"Failed to get draft details: {e}")
            raise

    @staticmethod
    def finalize_draft_for_payment(
        db: Session,
        draft_id: int,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Finalize draft and prepare for payment or free download
        This is called when user clicks 'Generate Document'
        """
        try:
            draft = db.query(DocumentDraft).filter(DocumentDraft.id == draft_id).first()

            if not draft:
                return {"success": False, "error": "Draft not found"}

            # Verify access
            if user_id and draft.user_id != user_id:
                return {"success": False, "error": "Access denied"}

            if not user_id and draft.session_id != session_id:
                return {"success": False, "error": "Session mismatch"}

            # Generate document content
            placeholder_data = json.loads(draft.placeholder_data) if draft.placeholder_data else {}

            # Generate document (this would use your existing document generation logic)
            document_result = DraftSystemService._generate_document_from_draft(
                db, draft, placeholder_data
            )

            if not document_result["success"]:
                return document_result

            # Update draft with generated content
            draft.document_content = document_result["content"]
            draft.completion_percentage = 100.0
            draft.last_modified = datetime.utcnow()

            db.commit()

            # Determine next action
            if draft.is_free_eligible or draft.token_cost == 0:
                # Free download
                return {
                    "success": True,
                    "action": "free_download",
                    "draft_id": draft_id,
                    "document_content": draft.document_content,
                    "download_url": f"/api/drafts/{draft_id}/download",
                    "message": "Document ready for free download!"
                }
            else:
                # Requires payment
                return {
                    "success": True,
                    "action": "payment_required",
                    "draft_id": draft_id,
                    "token_cost": draft.token_cost,
                    "payment_options": {
                        "pay_now": f"/api/drafts/{draft_id}/pay",
                        "save_as_draft": "already_saved"
                    },
                    "message": f"Document ready! Pay {draft.token_cost} tokens to download or keep as draft."
                }

        except Exception as e:
            logger.error(f"Failed to finalize draft: {e}")
            raise

    @staticmethod
    def pay_for_draft(
        db: Session,
        draft_id: int,
        user_id: int,
        payment_method: str = "tokens"
    ) -> Dict[str, Any]:
        """Process payment for draft and enable download"""
        try:
            draft = db.query(DocumentDraft).filter(
                DocumentDraft.id == draft_id,
                DocumentDraft.user_id == user_id
            ).first()

            if not draft:
                return {"success": False, "error": "Draft not found"}

            if draft.payment_status == "paid":
                return {"success": False, "error": "Draft already paid for"}

            # Check user token balance
            from app.services.wallet_service import WalletService
            wallet_balance = WalletService.get_wallet_balance(db, user_id)

            if wallet_balance["balance"] < draft.token_cost:
                return {
                    "success": False,
                    "error": "Insufficient token balance",
                    "required_tokens": draft.token_cost,
                    "current_balance": wallet_balance["balance"],
                    "shortfall": draft.token_cost - wallet_balance["balance"]
                }

            # Deduct tokens
            debit_result = WalletService.debit_tokens(
                db, user_id, draft.token_cost, f"Document generation - Draft {draft_id}"
            )

            if not debit_result["success"]:
                return {"success": False, "error": "Payment processing failed"}

            # Update draft status
            draft.payment_status = "paid"
            draft.requires_payment = False
            draft.last_modified = datetime.utcnow()

            db.commit()

            # Create document record
            document_result = DraftSystemService._create_document_from_paid_draft(db, draft, user_id)

            logger.info(f"Draft {draft_id} paid for by user {user_id} - {draft.token_cost} tokens")

            return {
                "success": True,
                "draft_id": draft_id,
                "document_id": document_result.get("document_id"),
                "tokens_debited": draft.token_cost,
                "remaining_balance": wallet_balance["balance"] - draft.token_cost,
                "download_url": f"/api/drafts/{draft_id}/download",
                "message": "Payment successful! Document is ready for download."
            }

        except Exception as e:
            logger.error(f"Failed to process draft payment: {e}")
            raise

    @staticmethod
    def delete_draft(
        db: Session,
        draft_id: int,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a draft"""
        try:
            draft = db.query(DocumentDraft).filter(DocumentDraft.id == draft_id).first()

            if not draft:
                return {"success": False, "error": "Draft not found"}

            # Verify access
            if user_id and draft.user_id != user_id:
                return {"success": False, "error": "Access denied"}

            if not user_id and draft.session_id != session_id:
                return {"success": False, "error": "Session mismatch"}

            # Delete associated auto-save records
            db.query(DraftAutoSave).filter(DraftAutoSave.draft_id == draft_id).delete()

            # Delete draft
            db.delete(draft)
            db.commit()

            logger.info(f"Draft {draft_id} deleted")

            return {
                "success": True,
                "message": "Draft deleted successfully"
            }

        except Exception as e:
            logger.error(f"Failed to delete draft: {e}")
            raise

    @staticmethod
    def cleanup_expired_drafts(db: Session) -> Dict[str, Any]:
        """Clean up expired drafts (background task)"""
        try:
            expired_drafts = db.query(DocumentDraft).filter(
                DocumentDraft.expires_at < datetime.utcnow(),
                DocumentDraft.payment_status != "paid"
            ).all()

            deleted_count = 0
            for draft in expired_drafts:
                # Delete auto-save records
                db.query(DraftAutoSave).filter(DraftAutoSave.draft_id == draft.id).delete()

                # Delete draft
                db.delete(draft)
                deleted_count += 1

            db.commit()

            logger.info(f"Cleaned up {deleted_count} expired drafts")

            return {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"Cleaned up {deleted_count} expired drafts"
            }

        except Exception as e:
            logger.error(f"Failed to cleanup expired drafts: {e}")
            raise

    @staticmethod
    def _calculate_completion_percentage(
        placeholder_data: Dict[str, Any],
        template_id: int,
        db: Session
    ) -> float:
        """Calculate completion percentage based on filled placeholders"""
        try:
            # Get template placeholder count (simplified)
            from app.models.template import Template
            template = db.query(Template).filter(Template.id == template_id).first()

            if not template:
                return 0.0

            # Analyze template to count required placeholders
            from app.models.template import Placeholder
            template_placeholders = db.query(Placeholder).filter(
                Placeholder.template_id == template_id
            ).count()

            total_fields = max(len(placeholder_data), template_placeholders, 5)
            filled_fields = len([v for v in placeholder_data.values() if v and str(v).strip()])

            return min(100.0, (filled_fields / total_fields) * 100)

        except Exception:
            return 0.0

    @staticmethod
    def _generate_document_from_draft(
        db: Session,
        draft: DocumentDraft,
        placeholder_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate document content from draft data"""
        try:
            # Use existing document generation service
            from app.services.document_service import DocumentService

            # Generate document using existing service
            generation_result = DocumentService.generate_document_preview(
                db=db,
                template_id=draft.template_id,
                placeholder_data=placeholder_data,
                user_id=draft.user_id
            )

            if generation_result.get("success"):
                return {
                    "success": True,
                    "content": generation_result.get("preview_content", "Generated document content"),
                    "file_path": generation_result.get("file_path")
                }
            else:
                return {"success": False, "error": "Document generation failed"}

        except Exception as e:
            logger.error(f"Failed to generate document from draft: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _create_document_from_paid_draft(
        db: Session,
        draft: DocumentDraft,
        user_id: int
    ) -> Dict[str, Any]:
        """Create official document record from paid draft"""
        try:
            from app.models.document import Document

            # Create document record
            document = Document(
                user_id=user_id,
                template_id=draft.template_id,
                title=draft.title,
                content=draft.document_content,
                status="completed",
                created_at=datetime.utcnow()
            )

            db.add(document)
            db.commit()
            db.refresh(document)

            # Document created from draft


            return {"success": True, "document_id": document.id}

        except Exception as e:
            logger.error(f"Failed to create document from draft: {e}")
            return {"success": False, "error": str(e)}
