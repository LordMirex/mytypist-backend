"""
Admin Template Management Routes
Handles template creation, updates, and management operations
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models.user import User
from app.models.template_management import Template, TemplateCategory
from app.services.template_service import TemplateService
from app.dependencies import get_db, get_current_admin_user
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    CategoryCreate,
    CategoryResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/templates",
    tags=["admin", "templates"],
    dependencies=[Depends(get_current_admin_user)]
)

@router.post("/", response_model=TemplateResponse)
async def create_template(
    title: str = Form(...),
    description: str = Form(...),
    template_file: UploadFile = File(...),
    preview_file: UploadFile = File(...),
    categories: List[int] = Form(...),
    metadata: Dict[str, Any] = Form(...),
    is_public: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new template (admin only)"""
    try:
        template = await TemplateService.create_template(
            db=db,
            user_id=current_user.id,
            title=title,
            description=description,
            template_file=template_file,
            preview_file=preview_file,
            categories=categories,
            metadata=metadata,
            is_public=is_public
        )
        return template
    except Exception as e:
        logger.error(f"Failed to create template: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    template_file: Optional[UploadFile] = File(None),
    preview_file: Optional[UploadFile] = File(None),
    categories: Optional[List[int]] = Form(None),
    metadata: Optional[Dict[str, Any]] = Form(None),
    is_public: Optional[bool] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update an existing template (admin only)"""
    try:
        update_data = {
            "title": title,
            "description": description,
            "categories": categories,
            "metadata": metadata,
            "is_public": is_public
        }
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}

        template = await TemplateService.update_template(
            db=db,
            template_id=template_id,
            user_id=current_user.id,
            update_data=update_data,
            template_file=template_file,
            preview_file=preview_file
        )
        return template
    except Exception as e:
        logger.error(f"Failed to update template: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{template_id}/approve")
async def approve_template(
    template_id: int,
    approval_status: str,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Approve or reject a template (admin only)"""
    try:
        template = await TemplateService.approve_template(
            db=db,
            template_id=template_id,
            admin_id=current_user.id,
            approval_status=approval_status,
            notes=notes
        )
        return {"success": True, "template": template}
    except Exception as e:
        logger.error(f"Failed to approve template: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Category Management Routes

@router.post("/categories", response_model=CategoryResponse)
async def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db)
):
    """Create a new template category"""
    try:
        db_category = TemplateCategory(**category.dict())
        db.add(db_category)
        db.commit()
        db.refresh(db_category)
        return db_category
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create category: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(
    db: Session = Depends(get_db)
):
    """List all template categories"""
    try:
        categories = db.query(TemplateCategory).all()
        return categories
    except Exception as e:
        logger.error(f"Failed to list categories: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
