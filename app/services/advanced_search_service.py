"""
Advanced Search Service
Full-text search, filtering, recommendations, and search analytics
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, JSON, func, desc, and_, or_
from sqlalchemy.orm import relationship
import re
from collections import Counter
import math

from database import Base
from app.models.template import Template
from app.models.document import Document
from app.models.user import User
from app.services.analytics.visit_tracking import VisitTrackingService


class SearchQuery(Base):
    """Search query tracking"""
    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)

    # Query details
    query_text = Column(Text, nullable=False, index=True)
    search_type = Column(String(50), nullable=False)  # template, document, global
    filters_applied = Column(JSON, nullable=True)

    # Results
    results_count = Column(Integer, nullable=False, default=0)
    clicked_result_ids = Column(JSON, nullable=True)  # Track which results were clicked

    # Performance
    response_time_ms = Column(Integer, nullable=True)

    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class SearchRecommendation(Base):
    """Search recommendations based on user behavior"""
    __tablename__ = "search_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)

    # Recommendation details
    recommendation_type = Column(String(50), nullable=False)  # similar_users, trending, personalized
    item_type = Column(String(20), nullable=False)  # template, document
    item_id = Column(Integer, nullable=False, index=True)

    # Scoring
    relevance_score = Column(Float, nullable=False, default=0.0)
    confidence_score = Column(Float, nullable=False, default=0.0)

    # Metadata
    reason = Column(Text, nullable=True)  # Why this was recommended
    recommendation_metadata = Column(JSON, nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    clicked = Column(Boolean, nullable=False, default=False)
    clicked_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)


class AdvancedSearchService:
    """Advanced search and recommendation service"""

    @staticmethod
    def search_templates(db: Session, query: str, user_id: Optional[int] = None,
                        category: str = None, min_price: float = None, max_price: float = None,
                        rating: float = None, language: str = None, tags: List[str] = None,
                        sort_by: str = "relevance", page: int = 1, per_page: int = 20) -> Dict:
        """Advanced template search with full-text search and ranking"""

        start_time = datetime.utcnow()

        # Base query
        base_query = db.query(Template).filter(
            Template.is_active == True,
            Template.is_public == True
        )

        # Text search with ranking
        if query:
            # Clean and prepare search terms
            search_terms = AdvancedSearchService._prepare_search_terms(query)

            # Build search conditions with weighted scoring
            search_conditions = []

            for term in search_terms:
                # Exact name match (highest weight)
                search_conditions.append(
                    Template.name.ilike(f"%{term}%")
                )

                # Description match (medium weight)
                search_conditions.append(
                    Template.description.ilike(f"%{term}%")
                )

                # Keywords match (medium weight)
                search_conditions.append(
                    Template.keywords.ilike(f"%{term}%")
                )

                # Tags match (lower weight)
                if Template.tags:
                    search_conditions.append(
                        Template.tags.contains(f'"{term}"')
                    )

            if search_conditions:
                base_query = base_query.filter(or_(*search_conditions))

        # Apply filters
        if category:
            base_query = base_query.filter(Template.category == category)

        if min_price is not None:
            base_query = base_query.filter(Template.price >= min_price)

        if max_price is not None:
            base_query = base_query.filter(Template.price <= max_price)

        if rating:
            base_query = base_query.filter(Template.rating >= rating)

        if language:
            base_query = base_query.filter(Template.language == language)

        if tags:
            for tag in tags:
                base_query = base_query.filter(Template.tags.contains(f'"{tag}"'))

        # Apply sorting
        base_query = AdvancedSearchService._apply_template_sorting(base_query, sort_by, query)

        # Get total count
        total = base_query.count()

        # Apply pagination
        templates = base_query.offset((page - 1) * per_page).limit(per_page).all()

        # Calculate response time
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Log search query
        if query:
            search_log = SearchQuery(
                user_id=user_id,
                query_text=query,
                search_type="template",
                filters_applied={
                    "category": category,
                    "min_price": min_price,
                    "max_price": max_price,
                    "rating": rating,
                    "language": language,
                    "tags": tags,
                    "sort_by": sort_by
                },
                results_count=total,
                response_time_ms=int(response_time)
            )
            db.add(search_log)
            db.commit()

        # Get user's purchased templates (if logged in)
        purchased_template_ids = set()
        if user_id:
            from app.models.template import Template
            purchases = db.query(TemplatePurchase.template_id).filter(
                TemplatePurchase.user_id == user_id,
                TemplatePurchase.is_active == True
            ).all()
            purchased_template_ids = {p[0] for p in purchases}

        return {
            "templates": [
                {
                    **AdvancedSearchService._format_template_result(t, query),
                    "is_purchased": t.id in purchased_template_ids
                }
                for t in templates
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
            "response_time_ms": int(response_time),
            "filters": {
                "query": query,
                "category": category,
                "min_price": min_price,
                "max_price": max_price,
                "rating": rating,
                "language": language,
                "tags": tags,
                "sort_by": sort_by
            },
            "suggestions": AdvancedSearchService._get_search_suggestions(db, query) if query else []
        }

    @staticmethod
    def search_documents(db: Session, user_id: int, query: str,
                        status: str = None, template_id: int = None,
                        start_date: datetime = None, end_date: datetime = None,
                        sort_by: str = "relevance", page: int = 1, per_page: int = 20) -> Dict:
        """Advanced document search for user's documents"""

        start_time = datetime.utcnow()

        # Base query - only user's documents
        base_query = db.query(Document).filter(Document.user_id == user_id)

        # Text search
        if query:
            search_terms = AdvancedSearchService._prepare_search_terms(query)
            search_conditions = []

            for term in search_terms:
                search_conditions.extend([
                    Document.title.ilike(f"%{term}%"),
                    Document.description.ilike(f"%{term}%"),
                    Document.content.ilike(f"%{term}%")
                ])

            if search_conditions:
                base_query = base_query.filter(or_(*search_conditions))

        # Apply filters
        if status:
            base_query = base_query.filter(Document.status == status)

        if template_id:
            base_query = base_query.filter(Document.template_id == template_id)

        if start_date:
            base_query = base_query.filter(Document.created_at >= start_date)

        if end_date:
            base_query = base_query.filter(Document.created_at <= end_date)

        # Apply sorting
        base_query = AdvancedSearchService._apply_document_sorting(base_query, sort_by, query)

        # Get total count
        total = base_query.count()

        # Apply pagination
        documents = base_query.offset((page - 1) * per_page).limit(per_page).all()

        # Calculate response time
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Log search query
        if query:
            search_log = SearchQuery(
                user_id=user_id,
                query_text=query,
                search_type="document",
                filters_applied={
                    "status": status,
                    "template_id": template_id,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "sort_by": sort_by
                },
                results_count=total,
                response_time_ms=int(response_time)
            )
            db.add(search_log)
            db.commit()

        return {
            "documents": [
                AdvancedSearchService._format_document_result(d, query)
                for d in documents
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
            "response_time_ms": int(response_time),
            "filters": {
                "query": query,
                "status": status,
                "template_id": template_id,
                "start_date": start_date,
                "end_date": end_date,
                "sort_by": sort_by
            }
        }

    @staticmethod
    def get_search_recommendations(db: Session, user_id: int, limit: int = 10) -> Dict:
        """Get personalized search recommendations"""

        # Get user's recent search patterns
        recent_searches = db.query(SearchQuery).filter(
            SearchQuery.user_id == user_id,
            SearchQuery.created_at >= datetime.utcnow() - timedelta(days=30)
        ).order_by(desc(SearchQuery.created_at)).limit(50).all()

        # Get user's template usage patterns
        user_templates = db.query(Document.template_id, func.count(Document.id).label('usage_count')).filter(
            Document.user_id == user_id,
            Document.template_id.isnot(None)
        ).group_by(Document.template_id).all()

        recommendations = []

        # 1. Trending templates in user's categories
        if user_templates:
            user_categories = db.query(Template.category).filter(
                Template.id.in_([t[0] for t in user_templates])
            ).distinct().all()

            trending_in_categories = db.query(Template).filter(
                Template.category.in_([cat[0] for cat in user_categories]),
                Template.is_active == True,
                Template.is_public == True,
                Template.rating >= 4.0
            ).order_by(desc(Template.usage_count)).limit(5).all()

            for template in trending_in_categories:
                recommendations.append({
                    "type": "template",
                    "item": AdvancedSearchService._format_template_result(template),
                    "reason": f"Trending in {template.category}",
                    "score": template.rating * template.usage_count / 100
                })

        # 2. Similar users' popular templates
        similar_templates = AdvancedSearchService._get_collaborative_recommendations(db, user_id, 3)
        recommendations.extend(similar_templates)

        # 3. New templates in user's interest areas
        if recent_searches:
            search_terms = []
            for search in recent_searches:
                search_terms.extend(AdvancedSearchService._prepare_search_terms(search.query_text))

            common_terms = [term for term, count in Counter(search_terms).most_common(5)]

            new_templates = db.query(Template).filter(
                Template.is_active == True,
                Template.is_public == True,
                Template.created_at >= datetime.utcnow() - timedelta(days=7)
            )

            for term in common_terms:
                new_templates = new_templates.filter(
                    or_(
                        Template.name.ilike(f"%{term}%"),
                        Template.description.ilike(f"%{term}%"),
                        Template.keywords.ilike(f"%{term}%")
                    )
                )

            new_templates = new_templates.order_by(desc(Template.created_at)).limit(2).all()

            for template in new_templates:
                recommendations.append({
                    "type": "template",
                    "item": AdvancedSearchService._format_template_result(template),
                    "reason": "New template matching your interests",
                    "score": 0.8
                })

        # Sort by score and limit results
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        recommendations = recommendations[:limit]

        return {
            "recommendations": recommendations,
            "total": len(recommendations),
            "generated_at": datetime.utcnow()
        }

    @staticmethod
    def get_search_analytics(db: Session, user_id: Optional[int] = None, days: int = 30) -> Dict:
        """Get search analytics"""

        start_date = datetime.utcnow() - timedelta(days=days)

        query = db.query(SearchQuery).filter(SearchQuery.created_at >= start_date)

        if user_id:
            query = query.filter(SearchQuery.user_id == user_id)

        searches = query.all()

        if not searches:
            return {
                "period_days": days,
                "total_searches": 0,
                "unique_queries": 0,
                "average_response_time": 0,
                "popular_terms": [],
                "search_trends": []
            }

        # Extract search terms
        all_terms = []
        for search in searches:
            all_terms.extend(AdvancedSearchService._prepare_search_terms(search.query_text))

        popular_terms = Counter(all_terms).most_common(10)

        # Daily search trends
        daily_searches = {}
        for search in searches:
            date = search.created_at.date()
            daily_searches[date] = daily_searches.get(date, 0) + 1

        search_trends = [
            {"date": str(date), "count": count}
            for date, count in sorted(daily_searches.items())
        ]

        # Calculate average response time
        response_times = [s.response_time_ms for s in searches if s.response_time_ms]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        return {
            "period_days": days,
            "total_searches": len(searches),
            "unique_queries": len(set(s.query_text.lower() for s in searches)),
            "average_response_time": round(avg_response_time, 2),
            "popular_terms": [{"term": term, "count": count} for term, count in popular_terms],
            "search_trends": search_trends,
            "search_types": dict(Counter(s.search_type for s in searches))
        }

    @staticmethod
    def _prepare_search_terms(query: str) -> List[str]:
        """Prepare search terms from query string"""
        if not query:
            return []

        # Remove special characters and split
        clean_query = re.sub(r'[^\w\s]', ' ', query.lower())
        terms = clean_query.split()

        # Remove common stop words
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'a', 'an'}
        terms = [term for term in terms if term not in stop_words and len(term) > 2]

        return terms

    @staticmethod
    def _apply_template_sorting(query, sort_by: str, search_query: str = None):
        """Apply sorting to template query"""
        if sort_by == "price_low":
            return query.order_by(Template.price)
        elif sort_by == "price_high":
            return query.order_by(desc(Template.price))
        elif sort_by == "rating":
            return query.order_by(desc(Template.rating), desc(Template.rating_count))
        elif sort_by == "popularity":
            return query.order_by(desc(Template.usage_count))
        elif sort_by == "newest":
            return query.order_by(desc(Template.created_at))
        elif sort_by == "name":
            return query.order_by(Template.name)
        else:  # relevance (default)
            if search_query:
                # Boost exact matches and higher rated templates
                return query.order_by(
                    desc(Template.rating * Template.usage_count / 100)
                )
            else:
                return query.order_by(desc(Template.rating), desc(Template.usage_count))

    @staticmethod
    def _apply_document_sorting(query, sort_by: str, search_query: str = None):
        """Apply sorting to document query"""
        if sort_by == "created_at":
            return query.order_by(desc(Document.created_at))
        elif sort_by == "updated_at":
            return query.order_by(desc(Document.updated_at))
        elif sort_by == "title":
            return query.order_by(Document.title)
        elif sort_by == "status":
            return query.order_by(Document.status)
        else:  # relevance (default)
            return query.order_by(desc(Document.updated_at))

    @staticmethod
    def _format_template_result(template: Template, query: str = None) -> Dict:
        """Format template for search results"""
        result = {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "type": template.type,
            "price": template.price,
            "is_premium": template.is_premium,
            "rating": template.rating,
            "rating_count": template.rating_count,
            "usage_count": template.usage_count,
            "tags": template.tags or [],
            "language": template.language,
            "created_at": template.created_at
        }

        # Add relevance highlighting if search query provided
        if query:
            result["highlights"] = AdvancedSearchService._generate_highlights(
                template, query
            )

        return result

    @staticmethod
    def _format_document_result(document: Document, query: str = None) -> Dict:
        """Format document for search results"""
        result = {
            "id": document.id,
            "title": document.title,
            "description": document.description,
            "status": document.status,
            "template_id": document.template_id,
            "created_at": document.created_at,
            "updated_at": document.updated_at
        }

        # Add relevance highlighting if search query provided
        if query:
            result["highlights"] = AdvancedSearchService._generate_document_highlights(
                document, query
            )

        return result

    @staticmethod
    def _generate_highlights(template: Template, query: str) -> Dict:
        """Generate search result highlights"""
        highlights = {}
        search_terms = AdvancedSearchService._prepare_search_terms(query)

        for term in search_terms:
            if template.name and term.lower() in template.name.lower():
                highlights["name"] = True
            if template.description and term.lower() in template.description.lower():
                highlights["description"] = True
            if template.keywords and term.lower() in template.keywords.lower():
                highlights["keywords"] = True

        return highlights

    @staticmethod
    def _generate_document_highlights(document: Document, query: str) -> Dict:
        """Generate document search result highlights"""
        highlights = {}
        search_terms = AdvancedSearchService._prepare_search_terms(query)

        for term in search_terms:
            if document.title and term.lower() in document.title.lower():
                highlights["title"] = True
            if document.description and term.lower() in document.description.lower():
                highlights["description"] = True
            if document.content and term.lower() in document.content.lower():
                highlights["content"] = True

        return highlights

    @staticmethod
    def _get_search_suggestions(db: Session, query: str) -> List[str]:
        """Get search suggestions based on query"""
        if not query or len(query) < 3:
            return []

        # Get popular searches that start with or contain the query
        similar_searches = db.query(SearchQuery.query_text, func.count(SearchQuery.id).label('count')).filter(
            SearchQuery.query_text.ilike(f"%{query}%"),
            SearchQuery.created_at >= datetime.utcnow() - timedelta(days=30)
        ).group_by(SearchQuery.query_text).order_by(desc('count')).limit(5).all()

        suggestions = [search[0] for search in similar_searches if search[0].lower() != query.lower()]

        # Add template name suggestions
        template_suggestions = db.query(Template.name).filter(
            Template.name.ilike(f"%{query}%"),
            Template.is_active == True,
            Template.is_public == True
        ).limit(3).all()

        suggestions.extend([t[0] for t in template_suggestions])

        return list(set(suggestions))[:5]  # Remove duplicates and limit

    @staticmethod
    def _get_collaborative_recommendations(db: Session, user_id: int, limit: int) -> List[Dict]:
        """Get recommendations based on similar users' behavior"""
        # This is a simplified collaborative filtering approach
        # In production, you'd want to use more sophisticated algorithms

        # Find users with similar template usage patterns
        user_templates = db.query(Document.template_id).filter(
            Document.user_id == user_id,
            Document.template_id.isnot(None)
        ).distinct().all()

        if not user_templates:
            return []

        user_template_ids = [t[0] for t in user_templates]

        # Find other users who used similar templates
        similar_users = db.query(
            Document.user_id,
            func.count(Document.template_id).label('common_templates')
        ).filter(
            Document.template_id.in_(user_template_ids),
            Document.user_id != user_id
        ).group_by(Document.user_id).having(
            func.count(Document.template_id) >= 2  # At least 2 common templates
        ).order_by(desc('common_templates')).limit(10).all()

        if not similar_users:
            return []

        similar_user_ids = [u[0] for u in similar_users]

        # Get templates used by similar users but not by current user
        recommended_templates = db.query(
            Document.template_id,
            func.count(Document.id).label('usage_count')
        ).join(Template, Document.template_id == Template.id).filter(
            Document.user_id.in_(similar_user_ids),
            Document.template_id.notin_(user_template_ids),
            Template.is_active == True,
            Template.is_public == True
        ).group_by(Document.template_id).order_by(
            desc('usage_count')
        ).limit(limit).all()

        recommendations = []
        for template_id, usage_count in recommended_templates:
            template = db.query(Template).filter(Template.id == template_id).first()
            if template:
                recommendations.append({
                    "type": "template",
                    "item": AdvancedSearchService._format_template_result(template),
                    "reason": "Popular among similar users",
                    "score": min(usage_count / 10.0, 1.0)  # Normalize score
                })

        return recommendations
