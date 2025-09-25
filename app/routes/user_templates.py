"""
User Template Upload Routes
Allow users to upload documents, extract placeholders, and make them public/private
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from app.models.user import User
from app.services.user_template_upload_service import UserTemplateUploadService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user

router = APIRouter()


class UpdateVisibilityRequest(BaseModel):
    """Request model for updating template visibility"""
    visibility: str


class AdminApprovalRequest(BaseModel):
    """Request model for admin template approval"""
    approved: bool
    price_tokens: Optional[int] = None
    review_notes: Optional[str] = None


@router.post("/upload", response_model=Dict[str, Any])
async def upload_user_template(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # JSON string of tags array
    visibility: str = Form("private"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload a new template document"""
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )

        # Check file size (10MB limit)
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size must be less than 10MB"
            )

        # Parse tags
        tags_list = []
        if tags:
            try:
                import json
                tags_list = json.loads(tags)
            except:
                tags_list = [tag.strip() for tag in tags.split(',') if tag.strip()]

        # Validate visibility
        valid_visibilities = ["private", "public"]
        if visibility not in valid_visibilities:
            visibility = "private"

        result = UserTemplateUploadService.upload_user_template(
            db=db,
            user_id=current_user.id,
            file_data=file_content,
            filename=file.filename,
            title=title,
            description=description,
            category=category,
            tags=tags_list,
            visibility=visibility
        )

        if result["success"]:
            # Log template upload
            AuditService.log_user_activity(
                db,
                current_user.id,
                "USER_TEMPLATE_UPLOADED",
                {
                    "template_id": result["template_id"],
                    "title": title,
                    "filename": file.filename,
                    "visibility": visibility
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload template: {str(e)}"
        )


@router.get("/my-templates", response_model=Dict[str, Any])
async def get_my_templates(
    visibility: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's uploaded templates"""
    try:
        result = UserTemplateUploadService.get_user_templates(
            db=db,
            user_id=current_user.id,
            visibility=visibility,
            limit=limit
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get templates: {str(e)}"
        )


@router.get("/{template_id}", response_model=Dict[str, Any])
async def get_template_details(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a user template"""
    try:
        from app.services.user_template_upload_service import UserUploadedTemplate

        template = db.query(UserUploadedTemplate).filter(
            UserUploadedTemplate.id == template_id
        ).first()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )

        # Check access permissions
        if template.user_id != current_user.id and not current_user.is_admin:
            # Check if template is public
            if template.visibility != "public" or not template.admin_approved:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )

        # Parse placeholders
        placeholders = []
        if template.extracted_placeholders:
            try:
                import json
                placeholders = json.loads(template.extracted_placeholders)
            except:
                pass

        # Parse tags
        tags = []
        if template.tags:
            try:
                import json
                tags = json.loads(template.tags)
            except:
                pass

        # Get extraction logs if owner or admin
        extraction_logs = []
        if template.user_id == current_user.id or current_user.is_admin:
            from app.services.user_template_upload_service import PlaceholderExtractionLog
            logs = db.query(PlaceholderExtractionLog).filter(
                PlaceholderExtractionLog.template_id == template_id
            ).order_by(PlaceholderExtractionLog.created_at.desc()).limit(5).all()

            extraction_logs = [
                {
                    "id": log.id,
                    "method": log.extraction_method,
                    "placeholders_found": log.placeholders_found,
                    "success": log.success,
                    "error_message": log.error_message,
                    "extraction_time_ms": log.extraction_time_ms,
                    "created_at": log.created_at.isoformat()
                } for log in logs
            ]

        return {
            "success": True,
            "template": {
                "id": template.id,
                "title": template.title,
                "description": template.description,
                "category": template.category,
                "tags": tags,
                "original_filename": template.original_filename,
                "file_size_bytes": template.file_size_bytes,
                "file_type": template.file_type,
                "placeholder_count": template.placeholder_count,
                "placeholders": placeholders,
                "visibility": template.visibility,
                "admin_approved": template.admin_approved,
                "admin_review_notes": template.admin_review_notes,
                "price_tokens": template.price_tokens,
                "views_count": template.views_count,
                "downloads_count": template.downloads_count,
                "revenue_generated": template.revenue_generated,
                "extraction_status": template.extraction_status,
                "extraction_error": template.extraction_error,
                "is_owner": template.user_id == current_user.id,
                "created_at": template.created_at.isoformat(),
                "updated_at": template.updated_at.isoformat()
            },
            "extraction_logs": extraction_logs
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get template details: {str(e)}"
        )


@router.put("/{template_id}/visibility", response_model=Dict[str, Any])
async def update_template_visibility(
    template_id: int,
    visibility_request: UpdateVisibilityRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update template visibility (private/public)"""
    try:
        result = UserTemplateUploadService.update_template_visibility(
            db=db,
            template_id=template_id,
            user_id=current_user.id,
            visibility=visibility_request.visibility
        )

        if result["success"]:
            # Log visibility change
            AuditService.log_user_activity(
                db,
                current_user.id,
                "TEMPLATE_VISIBILITY_UPDATED",
                {
                    "template_id": template_id,
                    "new_visibility": visibility_request.visibility
                }
            )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update visibility: {str(e)}"
        )


@router.delete("/{template_id}", response_model=Dict[str, Any])
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a user template"""
    try:
        from app.services.user_template_upload_service import UserUploadedTemplate

        template = db.query(UserUploadedTemplate).filter(
            UserUploadedTemplate.id == template_id,
            UserUploadedTemplate.user_id == current_user.id
        ).first()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )

        # Soft delete
        template.is_active = False
        template.updated_at = datetime.utcnow()

        db.commit()

        # Log deletion
        AuditService.log_user_activity(
            db,
            current_user.id,
            "USER_TEMPLATE_DELETED",
            {
                "template_id": template_id,
                "title": template.title
            }
        )

        return {
            "success": True,
            "template_id": template_id,
            "message": "Template deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete template: {str(e)}"
        )


@router.post("/{template_id}/re-extract", response_model=Dict[str, Any])
async def re_extract_placeholders(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Re-run placeholder extraction on template"""
    try:
        from app.services.user_template_upload_service import UserUploadedTemplate

        template = db.query(UserUploadedTemplate).filter(
            UserUploadedTemplate.id == template_id,
            UserUploadedTemplate.user_id == current_user.id
        ).first()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )

        # Re-run extraction
        extraction_result = UserTemplateUploadService._extract_placeholders(
            db, template_id, template.file_path
        )

        # Log re-extraction
        AuditService.log_user_activity(
            db,
            current_user.id,
            "TEMPLATE_RE_EXTRACTED",
            {
                "template_id": template_id,
                "extraction_success": extraction_result.get("success", False),
                "placeholders_found": extraction_result.get("placeholders_count", 0)
            }
        )

        return extraction_result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to re-extract placeholders: {str(e)}"
        )


