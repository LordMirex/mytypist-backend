"""
Document processing background tasks
"""

import os
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from celery import Celery
from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.template import Template
from app.services.document_service import DocumentService
from app.services.audit_service import AuditService

# Create Celery instance
celery_app = Celery(
    "document_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)


@celery_app.task(bind=True, max_retries=3)
def generate_document_task(self, document_id: int, placeholder_data: Dict[str, Any]):
    """Generate document from template in background"""
    
    db = SessionLocal()
    
    try:
        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise Exception(f"Document {document_id} not found")
        
        # Update status to processing
        document.status = DocumentStatus.PROCESSING
        db.commit()
        
        # Generate document (run async function in sync context)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        success = loop.run_until_complete(
            DocumentService.generate_document_from_template(document_id, placeholder_data)
        )
        
        # Refresh document to get updated data
        db.refresh(document)
        
        if success:
            # Log successful generation
            AuditService.log_document_event(
                "DOCUMENT_GENERATED",
                document.user_id,
                None,
                {
                    "document_id": document_id,
                    "template_id": document.template_id,
                    "generation_time": document.generation_time
                }
            )
        else:
            # Log failure
            AuditService.log_document_event(
                "DOCUMENT_GENERATION_FAILED",
                document.user_id,
                None,
                {
                    "document_id": document_id,
                    "template_id": document.template_id,
                    "error": document.error_message
                }
            )
        
        return {
            "document_id": document_id,
            "success": success,
            "status": document.status.value
        }
    
    except Exception as exc:
        # Update document with error
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = DocumentStatus.FAILED
                document.error_message = str(exc)
                db.commit()
        except:
            pass
        
        # Retry task
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))
        
        # Log final failure
        AuditService.log_system_event(
            "DOCUMENT_GENERATION_FAILED",
            {
                "document_id": document_id,
                "error": str(exc),
                "retries": self.request.retries
            }
        )
        
        raise exc
    
    finally:
        db.close()


@celery_app.task(bind=True)
def generate_batch_documents_task(
    self, 
    batch_id: str, 
    document_ids: List[int], 
    placeholder_data_list: List[Dict[str, Any]]
):
    """Generate multiple documents in batch"""
    
    db = SessionLocal()
    results = []
    
    try:
        total_documents = len(document_ids)
        successful = 0
        failed = 0
        
        for i, (document_id, placeholder_data) in enumerate(zip(document_ids, placeholder_data_list)):
            try:
                # Update progress
                progress = int((i / total_documents) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i,
                        'total': total_documents,
                        'progress': progress,
                        'batch_id': batch_id
                    }
                )
                
                # Generate document directly (not using delay to avoid recursion)
                result_data = generate_document_task(document_id, placeholder_data)
                
                if result_data["success"]:
                    successful += 1
                else:
                    failed += 1
                
                results.append({
                    "document_id": document_id,
                    "success": result_data["success"],
                    "status": result_data["status"]
                })
            
            except Exception as e:
                failed += 1
                results.append({
                    "document_id": document_id,
                    "success": False,
                    "error": str(e)
                })
        
        # Log batch completion
        AuditService.log_system_event(
            "BATCH_GENERATION_COMPLETED",
            {
                "batch_id": batch_id,
                "total_documents": total_documents,
                "successful": successful,
                "failed": failed
            }
        )
        
        return {
            "batch_id": batch_id,
            "total_documents": total_documents,
            "successful": successful,
            "failed": failed,
            "results": results
        }
    
    except Exception as exc:
        AuditService.log_system_event(
            "BATCH_GENERATION_FAILED",
            {
                "batch_id": batch_id,
                "error": str(exc)
            }
        )
        raise exc
    
    finally:
        db.close()


@celery_app.task
def cleanup_temporary_files_task():
    """Clean up temporary files"""
    
    try:
        from pathlib import Path
        import tempfile
        
        cleanup_count = 0
        space_freed = 0
        
        # Clean temporary directories
        temp_dirs = [
            settings.DOCUMENTS_PATH,
            settings.TEMPLATES_PATH,
            tempfile.gettempdir()
        ]
        
        for temp_dir in temp_dirs:
            if not os.path.exists(temp_dir):
                continue
            
            for file_path in Path(temp_dir).rglob("*"):
                if file_path.is_file():
                    # Check if file is temporary (older than 1 hour)
                    file_age = time.time() - file_path.stat().st_mtime
                    
                    if file_age > 3600:  # 1 hour
                        # Check if it's a temporary file
                        if any(file_path.name.endswith(ext) for ext in ['.tmp', '.temp', '.processing']):
                            try:
                                file_size = file_path.stat().st_size
                                file_path.unlink()
                                cleanup_count += 1
                                space_freed += file_size
                            except OSError:
                                pass
        
        # Log cleanup results
        AuditService.log_system_event(
            "TEMPORARY_FILES_CLEANED",
            {
                "files_removed": cleanup_count,
                "space_freed_bytes": space_freed,
                "space_freed_mb": round(space_freed / (1024 * 1024), 2)
            }
        )
        
        return {
            "files_removed": cleanup_count,
            "space_freed_bytes": space_freed
        }
    
    except Exception as e:
        AuditService.log_system_event(
            "CLEANUP_FAILED",
            {"error": str(e)}
        )
        raise e


