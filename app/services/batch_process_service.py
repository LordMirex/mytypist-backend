"""
Batch Processing Service for Template Operations
"""

import asyncio
import logging
from typing import List, Dict, Any, Callable, Awaitable, TypeVar, Optional
from sqlalchemy.orm import Session
from app.models.template import Template
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

T = TypeVar('T')

class BatchProcessService:
    """Service for efficient batch processing of templates and related operations"""

    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.batch_size = 100  # Default batch size
        self.max_concurrent = 5  # Maximum concurrent tasks

    async def process_templates_batch(
        self,
        db: Session,
        template_ids: List[int],
        operation: Callable[[Session, Template], Awaitable[T]],
        batch_size: Optional[int] = None
    ) -> Dict[int, T]:
        """
        Process a batch of templates with the given operation
        
        Args:
            db: Database session
            template_ids: List of template IDs to process
            operation: Async function that processes a single template
            batch_size: Optional custom batch size
        
        Returns:
            Dictionary mapping template IDs to operation results
        """
        results = {}
        current_batch = []
        batch_size = batch_size or self.batch_size

        try:
            # Process in batches
            for template_id in template_ids:
                current_batch.append(template_id)
                
                if len(current_batch) >= batch_size:
                    batch_results = await self._process_batch(db, current_batch, operation)
                    results.update(batch_results)
                    current_batch = []

            # Process remaining templates
            if current_batch:
                batch_results = await self._process_batch(db, current_batch, operation)
                results.update(batch_results)

            return results

        except Exception as e:
            logger.error(f"Batch processing failed: {str(e)}")
            raise

    async def _process_batch(
        self,
        db: Session,
        template_ids: List[int],
        operation: Callable[[Session, Template], Awaitable[T]]
    ) -> Dict[int, T]:
        """Process a single batch of templates"""
        templates = (
            db.query(Template)
            .filter(Template.id.in_(template_ids))
            .all()
        )
        
        tasks = []
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_with_semaphore(template: Template) -> tuple[int, T]:
            async with semaphore:
                try:
                    result = await operation(db, template)
                    return template.id, result
                except Exception as e:
                    logger.error(f"Failed to process template {template.id}: {str(e)}")
                    raise

        # Create tasks for concurrent processing
        for template in templates:
            task = asyncio.create_task(process_with_semaphore(template))
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out failed operations and return successful results
        return {
            template_id: result
            for template_id, result in results
            if not isinstance(result, Exception)
        }

    async def bulk_cache_templates(
        self,
        db: Session,
        template_ids: List[int]
    ) -> Dict[int, bool]:
        """
        Bulk cache templates for better performance
        
        Args:
            db: Database session
            template_ids: List of template IDs to cache
        
        Returns:
            Dictionary mapping template IDs to cache success status
        """
        async def cache_template(db: Session, template: Template) -> bool:
            try:
                # Cache template data
                cache_key = f"template:{template.id}"
                await self.cache_service.set(cache_key, template.to_dict())
                return True
            except Exception as e:
                logger.error(f"Failed to cache template {template.id}: {str(e)}")
                return False

        return await self.process_templates_batch(db, template_ids, cache_template)

    async def bulk_update_templates(
        self,
        db: Session,
        template_ids: List[int],
        updates: Dict[str, Any]
    ) -> Dict[int, bool]:
        """
        Bulk update templates with the given field values
        
        Args:
            db: Database session
            template_ids: List of template IDs to update
            updates: Dictionary of field names and values to update
        
        Returns:
            Dictionary mapping template IDs to update success status
        """
        async def update_template(db: Session, template: Template) -> bool:
            try:
                for field, value in updates.items():
                    setattr(template, field, value)
                return True
            except Exception as e:
                logger.error(f"Failed to update template {template.id}: {str(e)}")
                return False

        results = await self.process_templates_batch(db, template_ids, update_template)
        
        # Commit changes
        try:
            db.commit()
        except Exception as e:
            logger.error(f"Failed to commit template updates: {str(e)}")
            db.rollback()
            return {template_id: False for template_id in template_ids}

        return results

    async def bulk_process_search_results(
        self,
        db: Session,
        template_ids: List[int],
        processor: Callable[[Template], Awaitable[T]]
    ) -> Dict[int, T]:
        """
        Process search results in batches
        
        Args:
            db: Database session
            template_ids: List of template IDs from search results
            processor: Async function to process each template
        
        Returns:
            Dictionary mapping template IDs to processor results
        """
        async def process_template(db: Session, template: Template) -> T:
            return await processor(template)

        return await self.process_templates_batch(db, template_ids, process_template)

    async def preload_templates(
        self,
        db: Session,
        template_ids: List[int]
    ) -> Dict[int, Dict[str, Any]]:
        """
        Preload templates and their related data for efficient access
        
        Args:
            db: Database session
            template_ids: List of template IDs to preload
        
        Returns:
            Dictionary mapping template IDs to template data
        """
        async def load_template_data(db: Session, template: Template) -> Dict[str, Any]:
            # Load related data
            template_data = template.to_dict()
            template_data['category'] = template.category.to_dict() if template.category else None
            template_data['user'] = template.user.to_dict() if template.user else None
            template_data['stats'] = {
                'usage_count': len(template.documents),
                'average_rating': sum(d.rating for d in template.documents if d.rating) / 
                                len([d for d in template.documents if d.rating]) if template.documents else 0
            }
            
            # Cache the loaded data
            cache_key = f"template_full:{template.id}"
            await self.cache_service.set(cache_key, template_data)
            
            return template_data

        return await self.process_templates_batch(db, template_ids, load_template_data)