"""Performance tracking and analytics service"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.document import Document
from app.models.template import Template
from app.models.user import User


class PerformanceService:
    """Service for tracking and calculating performance metrics"""
    
    @staticmethod
    def calculate_time_saved(
        template: Template,
        document_count: int
    ) -> float:
        """Calculate time saved based on template metrics and usage"""
        if not template.avg_manual_time:
            return 0.0
            
        # Get the difference between manual and automated time
        time_per_doc = template.avg_manual_time - template.avg_generation_time
        
        # Calculate total time saved
        return max(0, time_per_doc * document_count)

    @staticmethod
    def get_user_time_savings(
        db: Session,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get time savings statistics for a user"""
        
        # Build date filter
        date_filter = []
        if start_date:
            date_filter.append(Document.created_at >= start_date)
        if end_date:
            date_filter.append(Document.created_at <= end_date)
            
        # Get document counts by template
        template_usage = db.query(
            Document.template_id,
            func.count(Document.id).label('doc_count')
        ).filter(
            Document.user_id == user_id,
            Document.status == 'completed',
            *date_filter
        ).group_by(Document.template_id).all()
        
        total_time_saved = 0.0
        savings_by_template = []
        
        for template_id, doc_count in template_usage:
            template = db.query(Template).get(template_id)
            if template:
                time_saved = PerformanceService.calculate_time_saved(
                    template, doc_count
                )
                total_time_saved += time_saved
                
                savings_by_template.append({
                    'template_id': template_id,
                    'template_name': template.name,
                    'documents_generated': doc_count,
                    'time_saved_minutes': round(time_saved / 60, 2),
                    'efficiency_gain': round(
                        (template.avg_manual_time - template.avg_generation_time) 
                        / template.avg_manual_time * 100 
                        if template.avg_manual_time > 0 else 0,
                        2
                    )
                })
        
        return {
            'total_time_saved_minutes': round(total_time_saved / 60, 2),
            'documents_generated': sum(x['documents_generated'] for x in savings_by_template),
            'templates_used': len(savings_by_template),
            'savings_by_template': sorted(
                savings_by_template,
                key=lambda x: x['time_saved_minutes'],
                reverse=True
            )
        }

    @staticmethod
    def get_batch_analytics(
        db: Session,
        batch_id: str
    ) -> Dict[str, Any]:
        """Get analytics for a batch processing job"""
        
        # Get all documents in batch
        documents = db.query(Document).filter(
            Document.batch_id == batch_id
        ).all()
        
        if not documents:
            return {}
            
        # Calculate metrics
        total_docs = len(documents)
        completed_docs = sum(1 for d in documents if d.status == 'completed')
        failed_docs = sum(1 for d in documents if d.status == 'failed')
        
        # Get generation times
        generation_times = [
            (d.completed_at - d.processing_started_at).total_seconds()
            for d in documents
            if d.status == 'completed' 
            and d.completed_at 
            and d.processing_started_at
        ]
        
        avg_generation_time = (
            sum(generation_times) / len(generation_times)
            if generation_times else 0
        )
        
        return {
            'batch_id': batch_id,
            'total_documents': total_docs,
            'completed_documents': completed_docs,
            'failed_documents': failed_docs,
            'success_rate': round(completed_docs / total_docs * 100, 2),
            'avg_generation_time_seconds': round(avg_generation_time, 2),
            'total_processing_time_seconds': round(sum(generation_times), 2),
            'start_time': min(d.created_at for d in documents),
            'end_time': max(d.completed_at for d in documents if d.completed_at)
        }