"""
Blog System API Routes
Public blog access and admin content management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, validator
from datetime import datetime

from database import get_db
from app.services.auth_service import AuthService
from app.services.blog_service import BlogService, BlogCategory, BlogPost, PostStatus

router = APIRouter(prefix="/api/blog", tags=["blog"])


class CategoryCreateRequest(BaseModel):
    """Blog category creation"""
    name: str
    description: Optional[str] = None
    slug: Optional[str] = None
    color: Optional[str] = None
    sort_order: int = 0
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    @validator('name')
    def validate_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Category name must be at least 2 characters")
        return v.strip()


class PostCreateRequest(BaseModel):
    """Blog post creation"""
    category_id: Optional[int] = None
    title: str
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    content: str
    featured_image: Optional[str] = None
    featured_image_alt: Optional[str] = None
    gallery_images: Optional[List[str]] = None
    tags: Optional[str] = None
    language: str = "en"
    status: str = "draft"
    scheduled_for: Optional[str] = None
    
    # SEO fields
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    keywords: Optional[str] = None
    canonical_url: Optional[str] = None
    
    # Social sharing
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    twitter_image: Optional[str] = None
    
    # Settings
    allow_comments: bool = True
    is_featured: bool = False

    @validator('title')
    def validate_title(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("Title must be at least 5 characters")
        return v.strip()

    @validator('content')
    def validate_content(cls, v):
        if len(v.strip()) < 50:
            raise ValueError("Content must be at least 50 characters")
        return v.strip()

    @validator('status')
    def validate_status(cls, v):
        try:
            PostStatus(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid status: {v}")


class PostUpdateRequest(BaseModel):
    """Blog post update"""
    category_id: Optional[int] = None
    title: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    featured_image: Optional[str] = None
    featured_image_alt: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = None
    scheduled_for: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    keywords: Optional[str] = None
    allow_comments: Optional[bool] = None
    is_featured: Optional[bool] = None


# Public blog endpoints
@router.get("/public/categories")
async def get_public_categories(db: Session = Depends(get_db)):
    """Get all active blog categories"""
    try:
        categories = db.query(BlogCategory).filter(
            BlogCategory.is_active == True
        ).order_by(BlogCategory.sort_order, BlogCategory.name).all()
        
        category_list = []
        for cat in categories:
            post_count = db.query(BlogPost).filter(
                BlogPost.category_id == cat.id,
                BlogPost.status == PostStatus.PUBLISHED,
                BlogPost.published_at <= datetime.utcnow()
            ).count()
            
            category_list.append({
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "slug": cat.slug,
                "color": cat.color,
                "post_count": post_count,
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


@router.get("/public/posts")
async def get_public_posts(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    featured: bool = False,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get published blog posts"""
    try:
        result = BlogService.get_public_posts(
            db=db,
            category_slug=category,
            tag=tag,
            search_query=search,
            featured_only=featured,
            limit=limit,
            offset=offset
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
            detail=f"Failed to get posts: {str(e)}"
        )


