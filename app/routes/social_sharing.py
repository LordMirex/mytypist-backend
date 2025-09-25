"""
Routes for social sharing functionality
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from database import get_db
from app.models.document import Document
from app.services.social_share_service import SocialPreviewGenerator, SocialShareTracker

router = APIRouter()
preview_generator = SocialPreviewGenerator()
share_tracker = SocialShareTracker()

class ShareEvent(BaseModel):
    """Share event data model"""
    platform: str
    referrer: Optional[str] = None

@router.get("/preview/{document_id}")
async def get_social_preview(
    document_id: int,
    include_qr: bool = Query(True),
    db: Session = Depends(get_db)
):
    """
    Generate a social media preview image for a document
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    if not document.is_public:
        raise HTTPException(status_code=403, detail="Document is not public")
    
    preview = preview_generator.generate_document_preview(
        document,
        db,
        include_qr=include_qr
    )
    
    return StreamingResponse(preview, media_type="image/png")

@router.post("/share/{document_id}")
async def track_share(
    document_id: int,
    share_data: ShareEvent,
    db: Session = Depends(get_db)
):
    """
    Track a social share event
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    share = share_tracker.track_share(
        db,
        document_id,
        share_data.platform,
        share_data.referrer
    )
    
    return {"message": "Share tracked successfully", "share_id": share.id}

@router.get("/stats/{document_id}")
async def get_share_stats(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Get sharing statistics for a document
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    stats = share_tracker.get_sharing_stats(db, document_id)
    return stats