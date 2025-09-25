"""
System cleanup and maintenance tasks
"""

import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any
from pathlib import Path
from celery import Celery
from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal
from app.models.audit import AuditLog
from app.models.document import Document, DocumentStatus
from app.models.template import Template
from app.models.visit import Visit
from app.services.audit_service import AuditService
from app.services.encryption_service import EncryptionService

# Create Celery instance
celery_app = Celery(
    "cleanup_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)


@celery_app.task
def cleanup_old_audit_logs_task():
    """Clean up old audit logs based on retention policy"""

    db = SessionLocal()

    try:
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=settings.AUDIT_LOG_RETENTION_DAYS)

        # Count logs to be deleted
        logs_to_delete = db.query(AuditLog).filter(
            AuditLog.timestamp < cutoff_date,
            AuditLog.requires_retention == False
        ).count()

        # Delete old logs
        deleted_count = db.query(AuditLog).filter(
            AuditLog.timestamp < cutoff_date,
            AuditLog.requires_retention == False
        ).delete()

        db.commit()

        # Log cleanup activity
        AuditService.log_system_event(
            "AUDIT_LOGS_CLEANED",
            {
                "deleted_count": deleted_count,
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": settings.AUDIT_LOG_RETENTION_DAYS
            }
        )

        return {
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat()
        }

    except Exception as e:
        AuditService.log_system_event(
            "AUDIT_LOG_CLEANUP_FAILED",
            {"error": str(e)}
        )
        raise e

    finally:
        db.close()


@celery_app.task
def cleanup_expired_documents_task():
    """Clean up expired documents"""

    db = SessionLocal()

    try:
        current_time = datetime.utcnow()
        deleted_count = 0
        space_freed = 0

        # Find expired documents
        expired_documents = db.query(Document).filter(
            Document.auto_delete == True,
            Document.retention_expires_at < current_time
        ).all()

        for document in expired_documents:
            try:
                # Remove file if exists
                if document.file_path and os.path.exists(document.file_path):
                    file_size = os.path.getsize(document.file_path)

                    # Secure delete
                    if EncryptionService.secure_delete_file(document.file_path):
                        space_freed += file_size

                # Log document deletion
                AuditService.log_document_event(
                    "DOCUMENT_AUTO_DELETED",
                    document.user_id,
                    None,
                    {
                        "document_id": document.id,
                        "title": document.title,
                        "reason": "retention_expired"
                    }
                )

                # Delete from database
                db.delete(document)
                deleted_count += 1

            except Exception as e:
                print(f"Error deleting expired document {document.id}: {e}")
                continue

        db.commit()

        # Log cleanup results
        AuditService.log_system_event(
            "EXPIRED_DOCUMENTS_CLEANED",
            {
                "deleted_count": deleted_count,
                "space_freed_bytes": space_freed,
                "space_freed_mb": round(space_freed / (1024 * 1024), 2)
            }
        )

        return {
            "deleted_count": deleted_count,
            "space_freed_bytes": space_freed
        }

    except Exception as e:
        AuditService.log_system_event(
            "EXPIRED_DOCUMENT_CLEANUP_FAILED",
            {"error": str(e)}
        )
        raise e

    finally:
        db.close()


