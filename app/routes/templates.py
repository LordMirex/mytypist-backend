"""
Template management routes
"""

import os
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_
import json

from database import get_db
from config import settings
from app.models.template import Template, Placeholder
from app.models.user import User, UserRole
from app.schemas.template import (
    TemplateCreate, TemplateUpdate, TemplateResponse, TemplateList,
    TemplateSearch, TemplatePreview, TemplateUpload, TemplateRating,
    TemplateStats, PlaceholderCreate, PlaceholderResponse
)
from app.services.template_service import TemplateService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user
from app.services.auth_service import AuthService

# Provide a compatible dependency name used across routes
get_current_admin_user = AuthService.get_current_admin_user
from app.schemas.template_pricing import PriceUpdate, BulkPriceUpdate, SpecialOffer
from app.utils.validation import validate_file_upload

router = APIRouter()


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    category: str = Form(...),
    type: str = Form(...),
    language: str = Form("en"),
    font_family: str = Form("Times New Roman"),
    font_size: int = Form(12),
    is_public: bool = Form(False),
    is_premium: bool = Form(False),
    price: float = Form(0.0),
    tags: Optional[str] = Form(None),  # JSON string
    file: UploadFile = File(...),
    request: Request = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new template with file upload"""

    # Validate file upload
    if not validate_file_upload(file, settings.ALLOWED_EXTENSIONS, settings.MAX_FILE_SIZE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format or size"
        )

    # Parse tags if provided
    parsed_tags = []
    if tags:
        try:
            parsed_tags = json.loads(tags)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tags format"
            )

    # Create template data object
    template_data = TemplateCreate(
        name=name,
        description=description,
        category=category,
        type=type,
        language=language,
        font_family=font_family,
        font_size=font_size,
        is_public=is_public,
        is_premium=is_premium,
        price=price,
        tags=parsed_tags
    )

    # Create template with file
    template = await TemplateService.create_template(
        db, template_data, file, current_user.id
    )

    # Log template creation
    AuditService.log_template_event(
        "TEMPLATE_CREATED",
        current_user.id,
        request,
        {
            "template_id": template.id,
            "name": template.name,
            "category": template.category
        }
    )

    return TemplateResponse.from_orm(template)


@router.get("/", response_model=TemplateList)
async def list_templates(
    page: int = 1,
    per_page: int = 20,
    category: Optional[str] = None,
    type: Optional[str] = None,
    is_public: Optional[bool] = None,
    my_templates: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List templates with pagination and filters"""

    # Build query
    query = db.query(Template).filter(Template.is_active == True)

    # Apply access filters
    if my_templates:
        query = query.filter(Template.created_by == current_user.id)
    else:
        # Show public templates and user's own templates
        query = query.filter(
            or_(
                Template.is_public == True,
                Template.created_by == current_user.id
            )
        )

    # Apply other filters
    if category:
        query = query.filter(Template.category == category)

    if type:
        query = query.filter(Template.type == type)

    if is_public is not None:
        query = query.filter(Template.is_public == is_public)

    # Get total count
    total = query.count()

    # Apply pagination and ordering
    templates = query.order_by(desc(Template.created_at)).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    # Get categories and types for filtering UI
    categories = db.query(Template.category).distinct().filter(
        Template.is_active == True,
        or_(Template.is_public == True, Template.created_by == current_user.id)
    ).all()
    categories = [cat[0] for cat in categories]

    types = db.query(Template.type).distinct().filter(
        Template.is_active == True,
        or_(Template.is_public == True, Template.created_by == current_user.id)
    ).all()
    types = [typ[0] for typ in types]

    # Calculate pagination info
    pages = (total + per_page - 1) // per_page

    return TemplateList(
        templates=[TemplateResponse.from_orm(tmpl) for tmpl in templates],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        categories=categories,
        types=types
    )


