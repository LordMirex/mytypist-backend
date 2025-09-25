"""
Document Editing Routes
API endpoints for document editing with placeholder tracking and pricing
"""

from datetime import datetime
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from sqlalchemy.orm import Session

from database import get_db
from app.models.user import User
from app.utils.security import get_current_active_user
from app.services.document_editing_service import DocumentEditingService
from app.services.audit_service import AuditService

router = APIRouter()


@router.post("/{document_id}/estimate-edit-cost")
async def estimate_edit_cost(
    document_id: int,
    new_placeholder_data: Dict = Body(..., description="New placeholder data"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Estimate the cost of editing a document"""

    estimate = DocumentEditingService.estimate_edit_cost(db, document_id, new_placeholder_data)

    if "error" in estimate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=estimate["error"]
        )

    return estimate


@router.post("/{document_id}/edit")
async def edit_document(
    document_id: int,
    new_placeholder_data: Dict = Body(..., description="New placeholder data"),
    edit_reason: Optional[str] = Body(None, max_length=500, description="Reason for edit"),
    force_payment: bool = Body(False, description="Force payment even for free edits"),
    request: Request = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Apply edits to a document"""

    result = DocumentEditingService.apply_document_edit(
        db, document_id, current_user.id, new_placeholder_data, edit_reason, force_payment
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )

    # Log edit action
    AuditService.log_document_event(
        "DOCUMENT_EDITED",
        current_user.id,
        request,
        {
            "original_document_id": document_id,
            "new_document_id": result["document_id"],
            "edit_id": result["edit_id"],
            "changes_count": result["changes_applied"],
            "charge_applied": result["charge_applied"],
            "is_free_edit": result["is_free_edit"]
        }
    )

    return result


@router.get("/{document_id}/edit-history")
async def get_document_edit_history(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get edit history for a document"""

    history = DocumentEditingService.get_document_edit_history(db, document_id, current_user.id)

    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied"
        )

    return {"document_id": document_id, "edit_history": history}


@router.post("/edits/{edit_id}/revert")
async def revert_document_edit(
    edit_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Revert a document edit"""

    result = DocumentEditingService.revert_document_edit(db, edit_id, current_user.id)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )

    # Log revert action
    AuditService.log_system_event(
        "DOCUMENT_EDIT_REVERTED",
        {
            "user_id": current_user.id,
            "edit_id": edit_id,
            "document_id": result["document_id"],
            "refund_amount": result["refund_amount"]
        }
    )

    return result


@router.get("/my/edit-statistics")
async def get_user_edit_statistics(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's document editing statistics"""

    stats = DocumentEditingService.get_user_edit_statistics(db, current_user.id, days)
    return stats


@router.get("/pricing-info")
async def get_edit_pricing_info():
    """Get current edit pricing information"""

    pricing_info = DocumentEditingService.get_edit_pricing_info()
    return pricing_info
