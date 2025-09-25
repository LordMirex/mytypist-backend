"""
Dynamic FAQ Management API Routes
Public FAQ access and admin management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, validator

from database import get_db
from app.services.auth_service import AuthService
from app.services.faq_service import FAQService, FAQCategory, FAQ

router = APIRouter(prefix="/api/faq", tags=["faq"])


class CategoryCreateRequest(BaseModel):
    """Request to create FAQ category"""
    name: str
    description: Optional[str] = None
    slug: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int = 0
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    @validator('name')
    def validate_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Category name must be at least 2 characters")
        return v.strip()


class FAQCreateRequest(BaseModel):
    """Request to create FAQ"""
    category_id: int
    question: str
    answer: str
    short_answer: Optional[str] = None
    slug: Optional[str] = None
    tags: Optional[str] = None
    sort_order: int = 0
    is_featured: bool = False
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    keywords: Optional[str] = None

    @validator('question')
    def validate_question(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("Question must be at least 5 characters")
        return v.strip()

    @validator('answer')
    def validate_answer(cls, v):
        if len(v.strip()) < 10:
            raise ValueError("Answer must be at least 10 characters")
        return v.strip()


class FAQUpdateRequest(BaseModel):
    """Request to update FAQ"""
    question: Optional[str] = None
    answer: Optional[str] = None
    short_answer: Optional[str] = None
    tags: Optional[str] = None
    sort_order: Optional[int] = None
    is_featured: Optional[bool] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    keywords: Optional[str] = None
    is_active: Optional[bool] = None


class FeedbackRequest(BaseModel):
    """Request to provide feedback on FAQ"""
    is_helpful: bool


# Public FAQ endpoints
@router.get("/public/categories")
async def get_public_categories(db: Session = Depends(get_db)):
    """Get all active FAQ categories for public display"""
    try:
        categories = db.query(FAQCategory).filter(
            FAQCategory.is_active == True
        ).order_by(FAQCategory.sort_order, FAQCategory.name).all()
        
        category_list = []
        for cat in categories:
            faq_count = db.query(FAQ).filter(
                FAQ.category_id == cat.id,
                FAQ.is_active == True
            ).count()
            
            category_list.append({
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "slug": cat.slug,
                "icon": cat.icon,
                "faq_count": faq_count,
                "meta_title": cat.meta_title,
                "meta_description": cat.meta_description
            })
        
        return {
            "status": "success",
            "categories": category_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get categories: {str(e)}"
        )


@router.get("/public/list")
async def get_public_faqs(
    category: Optional[str] = None,
    search: Optional[str] = None,
    featured: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get FAQs for public display with optional filtering"""
    try:
        result = FAQService.get_public_faqs(
            db=db,
            category_slug=category,
            search_query=search,
            featured_only=featured,
            limit=limit
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get FAQs: {str(e)}"
        )


