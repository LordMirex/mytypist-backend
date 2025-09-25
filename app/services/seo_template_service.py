"""
SEO Template Service
Create individual SEO-optimized pages for each template with social sharing
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from database import Base

logger = logging.getLogger(__name__)


class TemplateSEO(Base):
    """SEO configuration for templates"""
    __tablename__ = "template_seo"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey('templates.id'), nullable=False, unique=True, index=True)

    # SEO Meta data
    seo_title = Column(String(100), nullable=True)  # Custom SEO title
    meta_description = Column(String(160), nullable=True)  # Meta description
    keywords = Column(Text, nullable=True)  # Comma-separated keywords
    canonical_url = Column(String(500), nullable=True)

    # Social Media Meta (Open Graph, Twitter Cards)
    og_title = Column(String(100), nullable=True)
    og_description = Column(String(200), nullable=True)
    og_image = Column(String(500), nullable=True)  # Preview image URL
    og_type = Column(String(50), default="website")

    twitter_title = Column(String(100), nullable=True)
    twitter_description = Column(String(200), nullable=True)
    twitter_image = Column(String(500), nullable=True)
    twitter_card = Column(String(50), default="summary_large_image")

    # Template preview content
    preview_image_path = Column(String(500), nullable=True)  # Admin uploaded preview
    extraction_document_path = Column(String(500), nullable=True)  # Document for processing
    sample_content = Column(Text, nullable=True)  # Sample filled template for preview

    # Analytics and performance
    page_views = Column(Integer, default=0)
    unique_visitors = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)  # Views to document creations
    search_ranking_keywords = Column(Text, nullable=True)  # JSON of ranking keywords

    # Configuration
    is_indexed = Column(Boolean, default=True)  # Allow search engine indexing
    is_featured = Column(Boolean, default=False)  # Featured in search results
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SEOTemplateService:
    """Service for managing SEO-optimized template pages"""

    @staticmethod
    def create_or_update_template_seo(
        db: Session,
        template_id: int,
        seo_data: Dict[str, Any],
        admin_user_id: int
    ) -> Dict[str, Any]:
        """Create or update SEO configuration for a template"""
        try:
            # Check if SEO config already exists
            existing_seo = db.query(TemplateSEO).filter(
                TemplateSEO.template_id == template_id
            ).first()

            if existing_seo:
                # Update existing
                for key, value in seo_data.items():
                    if hasattr(existing_seo, key):
                        setattr(existing_seo, key, value)
                existing_seo.updated_at = datetime.utcnow()
                db.commit()
                seo_config = existing_seo
            else:
                # Create new
                seo_config = TemplateSEO(
                    template_id=template_id,
                    **seo_data
                )
                db.add(seo_config)
                db.commit()
                db.refresh(seo_config)

            logger.info(f"SEO configuration updated for template {template_id}")

            return {
                "success": True,
                "template_id": template_id,
                "seo_id": seo_config.id,
                "message": "SEO configuration updated successfully"
            }

        except Exception as e:
            logger.error(f"Failed to update template SEO: {e}")
            raise

    @staticmethod
    def get_template_seo_page(
        db: Session,
        template_id: int,
        track_view: bool = True,
        visitor_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get SEO-optimized template page data"""
        try:
            # Get template info
            from app.models.template import Template
            template = db.query(Template).filter(
                Template.id == template_id,
                Template.is_active == True
            ).first()

            if not template:
                return {"success": False, "error": "Template not found"}

            # Get SEO configuration
            seo_config = db.query(TemplateSEO).filter(
                TemplateSEO.template_id == template_id
            ).first()

            # Get usage statistics
            from app.models.document import Document
            usage_count = db.query(Document).filter(
                Document.template_id == template_id
            ).count()

            # Get average rating
            from app.models.template import TemplateReview
            avg_rating = db.query(
                db.func.avg(TemplateReview.rating)
            ).filter(TemplateReview.template_id == template_id).scalar() or 0

            # Track page view if requested
            if track_view and seo_config:
                seo_config.page_views += 1
                if visitor_ip:  # Simple unique visitor tracking
                    # In production, you'd use more sophisticated tracking
                    seo_config.unique_visitors += 1
                db.commit()

            # Build SEO page data
            page_data = {
                "success": True,
                "template": {
                    "id": template.id,
                    "name": template.name,
                    "description": template.description,
                    "category": template.category,
                    "price": template.price,
                    "currency": "NGN",
                    "is_free": template.price == 0,
                    "created_at": template.created_at.isoformat() if template.created_at else None
                },
                "seo": {
                    "title": seo_config.seo_title if seo_config else f"{template.name} - MyTypist Document Template",
                    "meta_description": seo_config.meta_description if seo_config else f"Create professional {template.name} documents instantly. {template.description}",
                    "keywords": seo_config.keywords if seo_config else f"{template.name}, document template, {template.category}, professional documents",
                    "canonical_url": seo_config.canonical_url if seo_config else f"/templates/{template_id}",
                    "is_indexed": seo_config.is_indexed if seo_config else True
                },
                "social": {
                    "og_title": seo_config.og_title if seo_config else f"{template.name} - Professional Document Template",
                    "og_description": seo_config.og_description if seo_config else f"Create {template.name} documents in seconds. Used by {usage_count} people.",
                    "og_image": seo_config.og_image if seo_config else "/assets/default-template-preview.jpg",
                    "og_type": seo_config.og_type if seo_config else "website",
                    "twitter_title": seo_config.twitter_title if seo_config else f"{template.name} Template",
                    "twitter_description": seo_config.twitter_description if seo_config else f"Professional {template.name} template. Quick and easy document creation.",
                    "twitter_image": seo_config.twitter_image if seo_config else seo_config.og_image if seo_config else "/assets/default-template-preview.jpg",
                    "twitter_card": seo_config.twitter_card if seo_config else "summary_large_image"
                },
                "preview": {
                    "image_url": seo_config.preview_image_path if seo_config else None,
                    "sample_content": seo_config.sample_content if seo_config else None
                },
                "statistics": {
                    "usage_count": usage_count,
                    "average_rating": round(float(avg_rating), 1),
                    "page_views": seo_config.page_views if seo_config else 0,
                    "is_popular": usage_count > 100,
                    "is_trending": usage_count > 50  # Last month logic would be more complex
                },
                "cta": {
                    "primary_text": "Create Document for Free" if template.price == 0 else f"Create Document - {template.price} Tokens",
                    "secondary_text": "Preview Template",
                    "create_url": f"/create/{template_id}",
                    "preview_url": f"/templates/{template_id}/preview"
                }
            }

            return page_data

        except Exception as e:
            logger.error(f"Failed to get template SEO page: {e}")
            raise

    @staticmethod
    def generate_template_sitemap(db: Session) -> Dict[str, Any]:
        """Generate sitemap data for all SEO template pages"""
        try:
            # Get all active templates with SEO config
            from app.models.template import Template
            templates = db.query(Template).filter(
                Template.is_active == True
            ).all()

            sitemap_urls = []

            for template in templates:
                seo_config = db.query(TemplateSEO).filter(
                    TemplateSEO.template_id == template.id
                ).first()

                # Only include if indexing is enabled
                if not seo_config or seo_config.is_indexed:
                    sitemap_urls.append({
                        "url": f"/templates/{template.id}",
                        "lastmod": (seo_config.updated_at if seo_config else template.updated_at or template.created_at).isoformat(),
                        "priority": "0.8" if (seo_config and seo_config.is_featured) else "0.6",
                        "changefreq": "weekly"
                    })

            return {
                "success": True,
                "sitemap_urls": sitemap_urls,
                "total_urls": len(sitemap_urls)
            }

        except Exception as e:
            logger.error(f"Failed to generate sitemap: {e}")
            raise

    @staticmethod
    def get_seo_analytics(
        db: Session,
        template_id: Optional[int] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get SEO performance analytics"""
        try:
            from datetime import timedelta
            start_date = datetime.utcnow() - timedelta(days=days)

            query = db.query(TemplateSEO)

            if template_id:
                query = query.filter(TemplateSEO.template_id == template_id)

            seo_configs = query.all()

            analytics_data = []
            total_views = 0
            total_unique_visitors = 0

            for seo_config in seo_configs:
                # Get template info
                from app.models.template import Template
                template = db.query(Template).filter(
                    Template.id == seo_config.template_id
                ).first()

                if template:
                    # Get document creations (conversions)
                    from app.models.document import Document
                    conversions = db.query(Document).filter(
                        Document.template_id == template.id,
                        Document.created_at >= start_date
                    ).count()

                    conversion_rate = (conversions / max(seo_config.page_views, 1)) * 100

                    analytics_data.append({
                        "template_id": template.id,
                        "template_name": template.name,
                        "page_views": seo_config.page_views,
                        "unique_visitors": seo_config.unique_visitors,
                        "conversions": conversions,
                        "conversion_rate": round(conversion_rate, 2),
                        "seo_title": seo_config.seo_title,
                        "is_featured": seo_config.is_featured,
                        "keywords": seo_config.keywords
                    })

                    total_views += seo_config.page_views
                    total_unique_visitors += seo_config.unique_visitors

            # Sort by performance
            analytics_data.sort(key=lambda x: x["page_views"], reverse=True)

            return {
                "success": True,
                "period_days": days,
                "summary": {
                    "total_templates": len(analytics_data),
                    "total_page_views": total_views,
                    "total_unique_visitors": total_unique_visitors,
                    "average_conversion_rate": round(sum(item["conversion_rate"] for item in analytics_data) / len(analytics_data), 2) if analytics_data else 0
                },
                "template_analytics": analytics_data
            }

        except Exception as e:
            logger.error(f"Failed to get SEO analytics: {e}")
            raise

    @staticmethod
    def update_search_keywords(
        db: Session,
        template_id: int,
        keywords: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update search ranking keywords for a template"""
        try:
            seo_config = db.query(TemplateSEO).filter(
                TemplateSEO.template_id == template_id
            ).first()

            if not seo_config:
                return {"success": False, "error": "SEO configuration not found"}

            # Store keyword ranking data
            seo_config.search_ranking_keywords = json.dumps(keywords)
            seo_config.updated_at = datetime.utcnow()
            db.commit()

            return {
                "success": True,
                "template_id": template_id,
                "keywords_updated": len(keywords),
                "message": "Search keywords updated successfully"
            }

        except Exception as e:
            logger.error(f"Failed to update search keywords: {e}")
            raise

    @staticmethod
    def get_template_structured_data(
        db: Session,
        template_id: int
    ) -> Dict[str, Any]:
        """Generate JSON-LD structured data for template page"""
        try:
            template_data = SEOTemplateService.get_template_seo_page(
                db=db,
                template_id=template_id,
                track_view=False
            )

            if not template_data["success"]:
                return {"success": False, "error": "Template not found"}

            template = template_data["template"]
            stats = template_data["statistics"]

            # Generate Product schema for the template
            structured_data = {
                "@context": "https://schema.org/",
                "@type": "Product",
                "name": template["name"],
                "description": template["description"],
                "category": template["category"],
                "image": template_data["social"]["og_image"],
                "url": f"https://mytypist.com/templates/{template_id}",
                "offers": {
                    "@type": "Offer",
                    "price": str(template["price"]) if template["price"] > 0 else "0",
                    "priceCurrency": "NGN",
                    "availability": "https://schema.org/InStock",
                    "priceValidUntil": "2025-12-31"
                },
                "aggregateRating": {
                    "@type": "AggregateRating",
                    "ratingValue": str(stats["average_rating"]),
                    "ratingCount": str(stats["usage_count"])
                } if stats["usage_count"] > 0 else None,
                "brand": {
                    "@type": "Brand",
                    "name": "MyTypist"
                },
                "manufacturer": {
                    "@type": "Organization",
                    "name": "MyTypist",
                    "url": "https://mytypist.com"
                }
            }

            # Remove null values
            structured_data = {k: v for k, v in structured_data.items() if v is not None}

            return {
                "success": True,
                "structured_data": structured_data
            }

        except Exception as e:
            logger.error(f"Failed to generate structured data: {e}")
            raise
