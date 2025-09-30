"""
Public Document Sharing Routes
Share documents with anyone, SEO friendly and track views
No authentication required, optimized for conversions
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from app.models.document import Document
from app.models.visit import Visit
from app.models.user import User
from app.utils.security import get_current_active_user

router = APIRouter(prefix="/api/document-sharing", tags=["document-sharing"])


class DocumentShareAccessRequest(BaseModel):
    """Request model for accessing shared documents"""
    password: Optional[str] = None
    email: Optional[str] = None


@router.get("/document/{document_id}", response_model=Dict[str, Any])
async def get_shared_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public endpoint to view a shared document
    - No authentication required
    - Tracks views for analytics
    - Returns original document for previously downloaded documents
    - Returns watermarked preview for public templates
    """
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Track the visit
        visit = Visit(
            document_id=document.id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            referrer=request.headers.get("referer"),
            visited_at=datetime.utcnow()
        )
        db.add(visit)
        db.commit()

        # Return document based on its status
        return {
            "document_id": document.id,
            "title": document.title,
            "content": document.content,
            "created_at": document.created_at,
            "watermark": not document.is_downloaded,  # Only add watermark for non-downloaded docs
            "type": "downloaded" if document.is_downloaded else "template"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve shared document: {str(e)}"
        )


@router.get("/analytics/{document_id}", response_model=Dict[str, Any])
async def get_document_analytics(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Get analytics for a shared document
    - Total views
    - Unique visitors
    - Traffic sources
    """
    try:
        visits = db.query(Visit).filter(Visit.document_id == document_id).all()
        
        # Calculate analytics
        unique_ips = set(visit.ip_address for visit in visits)
        traffic_sources = {}
        for visit in visits:
            source = visit.referrer or "direct"
            traffic_sources[source] = traffic_sources.get(source, 0) + 1

        return {
            "total_views": len(visits),
            "unique_visitors": len(unique_ips),
            "traffic_sources": traffic_sources,
            "last_viewed": max(visit.visited_at for visit in visits) if visits else None
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve analytics: {str(e)}"
        )
        


@router.post("/shared/{share_token}/access", response_model=Dict[str, Any])
async def access_shared_document(
    share_token: str,
    access_request: DocumentShareAccessRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Access a shared document with password
    Provides view-only access to the document content
    """
    try:
        # Get client IP for logging
        client_ip = request.client.host if request.client else None

        # Access the document
        result = AdminDashboardService.access_shared_document(
            db=db,
            share_token=share_token,
            password=access_request.password,
            ip_address=client_ip
        )

        # Track the page visit for analytics
        if result["success"]:
            AdminDashboardService.track_page_visit(
                db=db,
                page_path=f"/shared/{share_token}",
                session_id=f"share_{share_token}",
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to access shared document: {str(e)}"
        )


@router.get("/my-shares", response_model=Dict[str, Any])
async def get_my_document_shares(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all document shares created by the current user
    """
    try:
        from app.services.admin_dashboard_service import DocumentShare
        from app.models.document import Document

        shares = db.query(DocumentShare).filter(
            DocumentShare.shared_by == current_user.id
        ).order_by(DocumentShare.created_at.desc()).all()

        share_data = []
        for share in shares:
            # Get document info
            document = db.query(Document).filter(
                Document.id == share.document_id
            ).first()

            share_data.append({
                "share_id": share.id,
                "share_token": share.share_token,
                "document_id": share.document_id,
                "document_title": document.title if document else "Unknown",
                "expires_at": share.expires_at.isoformat(),
                "is_active": share.is_active,
                "max_views": share.max_views,
                "current_views": share.current_views,
                "created_at": share.created_at.isoformat(),
                "last_accessed": share.last_accessed.isoformat() if share.last_accessed else None,
                "share_url": f"/shared/{share.share_token}"
            })

        return {
            "success": True,
            "shares": share_data,
            "total_shares": len(share_data)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document shares: {str(e)}"
        )


@router.delete("/shared/{share_token}")
async def deactivate_document_share(
    share_token: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Deactivate a document share (revoke access)
    """
    try:
        from app.services.admin_dashboard_service import DocumentShare

        share = db.query(DocumentShare).filter(
            DocumentShare.share_token == share_token
        ).first()

        if not share:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Share not found"
            )

        # Check ownership or admin permission
        if share.shared_by != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to deactivate this share"
            )

        # Deactivate the share
        share.is_active = False
        db.commit()

        # Log the action
        AuditService.log_user_activity(
            db,
            current_user.id,
            "DOCUMENT_SHARE_DEACTIVATED",
            {
                "share_token": share_token,
                "document_id": share.document_id
            }
        )

        return {
            "success": True,
            "message": "Document share has been deactivated"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate document share: {str(e)}"
        )


@router.get("/admin/shares", response_model=Dict[str, Any])
async def get_all_document_shares(
    page: int = 1,
    limit: int = 50,
    active_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to view all document shares
    """
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        from app.services.admin_dashboard_service import DocumentShare
        from app.models.document import Document

        query = db.query(DocumentShare)

        if active_only:
            query = query.filter(DocumentShare.is_active == True)

        # Get total count
        total_shares = query.count()

        # Apply pagination
        offset = (page - 1) * limit
        shares = query.order_by(DocumentShare.created_at.desc()).offset(offset).limit(limit).all()

        share_data = []
        for share in shares:
            # Get document and user info
            document = db.query(Document).filter(
                Document.id == share.document_id
            ).first()

            user = db.query(User).filter(
                User.id == share.shared_by
            ).first()

            share_data.append({
                "share_id": share.id,
                "share_token": share.share_token,
                "document_id": share.document_id,
                "document_title": document.title if document else "Unknown",
                "shared_by": {
                    "id": user.id if user else None,
                    "email": user.email if user else "Unknown"
                },
                "expires_at": share.expires_at.isoformat(),
                "is_active": share.is_active,
                "max_views": share.max_views,
                "current_views": share.current_views,
                "created_at": share.created_at.isoformat(),
                "last_accessed": share.last_accessed.isoformat() if share.last_accessed else None
            })

        return {
            "success": True,
            "shares": share_data,
            "pagination": {
                "total": total_shares,
                "page": page,
                "limit": limit,
                "total_pages": (total_shares + limit - 1) // limit
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document shares: {str(e)}"
        )
