"""
Draft System Routes
Auto-save documents with pay-later options and seamless user experience
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from app.models.user import User
from app.services.draft_system_service import DraftSystemService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user

router = APIRouter()


class CreateDraftRequest(BaseModel):
    """Request model for creating draft"""
    template_id: int
    title: str
    is_free_eligible: bool = False


class AutoSaveRequest(BaseModel):
    """Request model for auto-saving draft"""
    placeholder_data: Dict[str, Any]
    save_trigger: str = "typing_pause"
    field_name: Optional[str] = None


class PayForDraftRequest(BaseModel):
    """Request model for paying for draft"""
    payment_method: str = "tokens"


def get_session_info(request: Request) -> Dict[str, str]:
    """Extract session information from request"""
    return {
        "session_id": request.headers.get("x-session-id"),
        "device_fingerprint": request.headers.get("x-device-fingerprint"),
        "ip_address": request.client.host if request.client else None
    }


@router.post("/create", response_model=Dict[str, Any])
async def create_draft(
    draft_request: CreateDraftRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new document draft"""
    try:
        session_info = get_session_info(request)

        result = DraftSystemService.create_draft(
            db=db,
            template_id=draft_request.template_id,
            title=draft_request.title,
            user_id=current_user.id,
            session_id=session_info["session_id"],
            device_fingerprint=session_info["device_fingerprint"],
            is_free_eligible=draft_request.is_free_eligible
        )

        if result["success"]:
            # Log draft creation
            AuditService.log_user_activity(
                db,
                current_user.id,
                "DRAFT_CREATED",
                {
                    "draft_id": result["draft_id"],
                    "template_id": draft_request.template_id,
                    "is_free_eligible": draft_request.is_free_eligible
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create draft: {str(e)}"
        )


@router.post("/guest/create", response_model=Dict[str, Any])
async def create_guest_draft(
    draft_request: CreateDraftRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a draft for guest user"""
    try:
        session_info = get_session_info(request)

        if not session_info["session_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session ID required for guest drafts"
            )

        result = DraftSystemService.create_draft(
            db=db,
            template_id=draft_request.template_id,
            title=draft_request.title,
            user_id=None,
            session_id=session_info["session_id"],
            device_fingerprint=session_info["device_fingerprint"],
            is_free_eligible=draft_request.is_free_eligible
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create guest draft: {str(e)}"
        )


@router.post("/{draft_id}/auto-save", response_model=Dict[str, Any])
async def auto_save_draft(
    draft_id: int,
    auto_save_request: AutoSaveRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Auto-save draft content"""
    try:
        session_info = get_session_info(request)

        result = DraftSystemService.auto_save_draft(
            db=db,
            draft_id=draft_id,
            placeholder_data=auto_save_request.placeholder_data,
            save_trigger=auto_save_request.save_trigger,
            field_name=auto_save_request.field_name,
            user_id=current_user.id,
            session_id=session_info["session_id"]
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        # Don't raise HTTP exceptions for auto-save failures
        # Just return error response to avoid disrupting user experience
        return {"success": False, "error": "Auto-save failed"}


@router.post("/guest/{draft_id}/auto-save", response_model=Dict[str, Any])
async def auto_save_guest_draft(
    draft_id: int,
    auto_save_request: AutoSaveRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Auto-save guest draft content"""
    try:
        session_info = get_session_info(request)

        result = DraftSystemService.auto_save_draft(
            db=db,
            draft_id=draft_id,
            placeholder_data=auto_save_request.placeholder_data,
            save_trigger=auto_save_request.save_trigger,
            field_name=auto_save_request.field_name,
            user_id=None,
            session_id=session_info["session_id"]
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": "Auto-save failed"}


@router.get("/my-drafts", response_model=Dict[str, Any])
async def get_my_drafts(
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's drafts"""
    try:
        result = DraftSystemService.get_user_drafts(
            db=db,
            user_id=current_user.id,
            limit=limit
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get drafts: {str(e)}"
        )


@router.get("/guest/my-drafts", response_model=Dict[str, Any])
async def get_guest_drafts(
    request: Request,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get guest user's drafts"""
    try:
        session_info = get_session_info(request)

        if not session_info["session_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session ID required"
            )

        result = DraftSystemService.get_user_drafts(
            db=db,
            session_id=session_info["session_id"],
            limit=limit
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get guest drafts: {str(e)}"
        )


@router.get("/{draft_id}", response_model=Dict[str, Any])
async def get_draft_details(
    draft_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get detailed draft information"""
    try:
        session_info = get_session_info(request)

        result = DraftSystemService.get_draft_details(
            db=db,
            draft_id=draft_id,
            user_id=current_user.id,
            session_id=session_info["session_id"]
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
            detail=f"Failed to get draft details: {str(e)}"
        )


@router.get("/guest/{draft_id}", response_model=Dict[str, Any])
async def get_guest_draft_details(
    draft_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get guest draft details"""
    try:
        session_info = get_session_info(request)

        result = DraftSystemService.get_draft_details(
            db=db,
            draft_id=draft_id,
            user_id=None,
            session_id=session_info["session_id"]
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
            detail=f"Failed to get guest draft details: {str(e)}"
        )


@router.post("/{draft_id}/finalize", response_model=Dict[str, Any])
async def finalize_draft(
    draft_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Finalize draft and prepare for payment or free download
    This is the 'Generate Document' button functionality
    """
    try:
        session_info = get_session_info(request)

        result = DraftSystemService.finalize_draft_for_payment(
            db=db,
            draft_id=draft_id,
            user_id=current_user.id,
            session_id=session_info["session_id"]
        )

        if result["success"]:
            # Log draft finalization
            AuditService.log_user_activity(
                db,
                current_user.id,
                "DRAFT_FINALIZED",
                {
                    "draft_id": draft_id,
                    "action": result["action"],
                    "token_cost": result.get("token_cost", 0)
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to finalize draft: {str(e)}"
        )


@router.post("/guest/{draft_id}/finalize", response_model=Dict[str, Any])
async def finalize_guest_draft(
    draft_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Finalize guest draft - usually triggers registration flow"""
    try:
        session_info = get_session_info(request)

        result = DraftSystemService.finalize_draft_for_payment(
            db=db,
            draft_id=draft_id,
            user_id=None,
            session_id=session_info["session_id"]
        )

        # For guests, we typically want to trigger registration
        if result["success"] and result.get("action") == "payment_required":
            result["registration_required"] = True
            result["message"] = "Please register to download your document or save it as a draft."

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to finalize guest draft: {str(e)}"
        )


@router.post("/{draft_id}/pay", response_model=Dict[str, Any])
async def pay_for_draft(
    draft_id: int,
    pay_request: PayForDraftRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Pay for draft and enable download"""
    try:
        result = DraftSystemService.pay_for_draft(
            db=db,
            draft_id=draft_id,
            user_id=current_user.id,
            payment_method=pay_request.payment_method
        )

        if result["success"]:
            # Log payment
            AuditService.log_user_activity(
                db,
                current_user.id,
                "DRAFT_PAYMENT_COMPLETED",
                {
                    "draft_id": draft_id,
                    "tokens_debited": result["tokens_debited"],
                    "payment_method": pay_request.payment_method
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process draft payment: {str(e)}"
        )


@router.get("/{draft_id}/download")
async def download_draft(
    draft_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Download finalized draft document"""
    try:
        session_info = get_session_info(request)

        # Get draft details
        draft_result = DraftSystemService.get_draft_details(
            db=db,
            draft_id=draft_id,
            user_id=current_user.id,
            session_id=session_info["session_id"]
        )

        if not draft_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Draft not found"
            )

        draft = draft_result["draft"]

        # Check if document is ready for download
        if draft["requires_payment"] and draft["payment_status"] != "paid":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Payment required to download this document"
            )

        if not draft["document_content"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document not yet generated. Please finalize the draft first."
            )

        # Log download
        AuditService.log_user_activity(
            db,
            current_user.id,
            "DRAFT_DOWNLOADED",
            {"draft_id": draft_id}
        )

        # Return download response (you'd implement actual file serving)
        return {
            "success": True,
            "draft_id": draft_id,
            "download_ready": True,
            "file_name": f"{draft['title']}.pdf",
            "content_type": "application/pdf",
            "message": "Document ready for download"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download draft: {str(e)}"
        )


@router.delete("/{draft_id}")
async def delete_draft(
    draft_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a draft"""
    try:
        session_info = get_session_info(request)

        result = DraftSystemService.delete_draft(
            db=db,
            draft_id=draft_id,
            user_id=current_user.id,
            session_id=session_info["session_id"]
        )

        if result["success"]:
            # Log deletion
            AuditService.log_user_activity(
                db,
                current_user.id,
                "DRAFT_DELETED",
                {"draft_id": draft_id}
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete draft: {str(e)}"
        )


@router.post("/cleanup-expired")
async def cleanup_expired_drafts(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Admin endpoint to cleanup expired drafts"""
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        # Run cleanup in background
        background_tasks.add_task(DraftSystemService.cleanup_expired_drafts, db)

        return {
            "success": True,
            "message": "Draft cleanup started in background"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start cleanup: {str(e)}"
        )


@router.get("/admin/statistics")
async def get_draft_statistics(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get draft system statistics for admin"""
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        from datetime import datetime, timedelta
        from app.services.draft_system_service import DocumentDraft, DraftAutoSave

        start_date = datetime.utcnow() - timedelta(days=days)

        # Total drafts
        total_drafts = db.query(DocumentDraft).count()

        # Recent drafts
        recent_drafts = db.query(DocumentDraft).filter(
            DocumentDraft.created_at >= start_date
        ).count()

        # Paid drafts
        paid_drafts = db.query(DocumentDraft).filter(
            DocumentDraft.payment_status == "paid"
        ).count()

        # Auto-save events
        auto_saves = db.query(DraftAutoSave).filter(
            DraftAutoSave.created_at >= start_date
        ).count()

        # Average completion
        avg_completion = db.query(
            db.func.avg(DocumentDraft.completion_percentage)
        ).scalar() or 0

        return {
            "success": True,
            "period_days": days,
            "statistics": {
                "total_drafts": total_drafts,
                "recent_drafts": recent_drafts,
                "paid_drafts": paid_drafts,
                "conversion_rate": round((paid_drafts / max(total_drafts, 1)) * 100, 2),
                "auto_save_events": auto_saves,
                "average_completion": round(avg_completion, 1),
                "active_drafts": db.query(DocumentDraft).filter(
                    DocumentDraft.payment_status == "pending",
                    DocumentDraft.expires_at > datetime.utcnow()
                ).count()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )
