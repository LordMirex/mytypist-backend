"""
Dynamic FAQ Management System
Content management for frequently asked questions with search and analytics
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship

from database import Base

logger = logging.getLogger(__name__)


class FAQCategory(Base):
    """FAQ categories for organization"""
    __tablename__ = "faq_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    slug = Column(String(150), nullable=False, unique=True, index=True)
    icon = Column(String(50), nullable=True)  # Icon class or name
    sort_order = Column(Integer, default=0, index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # SEO
    meta_title = Column(String(100), nullable=True)
    meta_description = Column(String(160), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    faqs = relationship("FAQ", back_populates="category", cascade="all, delete-orphan")


class FAQ(Base):
    """Frequently Asked Questions with analytics"""
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey('faq_categories.id'), nullable=False, index=True)
    
    # Content
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    short_answer = Column(String(500), nullable=True)  # For quick previews
    
    # Organization
    slug = Column(String(200), nullable=False, unique=True, index=True)
    tags = Column(Text, nullable=True)  # Comma-separated tags for search
    sort_order = Column(Integer, default=0, index=True)
    is_featured = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # SEO and social
    meta_title = Column(String(100), nullable=True)
    meta_description = Column(String(160), nullable=True)
    keywords = Column(String(500), nullable=True)
    
    # Analytics
    view_count = Column(Integer, default=0)
    helpful_count = Column(Integer, default=0)  # "Was this helpful?" yes votes
    unhelpful_count = Column(Integer, default=0)  # "Was this helpful?" no votes
    
    # Content management
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    updated_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_reviewed = Column(DateTime, nullable=True)
    review_required = Column(Boolean, default=False)
    
    # Relationships
    category = relationship("FAQCategory", back_populates="faqs")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])


class FAQInteraction(Base):
    """Track user interactions with FAQs"""
    __tablename__ = "faq_interactions"

    id = Column(Integer, primary_key=True, index=True)
    faq_id = Column(Integer, ForeignKey('faqs.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)  # Nullable for anonymous
    session_id = Column(String(100), nullable=True, index=True)
    
    # Interaction details
    interaction_type = Column(String(20), nullable=False, index=True)  # view, helpful, unhelpful, search
    search_query = Column(String(500), nullable=True)  # If found via search
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    faq = relationship("FAQ")
    user = relationship("User")


class FAQService:
    """Service for managing dynamic FAQ system"""

    @staticmethod
    def create_category(
        db: Session,
        admin_user_id: int,
        category_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new FAQ category"""
        try:
            # Generate slug from name if not provided
            slug = category_data.get('slug') or FAQService._generate_slug(category_data['name'])
            
            # Check if slug already exists
            existing = db.query(FAQCategory).filter(FAQCategory.slug == slug).first()
            if existing:
                return {"success": False, "message": "Category slug already exists"}
            
            category = FAQCategory(
                name=category_data['name'],
                description=category_data.get('description'),
                slug=slug,
                icon=category_data.get('icon'),
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
            logger.error(f"Failed to create FAQ category: {e}")
            db.rollback()
            return {"success": False, "message": str(e)}

    @staticmethod
    def create_faq(
        db: Session,
        admin_user_id: int,
        faq_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new FAQ"""
        try:
            # Generate slug from question if not provided
            slug = faq_data.get('slug') or FAQService._generate_slug(faq_data['question'])
            
            # Check if slug already exists
            existing = db.query(FAQ).filter(FAQ.slug == slug).first()
            if existing:
                counter = 1
                while existing:
                    new_slug = f"{slug}-{counter}"
                    existing = db.query(FAQ).filter(FAQ.slug == new_slug).first()
                    if not existing:
                        slug = new_slug
                        break
                    counter += 1
            
            faq = FAQ(
                category_id=faq_data['category_id'],
                question=faq_data['question'],
                answer=faq_data['answer'],
                short_answer=faq_data.get('short_answer'),
                slug=slug,
                tags=faq_data.get('tags'),
                sort_order=faq_data.get('sort_order', 0),
                is_featured=faq_data.get('is_featured', False),
                meta_title=faq_data.get('meta_title'),
                meta_description=faq_data.get('meta_description'),
                keywords=faq_data.get('keywords'),
                created_by=admin_user_id
            )
            
            db.add(faq)
            db.commit()
            db.refresh(faq)
            
            return {
                "success": True,
                "faq_id": faq.id,
                "slug": faq.slug,
                "message": "FAQ created successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to create FAQ: {e}")
            db.rollback()
            return {"success": False, "message": str(e)}

    @staticmethod
    def get_public_faqs(
        db: Session,
        category_slug: str = None,
        search_query: str = None,
        featured_only: bool = False,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get FAQs for public display"""
        try:
            query = db.query(FAQ).filter(FAQ.is_active == True)
            
            # Filter by category
            if category_slug:
                category = db.query(FAQCategory).filter(
                    FAQCategory.slug == category_slug,
                    FAQCategory.is_active == True
                ).first()
                if category:
                    query = query.filter(FAQ.category_id == category.id)
                else:
                    return {"success": False, "message": "Category not found"}
            
            # Search functionality
            if search_query:
                search_term = f"%{search_query}%"
                query = query.filter(
                    FAQ.question.ilike(search_term) |
                    FAQ.answer.ilike(search_term) |
                    FAQ.tags.ilike(search_term) |
                    FAQ.keywords.ilike(search_term)
                )
            
            # Featured filter
            if featured_only:
                query = query.filter(FAQ.is_featured == True)
            
            # Order by sort_order and view_count
            query = query.order_by(FAQ.sort_order, FAQ.view_count.desc())
            
            # Apply limit
            faqs = query.limit(limit).all()
            
            # Get categories for navigation
            categories = db.query(FAQCategory).filter(
                FAQCategory.is_active == True
            ).order_by(FAQCategory.sort_order).all()
            
            # Format response
            faq_list = []
            for faq in faqs:
                faq_list.append({
                    "id": faq.id,
                    "question": faq.question,
                    "answer": faq.answer,
                    "short_answer": faq.short_answer,
                    "slug": faq.slug,
                    "category": {
                        "id": faq.category.id,
                        "name": faq.category.name,
                        "slug": faq.category.slug
                    },
                    "tags": faq.tags.split(',') if faq.tags else [],
                    "is_featured": faq.is_featured,
                    "view_count": faq.view_count,
                    "helpful_count": faq.helpful_count,
                    "unhelpful_count": faq.unhelpful_count,
                    "updated_at": faq.updated_at.isoformat()
                })
            
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
                    "faq_count": faq_count
                })
            
            return {
                "success": True,
                "faqs": faq_list,
                "categories": category_list,
                "total_faqs": len(faq_list)
            }
            
        except Exception as e:
            logger.error(f"Failed to get public FAQs: {e}")
            return {"success": False, "message": str(e)}

    @staticmethod
    def get_faq_by_slug(db: Session, slug: str, track_view: bool = True, user_id: int = None, session_id: str = None) -> Dict[str, Any]:
        """Get specific FAQ by slug with view tracking"""
        try:
            faq = db.query(FAQ).filter(
                FAQ.slug == slug,
                FAQ.is_active == True
            ).first()
            
            if not faq:
                return {"success": False, "message": "FAQ not found"}
            
            # Track view
            if track_view:
                faq.view_count += 1
                
                # Record interaction
                interaction = FAQInteraction(
                    faq_id=faq.id,
                    user_id=user_id,
                    session_id=session_id,
                    interaction_type="view"
                )
                db.add(interaction)
                db.commit()
            
            return {
                "success": True,
                "faq": {
                    "id": faq.id,
                    "question": faq.question,
                    "answer": faq.answer,
                    "slug": faq.slug,
                    "category": {
                        "id": faq.category.id,
                        "name": faq.category.name,
                        "slug": faq.category.slug,
                        "description": faq.category.description
                    },
                    "tags": faq.tags.split(',') if faq.tags else [],
                    "is_featured": faq.is_featured,
                    "view_count": faq.view_count,
                    "helpful_count": faq.helpful_count,
                    "unhelpful_count": faq.unhelpful_count,
                    "meta_title": faq.meta_title,
                    "meta_description": faq.meta_description,
                    "keywords": faq.keywords,
                    "updated_at": faq.updated_at.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get FAQ by slug: {e}")
            return {"success": False, "message": str(e)}

    @staticmethod
    def record_feedback(
        db: Session,
        faq_id: int,
        is_helpful: bool,
        user_id: int = None,
        session_id: str = None
    ) -> Dict[str, Any]:
        """Record user feedback on FAQ helpfulness"""
        try:
            faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
            if not faq:
                return {"success": False, "message": "FAQ not found"}
            
            # Update counters
            if is_helpful:
                faq.helpful_count += 1
            else:
                faq.unhelpful_count += 1
            
            # Record interaction
            interaction = FAQInteraction(
                faq_id=faq_id,
                user_id=user_id,
                session_id=session_id,
                interaction_type="helpful" if is_helpful else "unhelpful"
            )
            db.add(interaction)
            db.commit()
            
            return {
                "success": True,
                "message": "Feedback recorded successfully",
                "helpful_count": faq.helpful_count,
                "unhelpful_count": faq.unhelpful_count
            }
            
        except Exception as e:
            logger.error(f"Failed to record FAQ feedback: {e}")
            db.rollback()
            return {"success": False, "message": str(e)}

    @staticmethod
    def search_faqs(
        db: Session,
        query: str,
        limit: int = 20,
        user_id: int = None,
        session_id: str = None
    ) -> Dict[str, Any]:
        """Search FAQs with relevance scoring"""
        try:
            if not query or len(query.strip()) < 2:
                return {"success": False, "message": "Search query too short"}
            
            search_term = f"%{query.strip()}%"
            
            # Search with different weights for relevance
            faqs = db.query(FAQ).filter(
                FAQ.is_active == True,
                (FAQ.question.ilike(search_term) |
                 FAQ.answer.ilike(search_term) |
                 FAQ.tags.ilike(search_term) |
                 FAQ.keywords.ilike(search_term))
            ).order_by(
                # Prioritize question matches, then featured, then view count
                func.case(
                    (FAQ.question.ilike(search_term), 1),
                    else_=2
                ),
                FAQ.is_featured.desc(),
                FAQ.view_count.desc()
            ).limit(limit).all()
            
            # Record search interaction
            if faqs:
                for faq in faqs[:3]:  # Record for top 3 results
                    interaction = FAQInteraction(
                        faq_id=faq.id,
                        user_id=user_id,
                        session_id=session_id,
                        interaction_type="search",
                        search_query=query.strip()
                    )
                    db.add(interaction)
            
            db.commit()
            
            # Format results
            results = []
            for faq in faqs:
                # Calculate relevance score
                relevance_score = 0
                if query.lower() in faq.question.lower():
                    relevance_score += 50
                if query.lower() in faq.answer.lower():
                    relevance_score += 30
                if faq.tags and query.lower() in faq.tags.lower():
                    relevance_score += 20
                if faq.is_featured:
                    relevance_score += 10
                
                results.append({
                    "id": faq.id,
                    "question": faq.question,
                    "short_answer": faq.short_answer or faq.answer[:200] + "...",
                    "slug": faq.slug,
                    "category": {
                        "name": faq.category.name,
                        "slug": faq.category.slug
                    },
                    "relevance_score": relevance_score,
                    "view_count": faq.view_count,
                    "is_featured": faq.is_featured
                })
            
            # Sort by relevance score
            results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            return {
                "success": True,
                "query": query.strip(),
                "results": results,
                "total_results": len(results)
            }
            
        except Exception as e:
            logger.error(f"Failed to search FAQs: {e}")
            return {"success": False, "message": str(e)}

    @staticmethod
    def get_admin_analytics(db: Session, days: int = 30) -> Dict[str, Any]:
        """Get FAQ analytics for admin dashboard"""
        try:
            from datetime import timedelta
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Basic stats
            total_faqs = db.query(FAQ).filter(FAQ.is_active == True).count()
            total_categories = db.query(FAQCategory).filter(FAQCategory.is_active == True).count()
            
            # Recent interactions
            recent_interactions = db.query(FAQInteraction).filter(
                FAQInteraction.created_at >= start_date
            ).count()
            
            # Most viewed FAQs
            most_viewed = db.query(FAQ).filter(
                FAQ.is_active == True
            ).order_by(FAQ.view_count.desc()).limit(10).all()
            
            # Most searched queries
            search_queries = db.query(
                FAQInteraction.search_query,
                func.count(FAQInteraction.id).label('count')
            ).filter(
                FAQInteraction.interaction_type == 'search',
                FAQInteraction.search_query.isnot(None),
                FAQInteraction.created_at >= start_date
            ).group_by(FAQInteraction.search_query).order_by(
                func.count(FAQInteraction.id).desc()
            ).limit(10).all()
            
            # FAQs needing review (low helpfulness ratio)
            needs_review = db.query(FAQ).filter(
                FAQ.is_active == True,
                FAQ.helpful_count + FAQ.unhelpful_count > 10,
                FAQ.helpful_count < FAQ.unhelpful_count
            ).order_by(FAQ.unhelpful_count.desc()).limit(10).all()
            
            return {
                "success": True,
                "analytics": {
                    "overview": {
                        "total_faqs": total_faqs,
                        "total_categories": total_categories,
                        "recent_interactions": recent_interactions,
                        "period_days": days
                    },
                    "most_viewed_faqs": [
                        {
                            "id": faq.id,
                            "question": faq.question[:100] + "...",
                            "view_count": faq.view_count,
                            "helpful_count": faq.helpful_count,
                            "unhelpful_count": faq.unhelpful_count,
                            "slug": faq.slug
                        }
                        for faq in most_viewed
                    ],
                    "popular_searches": [
                        {
                            "query": query,
                            "count": count
                        }
                        for query, count in search_queries
                    ],
                    "needs_review": [
                        {
                            "id": faq.id,
                            "question": faq.question[:100] + "...",
                            "helpful_count": faq.helpful_count,
                            "unhelpful_count": faq.unhelpful_count,
                            "helpfulness_ratio": round(faq.helpful_count / (faq.helpful_count + faq.unhelpful_count) * 100, 1),
                            "slug": faq.slug
                        }
                        for faq in needs_review
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get FAQ analytics: {e}")
            return {"success": False, "message": str(e)}

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
        
        return slug[:150]  # Limit length