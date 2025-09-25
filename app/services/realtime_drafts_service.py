"""
Real-time Draft Management System
Implements auto-save every 3 seconds, background pre-processing, and 
instant document generation with intelligent form state management.
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from app.models.document import Document, DocumentStatus
from app.models.template import Template
from app.services.cache_service import cache_service
from config import settings
import redis

# Configure logging
drafts_logger = logging.getLogger('realtime_drafts')

@dataclass
class DraftState:
    """Real-time draft state management"""
    draft_id: str
    template_id: int
    user_id: int
    form_data: Dict[str, Any] = field(default_factory=dict)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    pre_processing_cache: Dict[str, Any] = field(default_factory=dict)
    last_modified: datetime = field(default_factory=datetime.utcnow)
    auto_save_enabled: bool = True
    is_dirty: bool = False
    processing_status: str = "draft"

@dataclass
class ValidationResult:
    """Field validation result"""
    field_name: str
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

class RealtimeDraftsManager:
    """
    Manages real-time draft states with auto-save, validation, and pre-processing
    """
    
    def __init__(self):
        self.active_drafts: Dict[str, DraftState] = {}
        self.auto_save_tasks: Dict[str, asyncio.Task] = {}
        self.validation_cache = {}
        self.processing_cache = {}
        
        # Redis for distributed draft storage
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                decode_responses=False,  # Keep binary for complex data
                socket_connect_timeout=2
            )
            self.redis_available = True
        except Exception:
            self.redis_available = False
        
        # Start cleanup task when event loop is available
        try:
            asyncio.create_task(self._cleanup_expired_drafts())
        except RuntimeError:
            # No event loop available during import, will start later
            pass
    
    async def create_draft(
        self,
        template_id: int,
        user_id: int,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new real-time draft
        """
        draft_id = str(uuid.uuid4())
        
        draft_state = DraftState(
            draft_id=draft_id,
            template_id=template_id,
            user_id=user_id,
            form_data=initial_data or {},
            last_modified=datetime.utcnow()
        )
        
        # Store in memory
        self.active_drafts[draft_id] = draft_state
        
        # Store in Redis for persistence
        if self.redis_available:
            await self._store_draft_in_redis(draft_state)
        
        # Start auto-save task
        self.auto_save_tasks[draft_id] = asyncio.create_task(
            self._auto_save_loop(draft_id)
        )
        
        drafts_logger.info(f"Created draft {draft_id} for template {template_id}")
        return draft_id
    
    async def update_draft_field(
        self,
        draft_id: str,
        field_name: str,
        field_value: Any,
        db: Session
    ) -> Dict[str, Any]:
        """
        Update a single field in the draft with real-time validation
        """
        if draft_id not in self.active_drafts:
            raise ValueError(f"Draft {draft_id} not found")
        
        draft = self.active_drafts[draft_id]
        old_value = draft.form_data.get(field_name)
        
        # Update field value
        draft.form_data[field_name] = field_value
        draft.last_modified = datetime.utcnow()
        draft.is_dirty = True
        
        # Real-time validation
        validation_result = await self._validate_field(
            field_name, field_value, draft.template_id, db
        )
        draft.validation_results[field_name] = validation_result
        
        # Background pre-processing if validation passes
        if validation_result.is_valid:
            await self._pre_process_field(draft_id, field_name, field_value)
        
        # Trigger auto-save if field is significant
        if self._is_significant_change(field_name, old_value, field_value):
            await self._schedule_immediate_save(draft_id)
        
        response = {
            'draft_id': draft_id,
            'field_updated': field_name,
            'validation': {
                'is_valid': validation_result.is_valid,
                'errors': validation_result.errors,
                'warnings': validation_result.warnings,
                'suggestions': validation_result.suggestions
            },
            'pre_processing_ready': field_name in draft.pre_processing_cache,
            'last_modified': draft.last_modified.isoformat()
        }
        
        drafts_logger.debug(f"Updated field {field_name} in draft {draft_id}")
        return response
    
    async def get_draft_state(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current draft state
        """
        if draft_id in self.active_drafts:
            draft = self.active_drafts[draft_id]
            return {
                'draft_id': draft.draft_id,
                'template_id': draft.template_id,
                'form_data': draft.form_data,
                'validation_results': {
                    field: {
                        'is_valid': result.is_valid,
                        'errors': result.errors,
                        'warnings': result.warnings,
                        'suggestions': result.suggestions
                    }
                    for field, result in draft.validation_results.items()
                },
                'last_modified': draft.last_modified.isoformat(),
                'processing_status': draft.processing_status,
                'pre_processing_complete': len(draft.pre_processing_cache),
                'is_ready_for_generation': self._is_ready_for_generation(draft)
            }
        
        # Try to load from Redis
        if self.redis_available:
            return await self._load_draft_from_redis(draft_id)
        
        return None
    
    async def prepare_for_instant_generation(
        self,
        draft_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Prepare draft for instant document generation
        """
        if draft_id not in self.active_drafts:
            raise ValueError(f"Draft {draft_id} not found")
        
        draft = self.active_drafts[draft_id]
        
        # Validate all fields
        validation_summary = await self._validate_all_fields(draft, db)
        
        if not validation_summary['all_valid']:
            return {
                'ready_for_generation': False,
                'validation_summary': validation_summary,
                'errors': validation_summary['errors']
            }
        
        # Complete pre-processing
        await self._complete_pre_processing(draft)
        
        # Calculate estimated generation time
        estimated_time = await self._estimate_generation_time(draft)
        
        return {
            'ready_for_generation': True,
            'estimated_generation_time_ms': estimated_time,
            'pre_processing_complete': len(draft.pre_processing_cache),
            'validation_summary': validation_summary
        }
    
    async def _auto_save_loop(self, draft_id: str):
        """
        Auto-save loop running every 3 seconds
        """
        while draft_id in self.active_drafts:
            try:
                await asyncio.sleep(3)  # 3-second interval
                
                if draft_id in self.active_drafts:
                    draft = self.active_drafts[draft_id]
                    
                    if draft.is_dirty and draft.auto_save_enabled:
                        await self._save_draft(draft_id)
                        drafts_logger.debug(f"Auto-saved draft {draft_id}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                drafts_logger.error(f"Auto-save error for draft {draft_id}: {e}")
        
        drafts_logger.info(f"Auto-save loop ended for draft {draft_id}")
    
    async def _save_draft(self, draft_id: str):
        """
        Save draft state
        """
        if draft_id not in self.active_drafts:
            return
        
        draft = self.active_drafts[draft_id]
        
        # Store in Redis
        if self.redis_available:
            await self._store_draft_in_redis(draft)
        
        # Mark as clean
        draft.is_dirty = False
        
        # Emit save event (for WebSocket notifications)
        await self._emit_draft_saved_event(draft_id)
    
    async def _validate_field(
        self,
        field_name: str,
        field_value: Any,
        template_id: int,
        db: Session
    ) -> ValidationResult:
        """
        Real-time field validation with caching
        """
        # Check cache first
        cache_key = f"validation_{template_id}_{field_name}_{str(field_value)[:50]}"
        
        if cache_key in self.validation_cache:
            return self.validation_cache[cache_key]
        
        # Perform validation
        result = ValidationResult(field_name=field_name, is_valid=True)
        
        # Get field validation rules from template
        template = db.query(Template).filter(Template.id == template_id).first()
        if template:
            validation_rules = self._get_field_validation_rules(field_name, template)
            result = await self._apply_validation_rules(field_value, validation_rules)
        
        # Cache result
        self.validation_cache[cache_key] = result
        
        return result
    
    def _get_field_validation_rules(self, field_name: str, template: Template) -> Dict[str, Any]:
        """
        Extract validation rules for field from template metadata
        """
        try:
            placeholders = json.loads(template.placeholders) if template.placeholders else []
            
            for placeholder in placeholders:
                if placeholder.get('name') == field_name:
                    return self._generate_validation_rules_for_placeholder(placeholder)
            
        except Exception:
            pass
        
        # Default rules based on field name
        return self._get_default_validation_rules(field_name)
    
    def _generate_validation_rules_for_placeholder(self, placeholder: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate validation rules based on placeholder metadata
        """
        field_name = placeholder.get('name', '').lower()
        
        rules = {'required': True}
        
        if 'email' in field_name:
            rules['pattern'] = r'^[^@]+@[^@]+\.[^@]+$'
            rules['type'] = 'email'
        elif 'phone' in field_name:
            rules['pattern'] = r'^\+?[1-9]\d{1,14}$'
            rules['type'] = 'phone'
        elif 'date' in field_name:
            rules['type'] = 'date'
            rules['format'] = 'YYYY-MM-DD'
        elif 'name' in field_name:
            rules['min_length'] = 2
            rules['max_length'] = 100
            rules['pattern'] = r'^[a-zA-Z\s\-\']+$'
        elif 'address' in field_name:
            rules['min_length'] = 10
            rules['max_length'] = 500
        elif 'signature' in field_name:
            rules['type'] = 'signature'
            rules['required'] = True
        
        return rules
    
    def _get_default_validation_rules(self, field_name: str) -> Dict[str, Any]:
        """
        Get default validation rules based on field name patterns
        """
        field_lower = field_name.lower()
        
        if 'email' in field_lower:
            return {'required': True, 'type': 'email', 'pattern': r'^[^@]+@[^@]+\.[^@]+$'}
        elif 'phone' in field_lower:
            return {'required': True, 'type': 'phone', 'pattern': r'^\+?[1-9]\d{1,14}$'}
        elif 'date' in field_lower:
            return {'required': True, 'type': 'date'}
        elif 'address' in field_lower:
            return {'required': True, 'min_length': 10, 'max_length': 500}
        else:
            return {'required': True, 'min_length': 1, 'max_length': 1000}
    
    async def _apply_validation_rules(
        self,
        value: Any,
        rules: Dict[str, Any]
    ) -> ValidationResult:
        """
        Apply validation rules to field value
        """
        result = ValidationResult(field_name='', is_valid=True)
        value_str = str(value).strip() if value else ''
        
        # Required check
        if rules.get('required', False) and not value_str:
            result.is_valid = False
            result.errors.append("This field is required")
            return result
        
        if not value_str:  # Skip other validations if empty and not required
            return result
        
        # Length checks
        min_length = rules.get('min_length')
        if min_length and len(value_str) < min_length:
            result.is_valid = False
            result.errors.append(f"Minimum length is {min_length} characters")
        
        max_length = rules.get('max_length')
        if max_length and len(value_str) > max_length:
            result.is_valid = False
            result.errors.append(f"Maximum length is {max_length} characters")
        
        # Pattern validation
        pattern = rules.get('pattern')
        if pattern:
            import re
            if not re.match(pattern, value_str):
                field_type = rules.get('type', 'text')
                result.is_valid = False
                result.errors.append(f"Please enter a valid {field_type}")
        
        # Type-specific validation
        field_type = rules.get('type')
        if field_type == 'date':
            try:
                from dateutil.parser import parse
                parse(value_str)
            except:
                result.is_valid = False
                result.errors.append("Please enter a valid date")
        
        # Add suggestions for improvement
        if result.is_valid:
            result.suggestions = self._generate_field_suggestions(value_str, rules)
        
        return result
    
    def _generate_field_suggestions(self, value: str, rules: Dict[str, Any]) -> List[str]:
        """
        Generate helpful suggestions for field improvement
        """
        suggestions = []
        field_type = rules.get('type')
        
        if field_type == 'name' and value.islower():
            suggestions.append("Consider using proper capitalization for names")
        elif field_type == 'email' and '@gmail.com' in value.lower():
            suggestions.append("Double-check Gmail address spelling")
        elif field_type == 'phone' and not value.startswith('+'):
            suggestions.append("Consider adding country code (e.g., +234)")
        
        return suggestions
    
    async def _pre_process_field(self, draft_id: str, field_name: str, field_value: Any):
        """
        Pre-process field value for faster document generation
        """
        draft = self.active_drafts[draft_id]
        
        # Format value based on field type
        processed_value = await self._format_field_value(field_name, field_value)
        
        # Store in pre-processing cache
        draft.pre_processing_cache[field_name] = {
            'original_value': field_value,
            'processed_value': processed_value,
            'processed_at': datetime.utcnow().isoformat()
        }
    
    async def _format_field_value(self, field_name: str, value: Any) -> Any:
        """
        Format field value according to its semantic type
        """
        if not value:
            return value
        
        value_str = str(value).strip()
        field_lower = field_name.lower()
        
        # Date formatting
        if 'date' in field_lower:
            try:
                from dateutil.parser import parse
                date_obj = parse(value_str)
                return date_obj.strftime("%B %d, %Y")  # "January 15, 2024"
            except:
                return value_str
        
        # Name formatting
        elif 'name' in field_lower:
            return value_str.title()
        
        # Address formatting
        elif 'address' in field_lower:
            return value_str  # Keep as-is for address
        
        # Email formatting
        elif 'email' in field_lower:
            return value_str.lower().strip()
        
        return value_str
    
    def _is_significant_change(self, field_name: str, old_value: Any, new_value: Any) -> bool:
        """
        Determine if field change is significant enough to trigger immediate save
        """
        # Always significant for certain field types
        significant_fields = ['signature', 'email', 'phone', 'date']
        
        if any(field_type in field_name.lower() for field_type in significant_fields):
            return old_value != new_value
        
        # Significant if length change is substantial
        old_len = len(str(old_value)) if old_value else 0
        new_len = len(str(new_value)) if new_value else 0
        
        return abs(old_len - new_len) > 5
    
    async def _schedule_immediate_save(self, draft_id: str):
        """
        Schedule immediate save for significant changes
        """
        if draft_id in self.active_drafts:
            # Cancel current auto-save task and save immediately
            if draft_id in self.auto_save_tasks:
                self.auto_save_tasks[draft_id].cancel()
            
            await self._save_draft(draft_id)
            
            # Restart auto-save task
            self.auto_save_tasks[draft_id] = asyncio.create_task(
                self._auto_save_loop(draft_id)
            )
    
    async def _validate_all_fields(self, draft: DraftState, db: Session) -> Dict[str, Any]:
        """
        Validate all fields in draft
        """
        all_valid = True
        field_errors = {}
        total_errors = 0
        
        for field_name, field_value in draft.form_data.items():
            validation_result = await self._validate_field(
                field_name, field_value, draft.template_id, db
            )
            
            if not validation_result.is_valid:
                all_valid = False
                field_errors[field_name] = validation_result.errors
                total_errors += len(validation_result.errors)
        
        return {
            'all_valid': all_valid,
            'total_errors': total_errors,
            'field_errors': field_errors,
            'validated_fields': len(draft.form_data)
        }
    
    async def _complete_pre_processing(self, draft: DraftState):
        """
        Complete all pre-processing for draft
        """
        for field_name, field_value in draft.form_data.items():
            if field_name not in draft.pre_processing_cache:
                await self._pre_process_field(draft.draft_id, field_name, field_value)
    
    def _is_ready_for_generation(self, draft: DraftState) -> bool:
        """
        Check if draft is ready for instant generation
        """
        # Must have form data
        if not draft.form_data:
            return False
        
        # Must pass validation
        for result in draft.validation_results.values():
            if not result.is_valid:
                return False
        
        # Should have pre-processing cache
        return len(draft.pre_processing_cache) > 0
    
    async def _estimate_generation_time(self, draft: DraftState) -> int:
        """
        Estimate document generation time in milliseconds
        """
        base_time = 200  # Base 200ms
        
        # Add time based on field complexity
        field_count = len(draft.form_data)
        field_time = field_count * 10  # 10ms per field
        
        # Add time for signature processing
        signature_fields = sum(1 for field in draft.form_data.keys() if 'signature' in field.lower())
        signature_time = signature_fields * 100  # 100ms per signature
        
        return base_time + field_time + signature_time
    
    async def _store_draft_in_redis(self, draft: DraftState):
        """
        Store draft state in Redis
        """
        try:
            draft_data = {
                'draft_id': draft.draft_id,
                'template_id': draft.template_id,
                'user_id': draft.user_id,
                'form_data': json.dumps(draft.form_data),
                'last_modified': draft.last_modified.isoformat(),
                'processing_status': draft.processing_status
            }
            
            redis_key = f"draft_{draft.draft_id}"
            self.redis_client.hset(redis_key, mapping=draft_data)
            self.redis_client.expire(redis_key, 86400)  # 24 hours
            
        except Exception as e:
            drafts_logger.error(f"Failed to store draft in Redis: {e}")
    
    async def _load_draft_from_redis(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """
        Load draft state from Redis
        """
        try:
            redis_key = f"draft_{draft_id}"
            draft_data = self.redis_client.hgetall(redis_key)
            
            if draft_data:
                return {
                    'draft_id': draft_data[b'draft_id'].decode(),
                    'template_id': int(draft_data[b'template_id']),
                    'user_id': int(draft_data[b'user_id']),
                    'form_data': json.loads(draft_data[b'form_data'].decode()),
                    'last_modified': draft_data[b'last_modified'].decode(),
                    'processing_status': draft_data[b'processing_status'].decode()
                }
        except Exception as e:
            drafts_logger.error(f"Failed to load draft from Redis: {e}")
        
        return None
    
    async def _emit_draft_saved_event(self, draft_id: str):
        """
        Emit draft saved event for WebSocket clients
        """
        # Implementation would depend on WebSocket setup
        drafts_logger.debug(f"Draft saved event emitted for {draft_id}")
    
    async def _cleanup_expired_drafts(self):
        """
        Cleanup expired drafts periodically
        """
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                current_time = datetime.utcnow()
                expired_drafts = []
                
                for draft_id, draft in self.active_drafts.items():
                    if current_time - draft.last_modified > timedelta(hours=24):
                        expired_drafts.append(draft_id)
                
                # Clean up expired drafts
                for draft_id in expired_drafts:
                    await self.cleanup_draft(draft_id)
                
                if expired_drafts:
                    drafts_logger.info(f"Cleaned up {len(expired_drafts)} expired drafts")
                
            except Exception as e:
                drafts_logger.error(f"Draft cleanup error: {e}")
    
    async def cleanup_draft(self, draft_id: str):
        """
        Clean up draft resources
        """
        # Cancel auto-save task
        if draft_id in self.auto_save_tasks:
            self.auto_save_tasks[draft_id].cancel()
            del self.auto_save_tasks[draft_id]
        
        # Remove from memory
        if draft_id in self.active_drafts:
            del self.active_drafts[draft_id]
        
        # Remove from Redis
        if self.redis_available:
            try:
                self.redis_client.delete(f"draft_{draft_id}")
            except Exception:
                pass
        
        drafts_logger.info(f"Draft {draft_id} cleaned up")

# Global drafts manager instance
realtime_drafts_manager = RealtimeDraftsManager()