@router.get("/public/search")
async def search_faqs(
    q: str,
    limit: int = 20,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Search FAQs with relevance ranking"""
    try:
        # Get session ID for tracking
        session_id = None
        if request and hasattr(request, 'session'):
            session_id = request.session.get('session_id')
        
        result = FAQService.search_faqs(
            db=db,
            query=q,
            limit=limit,
            session_id=session_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search FAQs: {str(e)}"
        )


@router.get("/public/{slug}")
async def get_faq_by_slug(
    slug: str,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Get specific FAQ by slug with view tracking"""
    try:
        # Get session ID for tracking
        session_id = None
        if request and hasattr(request, 'session'):
            session_id = request.session.get('session_id')
        
        result = FAQService.get_faq_by_slug(
            db=db,
            slug=slug,
            track_view=True,
            session_id=session_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get FAQ: {str(e)}"
        )


@router.post("/public/{faq_id}/feedback")
async def record_faq_feedback(
    faq_id: int,
    request_data: FeedbackRequest,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Record user feedback on FAQ helpfulness"""
    try:
        # Get session ID for tracking
        session_id = None
        if request and hasattr(request, 'session'):
            session_id = request.session.get('session_id')
        
        result = FAQService.record_feedback(
            db=db,
            faq_id=faq_id,
            is_helpful=request_data.is_helpful,
            session_id=session_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record feedback: {str(e)}"
        )


# Admin FAQ management endpoints
@router.post("/admin/categories")
async def create_category(
    request: CategoryCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Create new FAQ category (admin only)"""
    try:
        category_data = request.dict()
        
        result = FAQService.create_category(
            db=db,
            admin_user_id=current_user.id,
            category_data=category_data
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create category: {str(e)}"
        )


@router.get("/admin/categories")
async def list_admin_categories(
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """List all FAQ categories for admin (admin only)"""
    try:
        categories = db.query(FAQCategory).order_by(
            FAQCategory.sort_order, FAQCategory.name
        ).all()
        
        category_list = []
        for cat in categories:
            faq_count = db.query(FAQ).filter(FAQ.category_id == cat.id).count()
            
            category_list.append({
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "slug": cat.slug,
                "icon": cat.icon,
                "sort_order": cat.sort_order,
                "is_active": cat.is_active,
                "faq_count": faq_count,
                "created_at": cat.created_at.isoformat(),
                "updated_at": cat.updated_at.isoformat()
            })
        
        return {
            "status": "success",
            "categories": category_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list categories: {str(e)}"
        )


@router.post("/admin/faqs")
async def create_faq(
    request: FAQCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Create new FAQ (admin only)"""
    try:
        faq_data = request.dict()
        
        result = FAQService.create_faq(
            db=db,
            admin_user_id=current_user.id,
            faq_data=faq_data
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create FAQ: {str(e)}"
        )


@router.get("/admin/faqs")
async def list_admin_faqs(
    category_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """List FAQs for admin management (admin only)"""
    try:
        query = db.query(FAQ).join(FAQCategory)
        
        if category_id:
            query = query.filter(FAQ.category_id == category_id)
        
        total = query.count()
        faqs = query.order_by(
            FAQ.sort_order, FAQ.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        faq_list = []
        for faq in faqs:
            faq_list.append({
                "id": faq.id,
                "question": faq.question,
                "answer": faq.answer[:200] + "..." if len(faq.answer) > 200 else faq.answer,
                "slug": faq.slug,
                "category": {
                    "id": faq.category.id,
                    "name": faq.category.name
                },
                "sort_order": faq.sort_order,
                "is_featured": faq.is_featured,
                "is_active": faq.is_active,
                "view_count": faq.view_count,
                "helpful_count": faq.helpful_count,
                "unhelpful_count": faq.unhelpful_count,
                "helpfulness_ratio": round(
                    faq.helpful_count / (faq.helpful_count + faq.unhelpful_count) * 100, 1
                ) if (faq.helpful_count + faq.unhelpful_count) > 0 else 0,
                "created_at": faq.created_at.isoformat(),
                "updated_at": faq.updated_at.isoformat(),
                "review_required": faq.review_required
            })
        
        return {
            "status": "success",
            "faqs": faq_list,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total,
                "has_more": skip + limit < total
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list FAQs: {str(e)}"
        )


@router.get("/admin/faqs/{faq_id}")
async def get_admin_faq(
    faq_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get FAQ details for admin editing (admin only)"""
    try:
        faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
        
        if not faq:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="FAQ not found"
            )
        
        return {
            "status": "success",
            "faq": {
                "id": faq.id,
                "category_id": faq.category_id,
                "question": faq.question,
                "answer": faq.answer,
                "short_answer": faq.short_answer,
                "slug": faq.slug,
                "tags": faq.tags,
                "sort_order": faq.sort_order,
                "is_featured": faq.is_featured,
                "is_active": faq.is_active,
                "meta_title": faq.meta_title,
                "meta_description": faq.meta_description,
                "keywords": faq.keywords,
                "view_count": faq.view_count,
                "helpful_count": faq.helpful_count,
                "unhelpful_count": faq.unhelpful_count,
                "created_at": faq.created_at.isoformat(),
                "updated_at": faq.updated_at.isoformat(),
                "review_required": faq.review_required,
                "category": {
                    "id": faq.category.id,
                    "name": faq.category.name
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get FAQ: {str(e)}"
        )


@router.put("/admin/faqs/{faq_id}")
async def update_faq(
    faq_id: int,
    request: FAQUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Update FAQ (admin only)"""
    try:
        faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
        
        if not faq:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="FAQ not found"
            )
        
        # Update fields
        update_data = request.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(faq, field, value)
        
        faq.updated_by = current_user.id
        faq.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "status": "success",
            "message": "FAQ updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update FAQ: {str(e)}"
        )


@router.delete("/admin/faqs/{faq_id}")
async def delete_faq(
    faq_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Delete FAQ (admin only)"""
    try:
        faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
        
        if not faq:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="FAQ not found"
            )
        
        db.delete(faq)
        db.commit()
        
        return {
            "status": "success",
            "message": "FAQ deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete FAQ: {str(e)}"
        )


@router.get("/admin/analytics")
async def get_faq_analytics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get FAQ analytics for admin dashboard (admin only)"""
    try:
        result = FAQService.get_admin_analytics(db, days)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics: {str(e)}"
        )