@celery_app.task
def cleanup_unused_files_task():
    """Clean up files not referenced in database"""

    db = SessionLocal()

    try:
        deleted_count = 0
        space_freed = 0

        # Get all file paths from database
        document_files = set()
        template_files = set()

        # Get document files
        documents = db.query(Document).filter(Document.file_path.isnot(None)).all()
        for doc in documents:
            if doc.file_path:
                document_files.add(os.path.basename(doc.file_path))

        # Get template files
        templates = db.query(Template).filter(Template.file_path.isnot(None)).all()
        for template in templates:
            if template.file_path:
                template_files.add(template.file_path)

        # Check documents directory
        documents_dir = Path(settings.DOCUMENTS_PATH)
        if documents_dir.exists():
            for file_path in documents_dir.iterdir():
                if file_path.is_file():
                    if file_path.name not in document_files:
                        # File not referenced in database
                        try:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            deleted_count += 1
                            space_freed += file_size
                        except OSError:
                            pass

        # Check templates directory
        templates_dir = Path(settings.TEMPLATES_PATH)
        if templates_dir.exists():
            for file_path in templates_dir.iterdir():
                if file_path.is_file():
                    if file_path.name not in template_files:
                        # File not referenced in database
                        try:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            deleted_count += 1
                            space_freed += file_size
                        except OSError:
                            pass

        # Log cleanup results
        AuditService.log_system_event(
            "UNUSED_FILES_CLEANED",
            {
                "deleted_count": deleted_count,
                "space_freed_bytes": space_freed,
                "space_freed_mb": round(space_freed / (1024 * 1024), 2)
            }
        )

        return {
            "deleted_count": deleted_count,
            "space_freed_bytes": space_freed
        }

    except Exception as e:
        AuditService.log_system_event(
            "UNUSED_FILE_CLEANUP_FAILED",
            {"error": str(e)}
        )
        raise e

    finally:
        db.close()


@celery_app.task
def cleanup_old_visits_task():
    """Clean up old visit records for analytics"""

    db = SessionLocal()

    try:
        # Keep visits for 1 year
        cutoff_date = datetime.utcnow() - timedelta(days=365)

        # Delete old visits that don't have analytics consent
        deleted_count = db.query(Visit).filter(
            Visit.visited_at < cutoff_date,
            Visit.analytics_consent == False
        ).delete()

        db.commit()

        # Log cleanup
        AuditService.log_system_event(
            "OLD_VISITS_CLEANED",
            {
                "deleted_count": deleted_count,
                "cutoff_date": cutoff_date.isoformat()
            }
        )

        return {"deleted_count": deleted_count}

    except Exception as e:
        AuditService.log_system_event(
            "VISIT_CLEANUP_FAILED",
            {"error": str(e)}
        )
        raise e

    finally:
        db.close()


@celery_app.task
def optimize_database_task():
    """Optimize database performance"""

    db = SessionLocal()

    try:
        optimization_results = {}

        # PostgreSQL-specific optimizations
        db.execute("VACUUM ANALYZE")
        db.execute("REINDEX DATABASE CONCURRENTLY")
        optimization_results["postgresql_vacuum"] = "completed"
        optimization_results["postgresql_reindex"] = "completed"

        db.commit()

        # Log optimization
        AuditService.log_system_event(
            "DATABASE_OPTIMIZED",
            optimization_results
        )

        return optimization_results

    except Exception as e:
        AuditService.log_system_event(
            "DATABASE_OPTIMIZATION_FAILED",
            {"error": str(e)}
        )
        raise e

    finally:
        db.close()


@celery_app.task
def backup_database_task():
    """Create database backup"""

    try:
        backup_filename = f"mytypist_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.sql"
        backup_path = os.path.join(settings.STORAGE_PATH, "backups", backup_filename)

        # Ensure backup directory exists
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)

        backup_success = False
        backup_size = 0

        # PostgreSQL backup using pg_dump
        import subprocess

        try:
            result = subprocess.run([
                "pg_dump",
                settings.DATABASE_URL,
                "-f", backup_path
            ], check=True, capture_output=True, text=True)

            if os.path.exists(backup_path):
                backup_size = os.path.getsize(backup_path)
                backup_success = True

        except subprocess.CalledProcessError as e:
            print(f"PostgreSQL backup failed: {e}")
            backup_success = False

        if backup_success:
            # Log successful backup
            AuditService.log_system_event(
                "DATABASE_BACKUP_CREATED",
                {
                    "backup_filename": backup_filename,
                    "backup_size_bytes": backup_size,
                    "backup_size_mb": round(backup_size / (1024 * 1024), 2)
                }
            )
        else:
            AuditService.log_system_event(
                "DATABASE_BACKUP_FAILED",
                {"backup_filename": backup_filename}
            )

        return {
            "success": backup_success,
            "backup_filename": backup_filename,
            "backup_size_bytes": backup_size
        }

    except Exception as e:
        AuditService.log_system_event(
            "DATABASE_BACKUP_ERROR",
            {"error": str(e)}
        )
        raise e