@router.get("/public/posts/{slug}")
async def get_post_by_slug(
    slug: str,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Get blog post by slug with view tracking"""
    try:
        # Get visitor information for analytics
        visitor_ip = None
        session_id = None
        
        if request:
            visitor_ip = request.client.host
            if hasattr(request, 'session'):
                session_id = request.session.get('session_id')
        
        result = BlogService.get_post_by_slug(
            db=db,
            slug=slug,
            track_view=True,
            visitor_ip=visitor_ip,
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
            detail=f"Failed to get post: {str(e)}"
        )


@router.get("/public/featured")
async def get_featured_posts(
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """Get featured blog posts"""
    try:
        result = BlogService.get_public_posts(
            db=db,
            featured_only=True,
            limit=limit
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return {
            "status": "success",
            "posts": result["posts"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get featured posts: {str(e)}"
        )


# Admin blog management endpoints
@router.post("/admin/categories")
async def create_category(
    request: CategoryCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Create blog category (admin only)"""
    try:
        category_data = request.dict()
        
        result = BlogService.create_category(
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
    """List all blog categories for admin"""
    try:
        categories = db.query(BlogCategory).order_by(
            BlogCategory.sort_order, BlogCategory.name
        ).all()
        
        category_list = []
        for cat in categories:
            post_count = db.query(BlogPost).filter(BlogPost.category_id == cat.id).count()
            
            category_list.append({
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "slug": cat.slug,
                "color": cat.color,
                "sort_order": cat.sort_order,
                "is_active": cat.is_active,
                "post_count": post_count,
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


@router.post("/admin/posts")
async def create_post(
    request: PostCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Create blog post (admin only)"""
    try:
        post_data = request.dict()
        
        result = BlogService.create_post(
            db=db,
            author_id=current_user.id,
            post_data=post_data
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
            detail=f"Failed to create post: {str(e)}"
        )


@router.get("/admin/posts")
async def list_admin_posts(
    status_filter: Optional[str] = None,
    category_id: Optional[int] = None,
    author_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """List blog posts for admin management"""
    try:
        query = db.query(BlogPost)
        
        # Apply filters
        if status_filter:
            query = query.filter(BlogPost.status == PostStatus(status_filter))
        
        if category_id:
            query = query.filter(BlogPost.category_id == category_id)
            
        if author_id:
            query = query.filter(BlogPost.author_id == author_id)
        
        total = query.count()
        posts = query.order_by(
            BlogPost.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        post_list = []
        for post in posts:
            post_list.append({
                "id": post.id,
                "title": post.title,
                "slug": post.slug,
                "excerpt": post.excerpt[:150] + "..." if post.excerpt and len(post.excerpt) > 150 else post.excerpt,
                "status": post.status.value,
                "category": {
                    "id": post.category.id,
                    "name": post.category.name
                } if post.category else None,
                "author": {
                    "id": post.author.id,
                    "name": post.author.full_name or post.author.username
                },
                "is_featured": post.is_featured,
                "view_count": post.view_count,
                "comment_count": post.comment_count,
                "created_at": post.created_at.isoformat(),
                "published_at": post.published_at.isoformat() if post.published_at else None,
                "scheduled_for": post.scheduled_for.isoformat() if post.scheduled_for else None
            })
        
        return {
            "status": "success",
            "posts": post_list,
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
            detail=f"Failed to list posts: {str(e)}"
        )


@router.get("/admin/posts/{post_id}")
async def get_admin_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get blog post details for admin editing"""
    try:
        post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found"
            )
        
        return {
            "status": "success",
            "post": {
                "id": post.id,
                "category_id": post.category_id,
                "title": post.title,
                "slug": post.slug,
                "excerpt": post.excerpt,
                "content": post.content,
                "featured_image": post.featured_image,
                "featured_image_alt": post.featured_image_alt,
                "gallery_images": post.gallery_images,
                "tags": post.tags,
                "reading_time": post.reading_time,
                "language": post.language,
                "status": post.status.value,
                "published_at": post.published_at.isoformat() if post.published_at else None,
                "scheduled_for": post.scheduled_for.isoformat() if post.scheduled_for else None,
                "meta_title": post.meta_title,
                "meta_description": post.meta_description,
                "keywords": post.keywords,
                "canonical_url": post.canonical_url,
                "og_title": post.og_title,
                "og_description": post.og_description,
                "og_image": post.og_image,
                "twitter_title": post.twitter_title,
                "twitter_description": post.twitter_description,
                "twitter_image": post.twitter_image,
                "allow_comments": post.allow_comments,
                "is_featured": post.is_featured,
                "view_count": post.view_count,
                "like_count": post.like_count,
                "comment_count": post.comment_count,
                "created_at": post.created_at.isoformat(),
                "updated_at": post.updated_at.isoformat(),
                "category": {
                    "id": post.category.id,
                    "name": post.category.name
                } if post.category else None,
                "author": {
                    "id": post.author.id,
                    "name": post.author.full_name or post.author.username
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get post: {str(e)}"
        )


@router.put("/admin/posts/{post_id}")
async def update_post(
    post_id: int,
    request: PostUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Update blog post (admin only)"""
    try:
        post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found"
            )
        
        # Update fields
        update_data = request.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field == 'status' and value:
                # Handle status change
                old_status = post.status
                new_status = PostStatus(value)
                post.status = new_status
                
                # Set published_at when changing to published
                if new_status == PostStatus.PUBLISHED and old_status != PostStatus.PUBLISHED:
                    post.published_at = datetime.utcnow()
                    
            elif field == 'scheduled_for' and value:
                post.scheduled_for = datetime.fromisoformat(value)
            else:
                setattr(post, field, value)
        
        post.editor_id = current_user.id
        post.updated_at = datetime.utcnow()
        
        # Recalculate reading time if content changed
        if 'content' in update_data:
            post.reading_time = BlogService._calculate_reading_time(post.content)
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Post updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update post: {str(e)}"
        )


@router.delete("/admin/posts/{post_id}")
async def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Delete blog post (admin only)"""
    try:
        post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found"
            )
        
        db.delete(post)
        db.commit()
        
        return {
            "status": "success",
            "message": "Post deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete post: {str(e)}"
        )


@router.get("/admin/analytics")
async def get_blog_analytics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Get blog analytics (admin only)"""
    try:
        result = BlogService.get_admin_analytics(db, days)
        
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


@router.post("/admin/publish-scheduled")
async def publish_scheduled_posts(
    db: Session = Depends(get_db),
    current_user = Depends(AuthService.get_current_admin_user)
):
    """Manually trigger scheduled post publishing (admin only)"""
    try:
        published_count = BlogService.publish_scheduled_posts(db)
        
        return {
            "status": "success",
            "message": f"Published {published_count} scheduled posts"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish scheduled posts: {str(e)}"
        )