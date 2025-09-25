"""
Blog System with Admin Content Management
Comprehensive blogging platform with SEO optimization and analytics
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, JSON, func
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum

from database import Base
from app.models.user import User

logger = logging.getLogger(__name__)


class PostStatus(str, PyEnum):
    """Blog post status"""
    DRAFT = "draft"
    PUBLISHED = "published"
    SCHEDULED = "scheduled"
    ARCHIVED = "archived"


class BlogCategory(Base):
    """Blog post categories"""
    __tablename__ = "blog_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    slug = Column(String(150), nullable=False, unique=True, index=True)
    color = Column(String(20), nullable=True)  # Hex color for UI
    sort_order = Column(Integer, default=0, index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # SEO
    meta_title = Column(String(100), nullable=True)
    meta_description = Column(String(160), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    posts = relationship("BlogPost", back_populates="category")


class BlogPost(Base):
    """Blog posts with full CMS functionality"""
    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey('blog_categories.id'), nullable=True, index=True)
    
    # Content
    title = Column(String(255), nullable=False)
    slug = Column(String(300), nullable=False, unique=True, index=True)
    excerpt = Column(Text, nullable=True)  # Short description
    content = Column(Text, nullable=False)  # Full post content (Markdown/HTML)
    
    # Media
    featured_image = Column(String(500), nullable=True)
    featured_image_alt = Column(String(255), nullable=True)
    gallery_images = Column(JSON, nullable=True)  # Array of image URLs
    
    # Metadata
    tags = Column(Text, nullable=True)  # Comma-separated tags
    reading_time = Column(Integer, nullable=True)  # Estimated reading time in minutes
    language = Column(String(10), default="en")
    
    # Status and publishing
    status = Column(Enum(PostStatus), default=PostStatus.DRAFT, index=True)
    published_at = Column(DateTime, nullable=True, index=True)
    scheduled_for = Column(DateTime, nullable=True, index=True)
    
    # SEO
    meta_title = Column(String(100), nullable=True)
    meta_description = Column(String(160), nullable=True)
    keywords = Column(String(500), nullable=True)
    canonical_url = Column(String(500), nullable=True)
    
    # Social sharing
    og_title = Column(String(100), nullable=True)
    og_description = Column(String(200), nullable=True)
    og_image = Column(String(500), nullable=True)
    
    twitter_title = Column(String(100), nullable=True)
    twitter_description = Column(String(200), nullable=True)
    twitter_image = Column(String(500), nullable=True)
    
    # Analytics
    view_count = Column(Integer, default=0)
    unique_views = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    
    # Content settings
    allow_comments = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False, index=True)
    is_trending = Column(Boolean, default=False)
    
    # Author and management
    author_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    editor_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_reviewed = Column(DateTime, nullable=True)
    
    # Relationships
    category = relationship("BlogCategory", back_populates="posts")
    author = relationship("User", foreign_keys=[author_id])
    editor = relationship("User", foreign_keys=[editor_id])


class BlogComment(Base):
    """Blog post comments"""
    __tablename__ = "blog_comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey('blog_posts.id'), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey('blog_comments.id'), nullable=True, index=True)  # For nested comments
    
    # Comment content
    author_name = Column(String(100), nullable=False)
    author_email = Column(String(255), nullable=False)
    author_website = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    
    # Status and moderation
    is_approved = Column(Boolean, default=False, index=True)
    is_spam = Column(Boolean, default=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Relationships
    post = relationship("BlogPost")
    parent = relationship("BlogComment", remote_side=[id])


class BlogView(Base):
    """Blog post view tracking"""
    __tablename__ = "blog_views"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey('blog_posts.id'), nullable=False, index=True)
    
    # Visitor information
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    referer = Column(String(500), nullable=True)
    session_id = Column(String(100), nullable=True)
    
    # Geographic data
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    post = relationship("BlogPost")


class BlogService:
    """Service for blog content management"""

    @staticmethod
    def create_category(
        db: Session,
        admin_user_id: int,
        category_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create blog category"""
        try:
            # Generate slug if not provided
            slug = category_data.get('slug') or BlogService._generate_slug(category_data['name'])
            
            # Check if slug already exists
            existing = db.query(BlogCategory).filter(BlogCategory.slug == slug).first()
            if existing:
                return {"success": False, "message": "Category slug already exists"}
            
            category = BlogCategory(
                name=category_data['name'],
                description=category_data.get('description'),
                slug=slug,
                color=category_data.get('color'),
                sort_order=category_data.get('sort_order', 0),
                meta_title=category_data.get('meta_title'),
                meta_description=category_data.get('meta_description')
            )
            
            db.add(category)
            db.commit()
            db.refresh(category)
            
            return {
                "success": True,
                "category_id": category.id,
                "message": "Category created successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to create blog category: {e}")
            db.rollback()
            return {"success": False, "message": str(e)}

    @staticmethod
    def create_post(
        db: Session,
        author_id: int,
        post_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create blog post"""
        try:
            # Generate slug if not provided
            slug = post_data.get('slug') or BlogService._generate_slug(post_data['title'])
            
            # Ensure slug is unique
            existing = db.query(BlogPost).filter(BlogPost.slug == slug).first()
            if existing:
                counter = 1
                while existing:
                    new_slug = f"{slug}-{counter}"
                    existing = db.query(BlogPost).filter(BlogPost.slug == new_slug).first()
                    if not existing:
                        slug = new_slug
                        break
                    counter += 1
            
            # Calculate reading time (rough estimate: 200 words per minute)
            reading_time = BlogService._calculate_reading_time(post_data.get('content', ''))
            
            # Set published_at if status is published
            published_at = None
            if post_data.get('status') == PostStatus.PUBLISHED.value:
                published_at = datetime.utcnow()
            
            post = BlogPost(
                category_id=post_data.get('category_id'),
                title=post_data['title'],
                slug=slug,
                excerpt=post_data.get('excerpt'),
                content=post_data['content'],
                featured_image=post_data.get('featured_image'),
                featured_image_alt=post_data.get('featured_image_alt'),
                gallery_images=post_data.get('gallery_images'),
                tags=post_data.get('tags'),
                reading_time=reading_time,
                language=post_data.get('language', 'en'),
                status=PostStatus(post_data.get('status', PostStatus.DRAFT.value)),
                published_at=published_at,
                scheduled_for=datetime.fromisoformat(post_data['scheduled_for']) if post_data.get('scheduled_for') else None,
                meta_title=post_data.get('meta_title'),
                meta_description=post_data.get('meta_description'),
                keywords=post_data.get('keywords'),
                canonical_url=post_data.get('canonical_url'),
                og_title=post_data.get('og_title'),
                og_description=post_data.get('og_description'),
                og_image=post_data.get('og_image'),
                twitter_title=post_data.get('twitter_title'),
                twitter_description=post_data.get('twitter_description'),
                twitter_image=post_data.get('twitter_image'),
                allow_comments=post_data.get('allow_comments', True),
                is_featured=post_data.get('is_featured', False),
                author_id=author_id
            )
            
            db.add(post)
            db.commit()
            db.refresh(post)
            
            return {
                "success": True,
                "post_id": post.id,
                "slug": post.slug,
                "message": "Blog post created successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to create blog post: {e}")
            db.rollback()
            return {"success": False, "message": str(e)}

    @staticmethod
    def get_public_posts(
        db: Session,
        category_slug: str = None,
        tag: str = None,
        search_query: str = None,
        featured_only: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get published posts for public display"""
        try:
            query = db.query(BlogPost).filter(
                BlogPost.status == PostStatus.PUBLISHED,
                BlogPost.published_at <= datetime.utcnow()
            )
            
            # Filter by category
            if category_slug:
                query = query.join(BlogCategory).filter(
                    BlogCategory.slug == category_slug,
                    BlogCategory.is_active == True
                )
            
            # Filter by tag
            if tag:
                query = query.filter(BlogPost.tags.like(f"%{tag}%"))
            
            # Search functionality
            if search_query:
                search_term = f"%{search_query}%"
                query = query.filter(
                    BlogPost.title.ilike(search_term) |
                    BlogPost.content.ilike(search_term) |
                    BlogPost.excerpt.ilike(search_term) |
                    BlogPost.tags.ilike(search_term)
                )
            
            # Featured filter
            if featured_only:
                query = query.filter(BlogPost.is_featured == True)
            
            # Get total count
            total = query.count()
            
            # Order by published date and apply pagination
            posts = query.order_by(
                BlogPost.published_at.desc()
            ).offset(offset).limit(limit).all()
            
            # Format response
            post_list = []
            for post in posts:
                post_list.append({
                    "id": post.id,
                    "title": post.title,
                    "slug": post.slug,
                    "excerpt": post.excerpt,
                    "featured_image": post.featured_image,
                    "featured_image_alt": post.featured_image_alt,
                    "category": {
                        "id": post.category.id,
                        "name": post.category.name,
                        "slug": post.category.slug,
                        "color": post.category.color
                    } if post.category else None,
                    "tags": post.tags.split(',') if post.tags else [],
                    "reading_time": post.reading_time,
                    "is_featured": post.is_featured,
                    "view_count": post.view_count,
                    "like_count": post.like_count,
                    "comment_count": post.comment_count,
                    "author": {
                        "name": post.author.full_name or post.author.username,
                        "avatar": post.author.avatar_url
                    },
                    "published_at": post.published_at.isoformat() if post.published_at else None
                })
            
            return {
                "success": True,
                "posts": post_list,
                "pagination": {
                    "total": total,
                    "offset": offset,
                    "limit": limit,
                    "has_more": offset + limit < total
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get public posts: {e}")
            return {"success": False, "message": str(e)}

    @staticmethod
    def get_post_by_slug(
        db: Session, 
        slug: str, 
        track_view: bool = True,
        visitor_ip: str = None,
        session_id: str = None
    ) -> Dict[str, Any]:
        """Get blog post by slug with view tracking"""
        try:
            post = db.query(BlogPost).filter(
                BlogPost.slug == slug,
                BlogPost.status == PostStatus.PUBLISHED,
                BlogPost.published_at <= datetime.utcnow()
            ).first()
            
            if not post:
                return {"success": False, "message": "Post not found"}
            
            # Track view
            if track_view:
                post.view_count += 1
                
                # Record detailed view
                view = BlogView(
                    post_id=post.id,
                    ip_address=visitor_ip,
                    session_id=session_id
                )
                db.add(view)
                db.commit()
            
            return {
                "success": True,
                "post": {
                    "id": post.id,
                    "title": post.title,
                    "slug": post.slug,
                    "excerpt": post.excerpt,
                    "content": post.content,
                    "featured_image": post.featured_image,
                    "featured_image_alt": post.featured_image_alt,
                    "gallery_images": post.gallery_images,
                    "category": {
                        "id": post.category.id,
                        "name": post.category.name,
                        "slug": post.category.slug,
                        "color": post.category.color
                    } if post.category else None,
                    "tags": post.tags.split(',') if post.tags else [],
                    "reading_time": post.reading_time,
                    "language": post.language,
                    "is_featured": post.is_featured,
                    "allow_comments": post.allow_comments,
                    "view_count": post.view_count,
                    "like_count": post.like_count,
                    "comment_count": post.comment_count,
                    "meta_title": post.meta_title,
                    "meta_description": post.meta_description,
                    "keywords": post.keywords,
                    "og_title": post.og_title,
                    "og_description": post.og_description,
                    "og_image": post.og_image,
                    "twitter_title": post.twitter_title,
                    "twitter_description": post.twitter_description,
                    "twitter_image": post.twitter_image,
                    "author": {
                        "name": post.author.full_name or post.author.username,
                        "avatar": post.author.avatar_url,
                        "bio": post.author.bio
                    },
                    "published_at": post.published_at.isoformat() if post.published_at else None,
                    "updated_at": post.updated_at.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get post by slug: {e}")
            return {"success": False, "message": str(e)}

    @staticmethod
    def get_admin_analytics(db: Session, days: int = 30) -> Dict[str, Any]:
        """Get blog analytics for admin dashboard"""
        try:
            from datetime import timedelta
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Basic stats
            total_posts = db.query(BlogPost).filter(
                BlogPost.status == PostStatus.PUBLISHED
            ).count()
            
            total_categories = db.query(BlogCategory).filter(
                BlogCategory.is_active == True
            ).count()
            
            total_views = db.query(func.sum(BlogPost.view_count)).scalar() or 0
            
            # Recent activity
            recent_posts = db.query(BlogPost).filter(
                BlogPost.created_at >= start_date
            ).count()
            
            recent_views = db.query(BlogView).filter(
                BlogView.created_at >= start_date
            ).count()
            
            # Most popular posts
            popular_posts = db.query(BlogPost).filter(
                BlogPost.status == PostStatus.PUBLISHED
            ).order_by(BlogPost.view_count.desc()).limit(10).all()
            
            # Top categories by post count
            top_categories = db.query(
                BlogCategory.name,
                func.count(BlogPost.id).label('post_count')
            ).join(BlogPost).filter(
                BlogPost.status == PostStatus.PUBLISHED
            ).group_by(BlogCategory.id).order_by(
                func.count(BlogPost.id).desc()
            ).limit(5).all()
            
            return {
                "success": True,
                "analytics": {
                    "overview": {
                        "total_posts": total_posts,
                        "total_categories": total_categories,
                        "total_views": total_views,
                        "recent_posts": recent_posts,
                        "recent_views": recent_views,
                        "period_days": days
                    },
                    "popular_posts": [
                        {
                            "id": post.id,
                            "title": post.title[:80] + "..." if len(post.title) > 80 else post.title,
                            "slug": post.slug,
                            "view_count": post.view_count,
                            "like_count": post.like_count,
                            "comment_count": post.comment_count,
                            "published_at": post.published_at.isoformat() if post.published_at else None
                        }
                        for post in popular_posts
                    ],
                    "top_categories": [
                        {
                            "name": name,
                            "post_count": post_count
                        }
                        for name, post_count in top_categories
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get blog analytics: {e}")
            return {"success": False, "message": str(e)}

    @staticmethod
    def publish_scheduled_posts(db: Session) -> int:
        """Publish scheduled posts (called by background task)"""
        try:
            now = datetime.utcnow()
            
            scheduled_posts = db.query(BlogPost).filter(
                BlogPost.status == PostStatus.SCHEDULED,
                BlogPost.scheduled_for <= now
            ).all()
            
            published_count = 0
            for post in scheduled_posts:
                post.status = PostStatus.PUBLISHED
                post.published_at = now
                published_count += 1
            
            db.commit()
            
            if published_count > 0:
                logger.info(f"Published {published_count} scheduled blog posts")
            
            return published_count
            
        except Exception as e:
            logger.error(f"Failed to publish scheduled posts: {e}")
            return 0

    @staticmethod
    def _generate_slug(text: str) -> str:
        """Generate URL-friendly slug from text"""
        import re
        
        # Convert to lowercase and replace spaces with hyphens
        slug = text.lower().strip()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)  # Remove special characters
        slug = re.sub(r'\s+', '-', slug)  # Replace spaces with hyphens
        slug = re.sub(r'-+', '-', slug)  # Remove multiple consecutive hyphens
        slug = slug.strip('-')  # Remove leading/trailing hyphens
        
        return slug[:200]  # Limit length

    @staticmethod
    def _calculate_reading_time(content: str) -> int:
        """Calculate estimated reading time in minutes"""
        import re
        
        # Remove HTML tags and count words
        clean_content = re.sub(r'<[^>]+>', '', content)
        word_count = len(clean_content.split())
        
        # Average reading speed: 200 words per minute
        reading_time = max(1, round(word_count / 200))
        
        return reading_time