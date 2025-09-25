"""
Document management routes
"""

import os
import uuid
import hashlib
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
import io

from database import get_db
from config import settings
from app.models.document import Document, DocumentStatus, DocumentAccess
from app.models.template import Template
from app.models.user import User
from app.schemas.document import (
    DocumentCreate, DocumentUpdate, DocumentResponse, DocumentList,
    DocumentGenerate, DocumentShare, DocumentSearch, DocumentStats,
    DocumentBatch, DocumentBatchResponse, DocumentDownload, DocumentPreview
)
from app.services.document_service import DocumentService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user
from app.tasks.document_tasks import generate_document_task, generate_batch_documents_task

router = APIRouter()


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    document_data: DocumentCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    guest_session: str = None,
    db: Session = Depends(get_db)
):
    """Create a new document for authenticated users or guests"""
    
    # Check if this is a guest request
    if not current_user:
        guest_session = request.cookies.get("guest_session_id")
        if not guest_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication or guest session required"
            )

    # Validate template if provided
    template = None
    if document_data.template_id:
        template = db.query(Template).filter(
            Template.id == document_data.template_id,
            Template.is_active == True
        ).first()
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )

        # Check if user has access to template
        if not template.is_public and template.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to template"
            )

    # Create document
    if current_user:
        user_id = current_user.id
        doc_status = DocumentStatus.DRAFT
    else:
        user_id = None  # Will be updated when user registers
        doc_status = DocumentStatus.GUEST

    # Create document with appropriate status
    document = Document(
        title=document_data.title,
        description=document_data.description,
        template_id=template.id if template else None,
        content=document_data.content,
        user_id=user_id,
        status=doc_status,
        access_level=document_data.access_level,
        requires_signature=document_data.requires_signature,
        required_signature_count=document_data.required_signature_count,
        auto_delete=document_data.auto_delete,
        file_format=document_data.file_format
    )
    db.add(document)
    db.flush()

    # Start background generation if template is provided
    if template and document_data.placeholder_data:
        background_tasks.add_task(
            generate_document_task.delay,
            document.id,
            document_data.placeholder_data
        )
        document.status = DocumentStatus.PROCESSING
    
    # If guest, store session ID in metadata for later
    if not current_user and guest_session:
        document.metadata = {
            "guest_session_id": guest_session,
            "created_at": datetime.utcnow().isoformat()
        }
    
    db.commit()

    # Log document creation
    event_user = current_user.id if current_user else f"guest:{guest_session}"
    AuditService.log_document_event(
        "DOCUMENT_CREATED",
        event_user,
        request,
        {
            "document_id": document.id,
            "template_id": document_data.template_id,
            "title": document.title,
            "is_guest": not current_user
        }
    )

    return DocumentResponse.from_orm(document)


@router.get("/", response_model=DocumentList)
async def list_documents(
    page: int = 1,
    per_page: int = 20,
    status_filter: Optional[DocumentStatus] = None,
    template_id: Optional[int] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List user's documents with pagination and filters"""

    # Build query
    query = db.query(Document).filter(Document.user_id == current_user.id)

    # Apply filters
    if status_filter:
        query = query.filter(Document.status == status_filter)

    if template_id:
        query = query.filter(Document.template_id == template_id)

    if search:
        query = query.filter(
            or_(
                Document.title.contains(search),
                Document.description.contains(search)
            )
        )

    # Get total count
    total = query.count()

    # Apply pagination and ordering
    documents = query.order_by(desc(Document.created_at)).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    # Calculate pagination info
    pages = (total + per_page - 1) // per_page

    return DocumentList(
        documents=[DocumentResponse.from_orm(doc) for doc in documents],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )


@router.get("/search", response_model=DocumentList)
async def search_documents(
    search_params: DocumentSearch = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Advanced document search"""

    documents, total = DocumentService.search_documents(
        db, current_user.id, search_params
    )

    pages = (total + search_params.per_page - 1) // search_params.per_page

    return DocumentList(
        documents=[DocumentResponse.from_orm(doc) for doc in documents],
        total=total,
        page=search_params.page,
        per_page=search_params.per_page,
        pages=pages
    )


@router.get("/stats", response_model=DocumentStats)
async def get_document_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get document statistics for user"""

    stats = DocumentService.get_user_document_stats(db, current_user.id)
    return stats


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get document by ID"""

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Update view count
    document.view_count += 1
    db.commit()

    # Log document view
    AuditService.log_document_event(
        "DOCUMENT_VIEWED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "title": document.title
        }
    )

    return DocumentResponse.from_orm(document)


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    document_update: DocumentUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update document"""

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Update document
    updated_document = DocumentService.update_document(db, document, document_update)

    # Log document update
    AuditService.log_document_event(
        "DOCUMENT_UPDATED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "title": document.title,
            "updated_fields": list(document_update.dict(exclude_unset=True).keys())
        }
    )

    return DocumentResponse.from_orm(updated_document)


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete document"""

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Soft delete
    DocumentService.delete_document(db, document)

    # Log document deletion
    AuditService.log_document_event(
        "DOCUMENT_DELETED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "title": document.title
        }
    )

    return {"message": "Document deleted successfully"}


@router.post("/generate", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def generate_document(
    generation_data: DocumentGenerate,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate document from template"""

    # Validate template
    template = db.query(Template).filter(
        Template.id == generation_data.template_id,
        Template.is_active == True
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    # Check template access
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )

    # Create document
    document = DocumentService.create_document_from_generation(
        db, generation_data, current_user.id
    )

    # Start generation task
    background_tasks.add_task(
        generate_document_task.delay,
        document.id,
        generation_data.placeholder_data
    )

    # Log document generation
    AuditService.log_document_event(
        "DOCUMENT_GENERATED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "template_id": template.id,
            "title": document.title
        }
    )

    return DocumentResponse.from_orm(document)