@router.get("/admin/review-queue", response_model=Dict[str, Any])
async def get_template_review_queue(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get queue of templates pending admin review"""


@router.post("/admin/{template_id}/approve", response_model=Dict[str, Any])
async def admin_approve_template(
    template_id: int,
    approval_request: AdminApprovalRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Approve or reject user template (admin only)"""
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        result = UserTemplateUploadService.admin_approve_template(
            db=db,
            template_id=template_id,
            admin_user_id=current_user.id,
            approved=approval_request.approved,
            price_tokens=approval_request.price_tokens,
            review_notes=approval_request.review_notes
        )

        if result["success"]:
            # Log admin action
            AuditService.log_user_activity(
                db,
                current_user.id,
                "ADMIN_TEMPLATE_REVIEWED",
                {
                    "template_id": template_id,
                    "approved": approval_request.approved,
                    "price_tokens": approval_request.price_tokens
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve template: {str(e)}"
        )


@router.get("/public/browse", response_model=Dict[str, Any])
async def browse_public_templates(
    category: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Browse public user-uploaded templates"""
    try:
        from app.services.user_template_upload_service import UserUploadedTemplate
        from app.models.user import User

        query = db.query(UserUploadedTemplate).filter(
            UserUploadedTemplate.visibility == "public",
            UserUploadedTemplate.admin_approved == True,
            UserUploadedTemplate.is_active == True
        )

        if category:
            query = query.filter(UserUploadedTemplate.category == category)

        if tags:
            # Simple tag search - in production, use full-text search
            query = query.filter(UserUploadedTemplate.tags.contains(tags))

        templates = query.order_by(
            UserUploadedTemplate.downloads_count.desc(),
            UserUploadedTemplate.created_at.desc()
        ).offset(offset).limit(limit).all()

        templates_data = []
        for template in templates:
            # Get user info
            user = db.query(User).filter(User.id == template.user_id).first()

            # Parse tags
            tags_list = []
            if template.tags:
                try:
                    import json
                    tags_list = json.loads(template.tags)
                except:
                    pass

            templates_data.append({
                "template_id": template.id,
                "title": template.title,
                "description": template.description,
                "category": template.category,
                "tags": tags_list,
                "placeholder_count": template.placeholder_count,
                "price_tokens": template.price_tokens or 0,
                "views_count": template.views_count,
                "downloads_count": template.downloads_count,
                "created_by": {
                    "name": f"{user.first_name} {user.last_name}" if user else "Unknown",
                    "id": user.id if user else None
                },
                "created_at": template.created_at.isoformat()
            })

        return {
            "success": True,
            "templates": templates_data,
            "total_count": len(templates_data),
            "offset": offset,
            "limit": limit
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to browse public templates: {str(e)}"
        )


@router.get("/admin/statistics", response_model=Dict[str, Any])
async def get_user_template_statistics(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user template upload statistics (admin only)"""
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        from datetime import datetime, timedelta
        from app.services.user_template_upload_service import UserUploadedTemplate
        from sqlalchemy import func

        start_date = datetime.utcnow() - timedelta(days=days)

        # Basic statistics
        total_templates = db.query(UserUploadedTemplate).filter(
            UserUploadedTemplate.is_active == True
        ).count()

        recent_uploads = db.query(UserUploadedTemplate).filter(
            UserUploadedTemplate.created_at >= start_date,
            UserUploadedTemplate.is_active == True
        ).count()

        public_templates = db.query(UserUploadedTemplate).filter(
            UserUploadedTemplate.visibility == "public",
            UserUploadedTemplate.admin_approved == True,
            UserUploadedTemplate.is_active == True
        ).count()

        pending_review = db.query(UserUploadedTemplate).filter(
            UserUploadedTemplate.visibility == "pending_review",
            UserUploadedTemplate.is_active == True
        ).count()

        # Extraction success rate
        successful_extractions = db.query(UserUploadedTemplate).filter(
            UserUploadedTemplate.extraction_status == "completed",
            UserUploadedTemplate.created_at >= start_date
        ).count()

        extraction_success_rate = (successful_extractions / max(recent_uploads, 1)) * 100

        # Top categories
        category_stats = db.query(
            UserUploadedTemplate.category,
            func.count(UserUploadedTemplate.id).label('count')
        ).filter(
            UserUploadedTemplate.is_active == True,
            UserUploadedTemplate.category.isnot(None)
        ).group_by(
            UserUploadedTemplate.category
        ).order_by(
            func.count(UserUploadedTemplate.id).desc()
        ).limit(10).all()

        return {
            "success": True,
            "period_days": days,
            "statistics": {
                "total_templates": total_templates,
                "recent_uploads": recent_uploads,
                "public_templates": public_templates,
                "pending_review": pending_review,
                "approval_rate": round((public_templates / max(total_templates, 1)) * 100, 1),
                "extraction_success_rate": round(extraction_success_rate, 1),
                "uploads_per_day": round(recent_uploads / max(days, 1), 1)
            },
            "top_categories": [
                {
                    "category": cat.category,
                    "count": cat.count
                } for cat in category_stats
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )
