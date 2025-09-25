# --- MISSING FUNCTION STUBS FOR ERROR TRACKING ---
def process_extraction_file(file, *args, **kwargs):
    """Stub for process_extraction_file. TODO: Implement actual logic."""
    raise NotImplementedError("process_extraction_file is not yet implemented.")

def process_preview_file(file, *args, **kwargs):
    """Stub for process_preview_file. TODO: Implement actual logic."""
    raise NotImplementedError("process_preview_file is not yet implemented.")
"""
Template management and processing service
"""

import os
import time
import uuid
import hashlib
import json
import re
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func
from fastapi import UploadFile, HTTPException, status
from docx import Document as DocxDocument
import redis

from config import settings
from app.models.template import Template, Placeholder
from app.models.template_management import TemplateCategory, TemplateReview
from app.models.template_purchase import TemplatePurchase
from app.models.template_favorite import TemplateFavorite
from app.models.user import User
from app.services.batch_process_service import BatchProcessService
from app.services.cache_service import CacheService
from app.services.admin_service import AdminService
from app.services.audit_service import AuditService
from app.services.wallet_service import WalletService
from app.services.token_management_service import TokenManagementService
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateSearch,
    TemplatePreview,
    TemplateUpload,
    TemplateRating,
    TemplateStats,
    PlaceholderCreate
)
from app.utils.storage import StorageService
from app.utils.security import validate_file_security
from app.utils.validation import validate_template_metadata
from app.utils.monitoring import (
    ACTIVE_TEMPLATE_OPERATIONS,
    TEMPLATE_LOAD_TIME,
    TEMPLATE_ERRORS
)
from database import get_db

logger = logging.getLogger(__name__)

def monitor_performance(operation_name: str):
    """Decorator for monitoring template operations performance"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            ACTIVE_TEMPLATE_OPERATIONS.inc()
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                TEMPLATE_LOAD_TIME.labels(
                    method=operation_name,
                    cache_status='hit' if result else 'miss'
                ).observe(time.time() - start_time)
                return result
            except Exception as e:
                TEMPLATE_ERRORS.labels(operation=operation_name).inc()
                raise
            finally:
                ACTIVE_TEMPLATE_OPERATIONS.dec()
        return wrapper
    return decorator

class TemplateLoader:
    """Service for optimized template loading using BatchProcessService"""

    def __init__(self, batch_service: Optional[BatchProcessService] = None):
        """Initialize loader with batch processing service"""
        self.batch_service = batch_service or BatchProcessService(CacheService())

    @monitor_performance('load_single')
    async def load_template(self, db: Session, template_id: int) -> Optional[Template]:
        """Load a template with caching and performance monitoring"""
        try:
            # Use batch service to load and cache single template
            results = await self.batch_service.preload_templates(db, [template_id])
            return Template(**results[template_id]) if template_id in results else None
        except Exception as e:
            logger.error(f"Error loading template {template_id}: {str(e)}")
            raise

    @monitor_performance('load_bulk')
    async def load_templates_bulk(self, db: Session, template_ids: List[int], batch_size: int = 50) -> List[Template]:
        """Load multiple templates efficiently using batch service"""
        try:
            # Use batch service to load and cache templates in batches
            templates = []

            # Process in batches to avoid overwhelming the system
            for i in range(0, len(template_ids), batch_size):
                batch = template_ids[i:i + batch_size]
                results = await self.batch_service.preload_templates(db, batch)

                for template_id in batch:
                    if template_id in results:
                        templates.append(Template(**results[template_id]))

            return templates
        except Exception as e:
            logger.error(f"Error loading templates in bulk: {str(e)}")
            raise

    @monitor_performance('search')
    async def search_templates(self, db: Session, query: str, filters: Dict[str, Any] = None) -> List[Template]:
        """Search templates with caching"""
        try:
            # Use batch service to handle template search
            results = await self.batch_service.search_templates(db, query, filters or {})
            return [Template(**data) for data in results]
        except Exception as e:
            logger.error(f"Error searching templates: {str(e)}")
            raise

    @monitor_performance('update')
    async def update_template(self, db: Session, template_id: int, updates: Dict[str, Any]) -> Optional[Template]:
        """Update template with proper cache invalidation"""
        try:
            # Update template using batch service
            result = await self.batch_service.update_template(db, template_id, updates)
            return Template(**result) if result else None
        except Exception as e:
            logger.error(f"Error updating template {template_id}: {str(e)}")
            raise
        for template_id in template_ids:
            if template_id in results:
                templates.append(Template(**results[template_id]))

        return templates

    @staticmethod
    async def preload_templates(db: Session, category: str = None) -> bool:
        """Preload frequently accessed templates into cache"""
        try:
            query = db.query(Template).filter(Template.is_active == True)
            if category:
                query = query.filter(Template.category == category)

            templates = query.order_by(desc(Template.usage_count)).limit(100).all()
            template_ids = [t.id for t in templates]

            # Use batch service for preloading
            batch_service = BatchProcessService(CacheService())
            await batch_service.preload_templates(db, template_ids)
            return True
        except Exception as e:
            logger.error(f"Template preload error: {e}")
            return False



class TemplateSimilarityService:
    """Service for template similarity and recommendations"""

    @staticmethod
    def find_similar_templates(db: Session, template_id: int, limit: int = 5) -> List[Template]:
        """Find similar templates based on classification and similarity scores"""
        template = db.query(Template).filter(Template.id == template_id).first()
        if not template or not template.similarity_score:
            return []

        # Get similar template IDs sorted by similarity score
        similar_ids = sorted(
            [(int(tid), score) for tid, score in template.similarity_score.items()],
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        # Fetch similar templates
        similar_templates = []
        for tid, _ in similar_ids:
            similar = db.query(Template).filter(Template.id == tid).first()
            if similar and similar.is_active:
                similar_templates.append(similar)

        return similar_templates

    @staticmethod
    def get_cluster_templates(db: Session, template_id: int, limit: int = 5) -> List[Template]:
        """Get templates from the same cluster"""
        template = db.query(Template).filter(Template.id == template_id).first()
        if not template or template.cluster_id is None:
            return []

        return db.query(Template).filter(
            Template.cluster_id == template.cluster_id,
            Template.id != template_id,
            Template.is_active == True
        ).limit(limit).all()

    @staticmethod
    def search_by_keywords(db: Session, keywords: List[str], limit: int = 10) -> List[Template]:
        """Search templates by keywords from their classification"""
        templates = db.query(Template).filter(Template.is_active == True).all()

        # Score templates based on keyword matches
        scored_templates = []
        for template in templates:
            if not template.keywords:
                continue

            score = 0
            template_keywords = [k[0].lower() for k in template.keywords]
            for keyword in keywords:
                if keyword.lower() in template_keywords:
                    score += 1

            if score > 0:
                scored_templates.append((template, score))

        # Return top matching templates
        return [t[0] for t in sorted(scored_templates, key=lambda x: x[1], reverse=True)[:limit]]

logger = logging.getLogger(__name__)


class TemplateService:
    """Template management and processing service"""

    ALLOWED_TEMPLATE_EXTENSIONS = ['.docx', '.pdf', '.txt']
    ALLOWED_PREVIEW_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.pdf']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    # Pricing operations
    PRICE_OPERATIONS = {
        'set': lambda old, new: new,
        'increase': lambda old, new: old + new,
        'decrease': lambda old, new: max(0, old - new),
        'percentage': lambda old, new: old * (1 + new/100)
    }

    @staticmethod
    async def create_template(
        db: Session,
        user_id: int,
        title: str,
        description: str,
        template_file: UploadFile,
        preview_file: UploadFile,
        categories: List[int],
        metadata: Dict[str, Any],
        is_public: bool = True
    ) -> Template:
        """Create a new template"""
        try:
            # Validate files
            await TemplateService._validate_template_files(template_file, preview_file)

            # Create template record
            template = Template(
                name=title,
                description=description,
                created_by=user_id,
                is_public=is_public,
                category=metadata.get('category', 'general'),
                type=metadata.get('type', 'document'),
                original_filename=template_file.filename,
                file_size=template_file.size or 0,
                file_hash=hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
            )

            db.add(template)
            db.flush()  # Get template ID

            # Store files
            template_path = await StorageService.store_template_file(
                template_file,
                os.path.join("templates", str(template.id), template_file.filename)
            )
            preview_path = await StorageService.store_preview_file(
                preview_file,
                os.path.join("previews", str(template.id), preview_file.filename)
            )

            # Update template with file paths
            template.preview_file_path = preview_path
            template.file_path = template_path

            db.commit()

            # Audit log
            await AuditService.log_action(
                db,
                user_id=user_id,
                action="template_created",
                resource_type="template",
                resource_id=template.id
            )

            return template

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create template: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create template: {str(e)}"
            )

    @staticmethod
    async def get_template_preview(
        db: Session,
        template_id: int,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get template preview details with analytics tracking"""
        template = db.query(Template).filter(Template.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Increment preview count
        template.preview_count = getattr(template, 'preview_count', 0) + 1

        # Update preview to download rate
        download_count = getattr(template, 'download_count', 0)
        if download_count > 0:
            template.preview_to_download_rate = download_count / template.preview_count

        db.commit()

        return {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "type": template.type,
            "preview_path": template.preview_file_path,
            "is_premium": getattr(template, 'is_premium', False),
            "token_cost": getattr(template, 'token_cost', 1),
            "rating": getattr(template, 'rating', 0.0),
            "rating_count": getattr(template, 'rating_count', 0),
            "download_count": download_count,
            "average_generation_time": getattr(template, 'average_generation_time', None)
        }

    @staticmethod
    async def update_template_metrics(
        db: Session,
        template_id: int,
        generation_time: Optional[float] = None,
        downloaded: bool = False
    ) -> None:
        """Update template metrics"""
        template = db.query(Template).filter(Template.id == template_id).first()
        if not template:
            return

        if generation_time:
            # Update average generation time
            current_avg = getattr(template, 'average_generation_time', None)
            if current_avg:
                template.average_generation_time = (current_avg + generation_time) / 2
            else:
                template.average_generation_time = generation_time

        if downloaded:
            template.download_count = getattr(template, 'download_count', 0) + 1
            preview_count = getattr(template, 'preview_count', 1)
            template.preview_to_download_rate = template.download_count / preview_count if preview_count > 0 else 0

        db.commit()

    @staticmethod
    async def toggle_favorite(db: Session, user_id: int, template_id: int) -> Dict[str, Any]:
        """Toggle template favorite status for user"""
        try:
            # Check if template exists
            template = db.query(Template).filter(Template.id == template_id).first()
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            # Check if favorite exists
            fav = db.query(TemplateFavorite).filter(
                TemplateFavorite.template_id == template_id,
                TemplateFavorite.user_id == user_id
            ).first()

            if fav:
                # Remove favorite
                db.delete(fav)
                is_favorite = False
            else:
                # Add favorite
                fav = TemplateFavorite(user_id=user_id, template_id=template_id)
                db.add(fav)
                is_favorite = True

            db.commit()
            return {"is_favorite": is_favorite}

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to toggle favorite: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to toggle favorite: {str(e)}"
            )

    @staticmethod
    async def get_user_favorites(db: Session, user_id: int, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get user's favorite templates"""
        try:
            favs = (
                db.query(TemplateFavorite)
                .filter(TemplateFavorite.user_id == user_id)
                .order_by(desc(TemplateFavorite.created_at))
                .offset((page-1)*per_page)
                .limit(per_page)
                .all()
            )

            template_ids = [fav.template_id for fav in favs]
            templates = db.query(Template).filter(Template.id.in_(template_ids)).all()

            return {
                "templates": templates,
                "total": len(favs),
                "page": page,
                "per_page": per_page
            }

        except Exception as e:
            logger.error(f"Failed to get user favorites: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get favorites: {str(e)}"
            )

    @staticmethod
    async def _validate_template_files(template_file: UploadFile, preview_file: UploadFile) -> None:
        """Validate template and preview files"""
        # Validate template file
        if not validate_file_security(template_file):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template file failed security validation"
            )

        # Validate preview file
        if not validate_file_security(preview_file):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Preview file failed security validation"
            )

    @staticmethod
    def _generate_slug(title: str) -> str:
        """Generate URL-friendly slug from title"""
        return re.sub(r'[^a-zA-Z0-9-]', '-', title.lower()).strip('-')

    @staticmethod
    async def _can_edit_template(db: Session, user_id: int, template: Template) -> bool:
        """Check if user can edit template"""
        # Template creator can edit
        if template.created_by == user_id:
            return True

        # Admin users can edit (basic check)
        user = db.query(User).filter(User.id == user_id).first()
        if user and hasattr(user, 'role') and user.role == 'admin':
            return True

        return False