@celery_app.task
def cleanup_old_backups_task():
    """Clean up old backup files"""

    try:
        backup_dir = os.path.join(settings.STORAGE_PATH, "backups")

        if not os.path.exists(backup_dir):
            return {"deleted_count": 0}

        # Keep backups for 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        cutoff_timestamp = cutoff_date.timestamp()

        deleted_count = 0
        space_freed = 0

        for filename in os.listdir(backup_dir):
            file_path = os.path.join(backup_dir, filename)

            if os.path.isfile(file_path):
                file_mtime = os.path.getmtime(file_path)

                if file_mtime < cutoff_timestamp:
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        space_freed += file_size
                    except OSError:
                        pass

        # Log cleanup
        AuditService.log_system_event(
            "OLD_BACKUPS_CLEANED",
            {
                "deleted_count": deleted_count,
                "space_freed_bytes": space_freed,
                "space_freed_mb": round(space_freed / (1024 * 1024), 2)
            }
        )

        return {
            "deleted_count": deleted_count,
            "space_freed_bytes": space_freed
        }

    except Exception as e:
        AuditService.log_system_event(
            "BACKUP_CLEANUP_FAILED",
            {"error": str(e)}
        )
        raise e


@celery_app.task
def system_health_check_task():
    """Perform system health check"""

    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    # Check database connectivity
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = f"unhealthy: {str(e)}"

    # Check storage space
    try:
        storage_usage = shutil.disk_usage(settings.STORAGE_PATH)
        free_space_gb = storage_usage.free / (1024 ** 3)

        if free_space_gb > 1:  # More than 1GB free
            health_status["checks"]["storage"] = "healthy"
        else:
            health_status["checks"]["storage"] = f"low space: {free_space_gb:.1f}GB"
    except Exception as e:
        health_status["checks"]["storage"] = f"error: {str(e)}"

    # Check if critical directories exist
    critical_dirs = [settings.DOCUMENTS_PATH, settings.TEMPLATES_PATH]
    for dir_path in critical_dirs:
        if os.path.exists(dir_path) and os.access(dir_path, os.W_OK):
            health_status["checks"][f"directory_{os.path.basename(dir_path)}"] = "healthy"
        else:
            health_status["checks"][f"directory_{os.path.basename(dir_path)}"] = "missing or not writable"

    # Overall health
    unhealthy_checks = [k for k, v in health_status["checks"].items() if "unhealthy" in v or "error" in v or "missing" in v]
    health_status["overall_status"] = "unhealthy" if unhealthy_checks else "healthy"

    # Log health check
    AuditService.log_system_event(
        "SYSTEM_HEALTH_CHECK",
        health_status
    )

    return health_status


# Schedule periodic tasks
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Set up periodic cleanup tasks"""

    # Clean audit logs daily
    sender.add_periodic_task(
        86400.0,  # 24 hours
        cleanup_old_audit_logs_task.s(),
        name='cleanup old audit logs'
    )

    # Clean expired documents daily
    sender.add_periodic_task(
        86400.0,  # 24 hours
        cleanup_expired_documents_task.s(),
        name='cleanup expired documents'
    )

    # Clean unused files weekly
    sender.add_periodic_task(
        604800.0,  # 7 days
        cleanup_unused_files_task.s(),
        name='cleanup unused files'
    )

    # Clean old visits monthly
    sender.add_periodic_task(
        2592000.0,  # 30 days
        cleanup_old_visits_task.s(),
        name='cleanup old visits'
    )

    # Optimize database weekly
    sender.add_periodic_task(
        604800.0,  # 7 days
        optimize_database_task.s(),
        name='optimize database'
    )

    # Create backup daily
    sender.add_periodic_task(
        86400.0,  # 24 hours
        backup_database_task.s(),
        name='create database backup'
    )

    # Clean old backups weekly
    sender.add_periodic_task(
        604800.0,  # 7 days
        cleanup_old_backups_task.s(),
        name='cleanup old backups'
    )

    # Health check every 6 hours
    sender.add_periodic_task(
        21600.0,  # 6 hours
        system_health_check_task.s(),
        name='system health check'
    )