@celery_app.task
def optimize_document_storage_task():
    """Optimize document storage by compressing old files"""
    
    db = SessionLocal()
    
    try:
        import gzip
        import shutil
        from datetime import timedelta
        
        # Get documents older than 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        old_documents = db.query(Document).filter(
            Document.completed_at < thirty_days_ago,
            Document.status == DocumentStatus.COMPLETED,
            Document.file_path.isnot(None)
        ).all()
        
        compressed_count = 0
        space_saved = 0
        
        for document in old_documents:
            file_path = document.file_path
            if not file_path or not os.path.exists(file_path):
                continue
            
            # Skip if already compressed
            if file_path.endswith('.gz'):
                continue
            
            try:
                original_size = os.path.getsize(file_path)
                compressed_path = file_path + '.gz'
                
                # Compress file
                with open(file_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Verify compression
                if os.path.exists(compressed_path):
                    compressed_size = os.path.getsize(compressed_path)
                    
                    # Update document path
                    document.file_path = compressed_path
                    
                    # Remove original
                    os.remove(file_path)
                    
                    compressed_count += 1
                    space_saved += (original_size - compressed_size)
            
            except Exception as e:
                print(f"Error compressing document {document.id}: {e}")
                continue
        
        db.commit()
        
        # Log optimization results
        AuditService.log_system_event(
            "STORAGE_OPTIMIZED",
            {
                "documents_compressed": compressed_count,
                "space_saved_bytes": space_saved,
                "space_saved_mb": round(space_saved / (1024 * 1024), 2)
            }
        )
        
        return {
            "documents_compressed": compressed_count,
            "space_saved_bytes": space_saved
        }
    
    except Exception as e:
        AuditService.log_system_event(
            "STORAGE_OPTIMIZATION_FAILED",
            {"error": str(e)}
        )
        raise e
    
    finally:
        db.close()


@celery_app.task
def generate_document_thumbnails_task():
    """Generate thumbnails for documents"""
    
    db = SessionLocal()
    
    try:
        # Get documents without thumbnails
        documents = db.query(Document).filter(
            Document.status == DocumentStatus.COMPLETED,
            Document.file_path.isnot(None)
        ).all()
        
        thumbnail_count = 0
        
        for document in documents:
            file_path = document.file_path
            if not file_path or not os.path.exists(file_path):
                continue
            
            try:
                # Generate thumbnail (implementation would depend on document type)
                thumbnail_path = generate_document_thumbnail(file_path)
                
                if thumbnail_path:
                    # Store thumbnail path in document metadata
                    placeholder_data = document.placeholder_data or {}
                    placeholder_data["thumbnail_path"] = thumbnail_path
                    document.placeholder_data = placeholder_data
                    thumbnail_count += 1
            
            except Exception as e:
                print(f"Error generating thumbnail for document {document.id}: {e}")
                continue
        
        db.commit()
        
        return {"thumbnails_generated": thumbnail_count}
    
    except Exception as e:
        AuditService.log_system_event(
            "THUMBNAIL_GENERATION_FAILED",
            {"error": str(e)}
        )
        raise e
    
    finally:
        db.close()


def generate_document_thumbnail(file_path: str) -> str:
    """Generate thumbnail for document file (DOCX, PDF, or image)"""
    import os
    from PIL import Image
    try:
        ext = os.path.splitext(file_path)[1].lower()
        thumbnail_path = f"{file_path}.thumbnail.png"
        if ext == ".pdf":
            from pdf2image import convert_from_path
            pages = convert_from_path(file_path, first_page=1, last_page=1)
            if pages:
                pages[0].save(thumbnail_path, "PNG")
        elif ext in [".docx", ".doc"]:
            from docx2pdf import convert as docx2pdf_convert
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_path = os.path.join(tmpdir, "temp.pdf")
                docx2pdf_convert(file_path, pdf_path)
                from pdf2image import convert_from_path
                pages = convert_from_path(pdf_path, first_page=1, last_page=1)
                if pages:
                    pages[0].save(thumbnail_path, "PNG")
        elif ext in [".png", ".jpg", ".jpeg"]:
            with Image.open(file_path) as img:
                img.thumbnail((400, 400))
                img.save(thumbnail_path, "PNG")
        else:
            raise ValueError("Unsupported file type for thumbnail generation")
        return thumbnail_path
    except Exception as e:
        logger.error(f"Failed to generate thumbnail for {file_path}: {e}")
        raise