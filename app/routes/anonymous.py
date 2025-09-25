"""Anonymous document routes"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.template import Template
from app.schemas.document import DocumentCreate, DocumentPreview, DocumentResponse
from app.utils.guest_session import track_guest_activity
from app.utils.guest_document import generate_guest_preview, finalize_guest_document
from database import get_db

router = APIRouter()


@router.post("/preview/{template_id}", response_model=DocumentPreview)
async def preview_template(
    template_id: int,
    customization: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db)
):
    """Preview a document template as guest with customizations"""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    session_id = request.cookies.get("guest_session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Guest session required")
        
    # Generate preview with customizations
    preview_path = await generate_guest_preview(
        template,
        customization,
        session_id
    )
    
    # Track preview activity
    await track_guest_activity(
        session_id,
        "document_preview",
        {
            "template_id": template_id,
            "customization": customization
        }
    )
    
    return DocumentPreview(
        template_id=template.id,
        title=template.title,
        description=template.description,
        preview_file_path=preview_path,
        token_cost=template.token_cost
    )


@router.post("/guest-document", response_model=DocumentResponse)
async def create_guest_document(
    doc: DocumentCreate,
    customization: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a document as guest user with customizations"""
    template = db.query(Template).filter(Template.id == doc.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    session_id = request.cookies.get("guest_session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Guest session required")
    
    # Create document with guest status
    document = Document(
        template_id=template.id,
        title=doc.title,
        content=doc.content,
        status=DocumentStatus.GUEST
    )
    db.add(document)
    db.flush()  # Get ID without committing
    
    try:
        # Apply customizations and finalize
        document = await finalize_guest_document(
            document,
            customization,
            session_id
        )
        
        db.commit()
        
        # Track document creation
        await track_guest_activity(
            session_id,
            "document_create",
            {
                "template_id": template.id,
                "title": doc.title,
                "content": doc.content,
                "document_id": document.id,
                "customization": customization
            }
        )
        
        return document
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create guest document: {str(e)}"
        )


@router.put("/guest-document/{document_id}/customize", response_model=DocumentResponse)
async def customize_guest_document(
    document_id: int,
    customization: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db)
):
    """Update customization for an existing guest document"""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.status == DocumentStatus.GUEST
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=404,
            detail="Guest document not found"
        )
    
    session_id = request.cookies.get("guest_session_id")
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Guest session required"
        )
    
    try:
        # Apply new customizations
        document = await finalize_guest_document(
            document,
            customization,
            session_id
        )
        
        db.commit()
        
        # Track customization update
        await track_guest_activity(
            session_id,
            "document_customize",
            {
                "document_id": document_id,
                "customization": customization
            }
        )
        
        return document
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to customize document: {str(e)}"
        )