@router.post("/batch", response_model=DocumentBatchResponse, status_code=status.HTTP_201_CREATED)
async def generate_batch_documents(
    batch_data: DocumentBatch,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate multiple documents with smart input consolidation"""

    # Validate templates
    template_ids = list(set([doc.template_id for doc in batch_data.documents]))
    templates = db.query(Template).filter(
        Template.id.in_(template_ids),
        Template.is_active == True
    ).all()

    if len(templates) != len(template_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more templates not found"
        )

    # Check template access
    for template in templates:
        if not template.is_public and template.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to template: {template.title}"
            )

    # Smart input consolidation
    consolidated_inputs = await DocumentService.consolidate_batch_inputs(
        db=db,
        templates=templates,
        batch_documents=batch_data.documents
    )

    # Create batch documents
    batch_id = str(uuid.uuid4())
    documents = []

    for doc_data in batch_data.documents:
        document = DocumentService.create_document_for_batch(
            db, doc_data.template_id, doc_data, current_user.id, batch_id
        )
        documents.append(document)

    # Start advanced batch generation task
    background_tasks.add_task(
        generate_batch_documents_task.delay,
        batch_id,
        [doc.id for doc in documents],
        consolidated_inputs,
        batch_data.batch_settings if hasattr(batch_data, 'batch_settings') else {}
    )

    # Log batch generation
    AuditService.log_document_event(
        "ADVANCED_BATCH_GENERATED",
        current_user.id,
        request,
        {
            "batch_id": batch_id,
            "template_ids": template_ids,
            "document_count": len(documents),
            "consolidated_inputs": len(consolidated_inputs["consolidated_placeholders"]),
            "original_inputs": sum(len(doc.placeholder_data) for doc in batch_data.documents)
        }
    )

    return DocumentBatchResponse(
        batch_id=batch_id,
        total_documents=len(documents),
        processing_status="processing",
        estimated_completion=datetime.utcnow(),
        documents=[DocumentResponse.from_orm(doc) for doc in documents],
        consolidation_summary=consolidated_inputs["summary"]
    )


@router.get("/{document_id}/download", response_class=FileResponse, operation_id="download_document")
async def download_document(
    document_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Download document file with guest restrictions"""

    # Get the document with ownership check
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Check for guest restrictions
    if document.status == DocumentStatus.GUEST:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please register to download this document"
        )

    # Check if document is ready for download
    if not document.is_completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document is not ready for download"
        )

    # Check if file exists
    if not document.file_path or not os.path.exists(document.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found"
        )

    # Update download stats
    document.download_count += 1
    if not document.is_downloaded:
        document.is_downloaded = True
    db.commit()

    # Log document download
    AuditService.log_document_event(
        "DOCUMENT_DOWNLOADED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "title": document.title,
            "download_count": document.download_count
        }
    )

    return FileResponse(
        path=document.file_path,
        filename=document.original_filename or f"{document.title}.{document.file_format}",
        media_type="application/octet-stream"
    )