@router.get("/search", response_model=TemplateList)
async def search_templates(
    search_params: TemplateSearch = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Advanced template search"""

    templates, total = TemplateService.search_templates(
        db, current_user.id, search_params
    )

    pages = (total + search_params.per_page - 1) // search_params.per_page

    return TemplateList(
        templates=[TemplateResponse.from_orm(tmpl) for tmpl in templates],
        total=total,
        page=search_params.page,
        per_page=search_params.per_page,
        pages=pages
    )


@router.get("/categories")
async def get_template_categories(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all template categories"""

    categories = db.query(Template.category).distinct().filter(
        Template.is_active == True,
        or_(Template.is_public == True, Template.created_by == current_user.id)
    ).all()

    return {"categories": [cat[0] for cat in categories]}


@router.get("/types")
async def get_template_types(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get template types, optionally filtered by category"""

    query = db.query(Template.type).distinct().filter(
        Template.is_active == True,
        or_(Template.is_public == True, Template.created_by == current_user.id)
    )

    if category:
        query = query.filter(Template.category == category)

    types = query.all()

    return {"types": [typ[0] for typ in types]}


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get template by ID"""

    template = db.query(Template).filter(
        Template.id == template_id,
        Template.is_active == True
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    # Check access permissions
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )

    return TemplateResponse.from_orm(template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_update: TemplateUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update template"""

    template = db.query(Template).filter(
        Template.id == template_id,
        Template.created_by == current_user.id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or access denied"
        )

    # Update template
    updated_template = TemplateService.update_template(db, template, template_update)

    # Log template update
    AuditService.log_template_event(
        "TEMPLATE_UPDATED",
        current_user.id,
        request,
        {
            "template_id": template.id,
            "name": template.name,
            "updated_fields": list(template_update.dict(exclude_unset=True).keys())
        }
    )

    return TemplateResponse.from_orm(updated_template)


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete template"""

    template = db.query(Template).filter(
        Template.id == template_id,
        Template.created_by == current_user.id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or access denied"
        )

    # Soft delete
    TemplateService.delete_template(db, template)

    # Log template deletion
    AuditService.log_template_event(
        "TEMPLATE_DELETED",
        current_user.id,
        request,
        {
            "template_id": template.id,
            "name": template.name
        }
    )

    return {"message": "Template deleted successfully"}


@router.get("/{template_id}/preview", response_model=TemplatePreview)
async def preview_template(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get template preview"""

    template = db.query(Template).filter(
        Template.id == template_id,
        Template.is_active == True
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    # Check access permissions
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )

    preview = TemplateService.generate_preview(template)
    return preview


@router.get("/home")
async def templates_home(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get templates homepage data (featured, trending, new)."""

    data = TemplateService.get_templates_home(db, current_user.id)
    return data


@router.post("/{template_id}/purchase")
async def purchase_template(
    template_id: int,
    payment_method: str = Form('tokens'),
    request: Request = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Purchase a template using tokens or wallet."""

    result = TemplateService.purchase_template(db, template_id, current_user.id, payment_method)

    if not result.get("success", False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "Purchase failed"))

    AuditService.log_template_event(
        "TEMPLATE_PURCHASED",
        current_user.id,
        request,
        {"template_id": template_id, "purchase_id": result.get("purchase_id"), "amount": result.get("amount")}
    )

    return result


@router.post("/{template_id}/review")
async def add_template_review(
    template_id: int,
    rating: int = Form(...),
    title: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    request: Request = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add or update a review for a template."""

    res = TemplateService.add_template_review(db, template_id, current_user.id, rating, title, comment)
    if not res.get("success", False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.get("error", "Failed to add review"))

    AuditService.log_template_event(
        "TEMPLATE_REVIEWED",
        current_user.id,
        request,
        {"template_id": template_id, "review_id": res.get("review_id"), "rating": rating}
    )

    return {"message": "Review added successfully", "review_id": res.get("review_id")}


@router.post("/{template_id}/favorite")
async def toggle_favorite(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Toggle favorite status for a template."""

    res = TemplateService.toggle_favorite(db, template_id, current_user.id)
    if not res.get("success", False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to toggle favorite")

    return {"message": "Favorite toggled", "is_favorited": res.get("is_favorited")}


@router.get("/my/purchases")
async def my_purchases(
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's template purchases."""
    return TemplateService.get_user_purchases(db, current_user.id, page, per_page)


@router.get("/my/favorites")
async def my_favorites(
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's favorite templates."""
    return TemplateService.get_user_favorites(db, current_user.id, page, per_page)


@router.get("/stats")
async def templates_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get global template statistics."""
    return TemplateService.get_template_stats(db)


@router.get("/{template_id}/download", response_class=FileResponse)
async def download_template(
    template_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Download template file"""

    template = db.query(Template).filter(
        Template.id == template_id,
        Template.is_active == True
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    # Check access permissions
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )

    file_path = os.path.join(settings.TEMPLATES_PATH, template.file_path)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template file not found"
        )

    # Update download count
    template.download_count += 1
    db.commit()

    # Log template download
    AuditService.log_template_event(
        "TEMPLATE_DOWNLOADED",
        current_user.id,
        request,
        {
            "template_id": template.id,
            "name": template.name
        }
    )

    return FileResponse(
        path=file_path,
        filename=template.original_filename,
        media_type="application/octet-stream"
    )


@router.post("/{template_id}/rate")
async def rate_template(
    template_id: int,
    rating_data: TemplateRating,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Rate a template"""

    template = db.query(Template).filter(
        Template.id == template_id,
        Template.is_active == True,
        Template.is_public == True
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or not public"
        )

    # Update template rating
    TemplateService.rate_template(db, template, current_user.id, rating_data)

    # Log template rating
    AuditService.log_template_event(
        "TEMPLATE_RATED",
        current_user.id,
        request,
        {
            "template_id": template.id,
            "rating": rating_data.rating,
            "comment": rating_data.comment
        }
    )

    return {"message": "Template rated successfully"}


@router.get("/{template_id}/placeholders", response_model=List[PlaceholderResponse])
async def get_template_placeholders(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get template placeholders"""

    template = db.query(Template).filter(
        Template.id == template_id,
        Template.is_active == True
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    # Check access permissions
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )

    placeholders = db.query(Placeholder).filter(
        Placeholder.template_id == template_id
    ).order_by(
        Placeholder.paragraph_index,
        Placeholder.start_run_index
    ).all()

    return [PlaceholderResponse.from_orm(ph) for ph in placeholders]


@router.post("/{template_id}/use")
async def use_template(
    template_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Track template usage"""

    template = db.query(Template).filter(
        Template.id == template_id,
        Template.is_active == True
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    # Check access permissions
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )

    # Update usage count
    template.usage_count += 1
    db.commit()

    # Log template usage
    AuditService.log_template_event(
        "TEMPLATE_USED",
        current_user.id,
        request,
        {
            "template_id": template.id,
            "name": template.name
        }
    )

    return {"message": "Template usage tracked"}


@router.get("/my/stats", response_model=List[TemplateStats])
async def get_my_template_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get statistics for user's templates"""

    templates = db.query(Template).filter(
        Template.created_by == current_user.id,
        Template.is_active == True
    ).all()

    stats = []
    for template in templates:
        stats.append(TemplateStats(
            id=template.id,
            name=template.name,
            usage_count=template.usage_count,
            download_count=template.download_count,
            rating=template.rating,
            rating_count=template.rating_count,
            revenue=template.price * template.usage_count if template.is_premium else 0,
            created_at=template.created_at,
            last_used=TemplateService.get_last_used_date(db, template.id, current_user.id)
        ))

    return stats

@router.put("/{template_id}/price", response_model=Dict[str, Any])
async def update_template_price(
    template_id: int,
    price_update: PriceUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update price for a single template"""
    try:
        template = await TemplateService.update_template_price(db, template_id, price_update.new_price)
        return {
            "status": "success",
            "template_id": template.id,
            "new_price": template.price
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/price/bulk", response_model=Dict[str, Any])
async def update_bulk_prices(
    price_update: BulkPriceUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update prices in bulk for templates"""
    try:
        updated = await TemplateService.bulk_update_prices(
            db,
            price_update.filter_type,
            price_update.filter_value,
            price_update.price_change,
            price_update.operation
        )
        return {
            "status": "success",
            "updated_count": updated,
            "message": f"Successfully updated {updated} template prices"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{template_id}/special-offer", response_model=Dict[str, Any])
async def set_special_offer(
    template_id: int,
    offer: SpecialOffer,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Set a special offer/discount for a template"""
    try:
        template = await TemplateService.set_special_offer(
            db,
            template_id,
            offer.discount_percent,
            offer.start_date,
            offer.end_date
        )
        return {
            "status": "success",
            "template_id": template.id,
            "original_price": template.special_offer["original_price"],
            "discounted_price": template.price,
            "discount_percent": offer.discount_percent,
            "offer_ends": offer.end_date.isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