@router.post("/batch/{batch_id}/download")
async def download_batch_documents(
    batch_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Download all documents in a batch as a ZIP file"""

    # Get batch documents
    documents = db.query(Document).filter(
        Document.batch_id == batch_id,
        Document.user_id == current_user.id
    ).all()

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or no documents available"
        )

    # Check if all documents are completed
    incomplete_docs = [doc for doc in documents if not doc.is_completed]
    if incomplete_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{len(incomplete_docs)} documents are still processing"
        )

    # Generate batch download
    zip_file_info = await DocumentService.create_batch_download(
        documents=documents,
        batch_id=batch_id
    )

    if not zip_file_info["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create batch download"
        )

    # Update download counts
    for doc in documents:
        doc.download_count += 1
    db.commit()

    # Log batch download
    AuditService.log_document_event(
        "BATCH_DOWNLOADED",
        current_user.id,
        request,
        {
            "batch_id": batch_id,
            "document_count": len(documents),
            "zip_size": zip_file_info["file_size"]
        }
    )

    return FileResponse(
        path=zip_file_info["file_path"],
        filename=f"batch_{batch_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        media_type="application/zip"
    )


@router.get("/batch/{batch_id}/preview")
async def preview_batch_documents(
    batch_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Preview all documents in a batch before download"""

    # Get batch documents
    documents = db.query(Document).filter(
        Document.batch_id == batch_id,
        Document.user_id == current_user.id
    ).all()

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )

    # Generate previews for completed documents
    previews = []
    for doc in documents:
        if doc.is_completed:
            preview = await DocumentService.generate_document_preview(doc.id)
            previews.append({
                "document_id": doc.id,
                "title": doc.title,
                "status": doc.status,
                "preview_url": preview.get("preview_url"),
                "thumbnail_url": preview.get("thumbnail_url"),
                "file_size": preview.get("file_size"),
                "page_count": preview.get("page_count")
            })
        else:
            previews.append({
                "document_id": doc.id,
                "title": doc.title,
                "status": doc.status,
                "preview_url": None,
                "thumbnail_url": None,
                "message": "Document still processing"
            })

    return {
        "batch_id": batch_id,
        "total_documents": len(documents),
        "completed_documents": sum(1 for doc in documents if doc.is_completed),
        "processing_documents": sum(1 for doc in documents if not doc.is_completed),
        "previews": previews,
        "can_download": all(doc.is_completed for doc in documents)
    }


@router.post("/batch/{batch_id}/token-debit")
async def debit_tokens_for_batch(
    batch_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Debit tokens for batch documents (pay for processing)"""

    # Get batch documents
    documents = db.query(Document).filter(
        Document.batch_id == batch_id,
        Document.user_id == current_user.id,
        Document.token_cost > 0,
        Document.tokens_debited == False
    ).all()

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No unpaid documents found in batch"
        )

    # Calculate total cost
    total_cost = sum(doc.token_cost for doc in documents)

    # Check user's token balance
    from app.services.wallet_service import WalletService
    balance_info = WalletService.get_wallet_balance(db, current_user.id)

    if balance_info["token_balance"] < total_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient tokens. Required: {total_cost}, Available: {balance_info['token_balance']}"
        )

    # Process token debit
    result = await WalletService.debit_tokens_for_documents(
        db=db,
        user_id=current_user.id,
        document_ids=[doc.id for doc in documents],
        total_cost=total_cost
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )

    # Mark documents as paid
    for doc in documents:
        doc.tokens_debited = True
    db.commit()

    # Log token debit
    AuditService.log_document_event(
        "BATCH_TOKENS_DEBITED",
        current_user.id,
        request,
        {
            "batch_id": batch_id,
            "document_count": len(documents),
            "total_cost": total_cost,
            "transaction_id": result["transaction_id"]
        }
    )

    return {
        "success": True,
        "message": f"Successfully debited {total_cost} tokens for {len(documents)} documents",
        "documents_processed": len(documents),
        "total_cost": total_cost,
        "remaining_balance": result["new_balance"],
        "transaction_id": result["transaction_id"]
    }


@router.post("/{document_id}/share", response_model=dict)
async def share_document(
    document_id: int,
    share_data: DocumentShare,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Share document with link"""

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Create share link
    share_info = DocumentService.create_share_link(db, document, share_data)

    # Log document sharing
    AuditService.log_document_event(
        "DOCUMENT_SHARED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "title": document.title,
            "access_level": share_data.access_level.value,
            "expires_in_days": share_data.expires_in_days
        }
    )

    return share_info


@router.get("/{document_id}/preview", response_model=DocumentPreview)
async def preview_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get document preview"""

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    preview = DocumentService.generate_preview(document)
    return preview




@router.get("/shared/{share_token}")
async def access_shared_document(
    share_token: str,
    password: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Access shared document"""

    document = db.query(Document).filter(
        Document.share_token == share_token
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared document not found"
        )

    # Validate access
    access_info = DocumentService.validate_shared_access(document, password)
    if not access_info["valid"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=access_info["error"]
        )

    # Log shared access
    AuditService.log_document_event(
        "SHARED_DOCUMENT_ACCESSED",
        None,
        request,
        {
            "document_id": document.id,
            "share_token": share_token
        }
    )

    return {
        "document": DocumentResponse.from_orm(document),
        "access_type": "shared",
        "expires_at": document.share_expires_at
    }
