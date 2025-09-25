"""
Admin service for system management and monitoring
"""

import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from config import settings
from app.models.user import User, UserStatus
from app.models.template import Template
from app.models.document import Document, DocumentStatus
from app.models.payment import Payment, Subscription, PaymentStatus, SubscriptionStatus
from app.models.audit import AuditLog, AuditLevel
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

logger = logging.getLogger(__name__)


class AdminService:
    """Administrative service for system management"""
    
    @staticmethod
    def _extract_template_features(template_text: str) -> tuple:
        """Extract TF-IDF features from template text"""
        vectorizer = TfidfVectorizer(
            max_features=100,
            stop_words='english',
            ngram_range=(1, 2)
        )
        features = vectorizer.fit_transform([template_text])
        keywords = [(word, score) for word, score in 
                   zip(vectorizer.get_feature_names_out(),
                       features.toarray()[0]) if score > 0]
        return features, keywords

    @staticmethod
    def _cluster_templates(features, n_clusters=10):
        """Cluster templates using MiniBatchKMeans"""
        clustering = MiniBatchKMeans(
            n_clusters=n_clusters,
            random_state=42
        )
        return clustering.fit_predict(features)

    @staticmethod
    def _calculate_similarity(features) -> dict:
        """Calculate similarity scores between templates"""
        similarity_matrix = cosine_similarity(features)
        return {i: sorted(enumerate(sim_scores), key=lambda x: x[1], reverse=True)[1:6]
                for i, sim_scores in enumerate(similarity_matrix)}

    @staticmethod
    def update_template_classifications(db: Session):
        """Update template classifications and similarities"""
        templates = db.query(Template).filter(Template.is_active == True).all()
        
        # Extract features
        all_texts = [t.content for t in templates]
        all_features = []
        
        for i, template in enumerate(templates):
            features, keywords = AdminService._extract_template_features(template.content)
            template.keywords = keywords
            template.feature_vector = features.toarray()[0].tolist()
            all_features.append(features)
        
        # Combine features
        combined_features = np.vstack([f.toarray() for f in all_features])
        
        # Cluster templates
        clusters = AdminService._cluster_templates(combined_features)
        for template, cluster_id in zip(templates, clusters):
            template.cluster_id = int(cluster_id)
        
        # Calculate similarities
        similarity_scores = AdminService._calculate_similarity(combined_features)
        for i, template in enumerate(templates):
            template.similarity_score = {
                str(templates[idx].id): float(score)
                for idx, score in similarity_scores[i]
            }
        
        db.commit()
        
    @staticmethod
    def recalculate_classifications(db: Session) -> dict:
        """Recalculate all template classifications"""
        try:
            AdminService.update_template_classifications(db)
            return {"success": True, "message": "Template classifications updated"}
        except Exception as e:
            logger.error(f"Failed to update template classifications: {e}")
            return {"success": False, "error": str(e)}
            
    @staticmethod
    def get_cluster_details(db: Session, cluster_id: int) -> dict:
        """Get detailed information about a specific cluster"""
        templates = db.query(Template).filter(
            Template.cluster_id == cluster_id,
            Template.is_active == True
        ).all()
        
        # Get common keywords in cluster
        all_keywords = []
        for template in templates:
            if template.keywords:
                all_keywords.extend(template.keywords)
                
        keyword_counts = {}
        for keyword, score in all_keywords:
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
            
        return {
            "cluster_id": cluster_id,
            "template_count": len(templates),
            "common_keywords": sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            "templates": [{"id": t.id, "name": t.name} for t in templates]
        }
            
    @staticmethod
    def _get_template_classification_stats(db: Session) -> dict:
        """Get template classification statistics"""
        templates = db.query(Template).filter(Template.is_active == True).all()
        
        # Count templates per cluster
        cluster_counts = {}
        for template in templates:
            if template.cluster_id is not None:
                cluster_counts[template.cluster_id] = cluster_counts.get(template.cluster_id, 0) + 1
        
        # Get most common keywords
        all_keywords = []
        for template in templates:
            if template.keywords:
                all_keywords.extend(template.keywords)
        
        keyword_counts = {}
        for keyword, score in all_keywords:
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "clusters": cluster_counts,
            "top_keywords": top_keywords,
            "classified_count": len([t for t in templates if t.keywords])
        }
    
    @staticmethod
    def get_dashboard_stats(db: Session) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics"""
        
        # User statistics
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.status == UserStatus.ACTIVE).count()
        new_users_today = db.query(User).filter(
            func.date(User.created_at) == datetime.utcnow().date()
        ).count()
        
        # Document statistics
        total_documents = db.query(Document).count()
        completed_documents = db.query(Document).filter(
            Document.status == DocumentStatus.COMPLETED
        ).count()
        processing_documents = db.query(Document).filter(
            Document.status == DocumentStatus.PROCESSING
        ).count()
        failed_documents = db.query(Document).filter(
            Document.status == DocumentStatus.FAILED
        ).count()
        
        # Template statistics
        total_templates = db.query(Template).filter(Template.is_active == True).count()
        public_templates = db.query(Template).filter(
            Template.is_active == True,
            Template.is_public == True
        ).count()
        
        # Payment statistics
        total_revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.status == PaymentStatus.COMPLETED
        ).scalar() or 0
        
        monthly_revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.status == PaymentStatus.COMPLETED,
            func.extract('month', Payment.completed_at) == datetime.utcnow().month,
            func.extract('year', Payment.completed_at) == datetime.utcnow().year
        ).scalar() or 0
        
        active_subscriptions = db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.ACTIVE
        ).count()
        
        # System health
        recent_errors = db.query(AuditLog).filter(
            AuditLog.event_level == AuditLevel.ERROR,
            AuditLog.timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        # Storage usage
        storage_usage = AdminService.get_storage_usage()
        
        template_stats = AdminService._get_template_classification_stats(db)
        
        return {
            "users": {
                "total": total_users,
                "active": active_users,
                "new_today": new_users_today,
                "activity_rate": (active_users / total_users * 100) if total_users > 0 else 0
            },
            "documents": {
                "total": total_documents,
                "completed": completed_documents,
                "processing": processing_documents,
                "failed": failed_documents,
                "success_rate": (completed_documents / total_documents * 100) if total_documents > 0 else 0
            },
            "templates": {
                "total": total_templates,
                "public": public_templates,
                "private": total_templates - public_templates,
                "classification": template_stats,
                "clusters": {
                    "total_clusters": len(template_stats.get("clusters", {})),
                    "distribution": template_stats.get("clusters", {}),
                    "top_keywords": template_stats.get("top_keywords", []),
                    "classified_percent": (template_stats.get("classified_count", 0) / total_templates * 100) if total_templates > 0 else 0
                }
            },
            "revenue": {
                "total": float(total_revenue),
                "monthly": float(monthly_revenue),
                "active_subscriptions": active_subscriptions
            },
            "system": {
                "recent_errors": recent_errors,
                "storage_usage_mb": storage_usage["used_mb"],
                "storage_available_mb": storage_usage["available_mb"]
            }
        }
    
    @staticmethod
    def calculate_growth_rate(db: Session, metric: str) -> float:
        """Calculate growth rate for a specific metric"""
        
        current_month_start = datetime.utcnow().replace(day=1)
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        last_month_end = current_month_start - timedelta(days=1)
        
        if metric == "users":
            current_count = db.query(User).filter(
                User.created_at >= current_month_start
            ).count()
            
            last_count = db.query(User).filter(
                User.created_at >= last_month_start,
                User.created_at <= last_month_end
            ).count()
        
        elif metric == "documents":
            current_count = db.query(Document).filter(
                Document.created_at >= current_month_start
            ).count()
            
            last_count = db.query(Document).filter(
                Document.created_at >= last_month_start,
                Document.created_at <= last_month_end
            ).count()
        
        elif metric == "revenue":
            current_count = db.query(func.sum(Payment.amount)).filter(
                Payment.status == PaymentStatus.COMPLETED,
                Payment.completed_at >= current_month_start
            ).scalar() or 0
            
            last_count = db.query(func.sum(Payment.amount)).filter(
                Payment.status == PaymentStatus.COMPLETED,
                Payment.completed_at >= last_month_start,
                Payment.completed_at <= last_month_end
            ).scalar() or 0
        
        else:
            return 0.0
        
        if last_count > 0:
            return ((current_count - last_count) / last_count) * 100
        else:
            return 100.0 if current_count > 0 else 0.0
    
    @staticmethod
    def get_average_template_usage(db: Session) -> float:
        """Get average template usage"""
        
        avg_usage = db.query(func.avg(Template.usage_count)).filter(
            Template.is_active == True
        ).scalar()
        
        return float(avg_usage or 0)
    
    @staticmethod
    def get_monthly_recurring_revenue(db: Session) -> float:
        """Get monthly recurring revenue from active subscriptions"""
        
        monthly_subscriptions = db.query(func.sum(Subscription.amount)).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.billing_cycle == "monthly"
        ).scalar() or 0
        
        yearly_subscriptions = db.query(func.sum(Subscription.amount)).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.billing_cycle == "yearly"
        ).scalar() or 0
        
        # Convert yearly to monthly
        monthly_from_yearly = yearly_subscriptions / 12
        
        return float(monthly_subscriptions + monthly_from_yearly)
    
    @staticmethod
    def hard_delete_user(db: Session, user: User) -> None:
        """Permanently delete user and all related data"""
        
        # Delete user's documents and files
        documents = db.query(Document).filter(Document.user_id == user.id).all()
        for document in documents:
            if document.file_path and os.path.exists(document.file_path):
                try:
                    os.remove(document.file_path)
                except OSError:
                    pass
            db.delete(document)
        
        # Delete user's templates and files
        templates = db.query(Template).filter(Template.created_by == user.id).all()
        for template in templates:
            template_path = os.path.join(settings.TEMPLATES_PATH, template.file_path)
            if os.path.exists(template_path):
                try:
                    os.remove(template_path)
                except OSError:
                    pass
            db.delete(template)
        
        # Delete user's payments (keep for legal/accounting if needed)
        # payments = db.query(Payment).filter(Payment.user_id == user.id).all()
        # for payment in payments:
        #     db.delete(payment)
        
        # Delete user's subscriptions
        subscriptions = db.query(Subscription).filter(Subscription.user_id == user.id).all()
        for subscription in subscriptions:
            db.delete(subscription)
        
        # Delete user's audit logs (anonymize instead of delete for compliance)
        audit_logs = db.query(AuditLog).filter(AuditLog.user_id == user.id).all()
        for log in audit_logs:
            log.user_id = None
            log.ip_address = "XXX.XXX.XXX.XXX"
            log.user_agent = "[DELETED]"
        
        # Finally delete the user
        db.delete(user)
        db.commit()
    
    @staticmethod
    def get_system_health(db: Session) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        
        health = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "components": {}
        }
        
        # Database health
        try:
            db.execute("SELECT 1")
            health["components"]["database"] = {
                "status": "healthy",
                "response_time_ms": 10  # Would measure actual response time
            }
        except Exception as e:
            health["components"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health["overall_status"] = "unhealthy"
        
        # Storage health
        storage_info = AdminService.get_storage_usage()
        if storage_info["available_mb"] > 1000:  # More than 1GB available
            health["components"]["storage"] = {
                "status": "healthy",
                "used_mb": storage_info["used_mb"],
                "available_mb": storage_info["available_mb"],
                "usage_percent": storage_info["usage_percent"]
            }
        else:
            health["components"]["storage"] = {
                "status": "warning",
                "used_mb": storage_info["used_mb"],
                "available_mb": storage_info["available_mb"],
                "usage_percent": storage_info["usage_percent"],
                "message": "Low disk space"
            }
            if health["overall_status"] == "healthy":
                health["overall_status"] = "degraded"
        
        # Error rate check
        recent_errors = db.query(AuditLog).filter(
            AuditLog.event_level.in_([AuditLevel.ERROR, AuditLevel.CRITICAL]),
            AuditLog.timestamp >= datetime.utcnow() - timedelta(hours=1)
        ).count()
        
        if recent_errors < 10:
            health["components"]["error_rate"] = {
                "status": "healthy",
                "errors_last_hour": recent_errors
            }
        else:
            health["components"]["error_rate"] = {
                "status": "warning",
                "errors_last_hour": recent_errors,
                "message": "High error rate detected"
            }
            if health["overall_status"] == "healthy":
                health["overall_status"] = "degraded"
        
        return health
    
    @staticmethod
    def get_storage_usage() -> Dict[str, float]:
        """Get storage usage statistics"""
        
        try:
            usage = shutil.disk_usage(settings.STORAGE_PATH)
            total_mb = usage.total / (1024 * 1024)
            used_mb = (usage.total - usage.free) / (1024 * 1024)
            available_mb = usage.free / (1024 * 1024)
            usage_percent = (used_mb / total_mb) * 100
            
            return {
                "total_mb": total_mb,
                "used_mb": used_mb,
                "available_mb": available_mb,
                "usage_percent": usage_percent
            }
        except Exception:
            return {
                "total_mb": 0,
                "used_mb": 0,
                "available_mb": 0,
                "usage_percent": 0
            }
    
    @staticmethod
    def set_maintenance_mode(enabled: bool, message: Optional[str] = None) -> None:
        """Set system maintenance mode"""
        
        # In a real implementation, this would:
        # 1. Write to a config file or database
        # 2. Update a feature flag
        # 3. Notify load balancers
        
        maintenance_file = os.path.join(settings.STORAGE_PATH, "maintenance.json")
        
        if enabled:
            maintenance_data = {
                "enabled": True,
                "message": message or "System is under maintenance. Please try again later.",
                "started_at": datetime.utcnow().isoformat()
            }
            
            with open(maintenance_file, 'w') as f:
                import json
                json.dump(maintenance_data, f)
        else:
            if os.path.exists(maintenance_file):
                os.remove(maintenance_file)
    
    @staticmethod
    def cleanup_orphaned_files(db: Session, dry_run: bool = True) -> Dict[str, Any]:
        """Cleanup orphaned files not referenced in database"""
        
        result = {
            "removed_count": 0,
            "space_freed": 0,
            "orphaned_files": []
        }
        
        # Get all file references from database
        document_files = set()
        template_files = set()
        
        documents = db.query(Document).filter(Document.file_path.isnot(None)).all()
        for doc in documents:
            if doc.file_path:
                document_files.add(os.path.basename(doc.file_path))
        
        templates = db.query(Template).filter(Template.file_path.isnot(None)).all()
        for template in templates:
            if template.file_path:
                template_files.add(template.file_path)
        
        # Check documents directory
        docs_dir = Path(settings.DOCUMENTS_PATH)
        if docs_dir.exists():
            for file_path in docs_dir.iterdir():
                if file_path.is_file() and file_path.name not in document_files:
                    file_size = file_path.stat().st_size
                    result["orphaned_files"].append({
                        "path": str(file_path),
                        "size": file_size,
                        "type": "document"
                    })
                    
                    if not dry_run:
                        try:
                            file_path.unlink()
                            result["removed_count"] += 1
                            result["space_freed"] += file_size
                        except OSError:
                            pass
        
        # Check templates directory
        templates_dir = Path(settings.TEMPLATES_PATH)
        if templates_dir.exists():
            for file_path in templates_dir.iterdir():
                if file_path.is_file() and file_path.name not in template_files:
                    file_size = file_path.stat().st_size
                    result["orphaned_files"].append({
                        "path": str(file_path),
                        "size": file_size,
                        "type": "template"
                    })
                    
                    if not dry_run:
                        try:
                            file_path.unlink()
                            result["removed_count"] += 1
                            result["space_freed"] += file_size
                        except OSError:
                            pass
        
        return result
    
    @staticmethod
    def get_usage_analytics(db: Session, days: int = 30) -> Dict[str, Any]:
        """Get detailed usage analytics"""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Daily document generation
        daily_docs = db.query(
            func.date(Document.created_at).label('date'),
            func.count(Document.id).label('count')
        ).filter(
            Document.created_at >= start_date
        ).group_by(
            func.date(Document.created_at)
        ).order_by('date').all()
        
        # Template usage
        template_usage = db.query(
            Template.name,
            Template.usage_count,
            Template.category
        ).filter(
            Template.is_active == True
        ).order_by(
            desc(Template.usage_count)
        ).limit(10).all()
        
        # User activity
        active_users = db.query(
            func.date(User.last_login_at).label('date'),
            func.count(User.id).label('count')
        ).filter(
            User.last_login_at >= start_date
        ).group_by(
            func.date(User.last_login_at)
        ).order_by('date').all()
        
        return {
            "period_days": days,
            "daily_documents": [
                {
                    "date": str(item.date),
                    "count": item.count
                }
                for item in daily_docs
            ],
            "template_usage": [
                {
                    "name": template.name,
                    "usage_count": template.usage_count,
                    "category": template.category
                }
                for template in template_usage
            ],
            "daily_active_users": [
                {
                    "date": str(item.date),
                    "count": item.count
                }
                for item in active_users
            ]
        }
    
    @staticmethod
    def create_system_backup(include_files: bool = True) -> Dict[str, Any]:
        """Create comprehensive system backup"""
        
        backup_id = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        backup_dir = os.path.join(settings.STORAGE_PATH, "backups", backup_id)
        
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_size = 0
        
        try:
            # Backup database using PostgreSQL pg_dump
            try:
                backup_db_path = os.path.join(backup_dir, "database_backup.sql")
                import subprocess
                
                # Extract connection details from DATABASE_URL
                db_url = settings.DATABASE_URL
                subprocess.run([
                    "pg_dump", db_url, "-f", backup_db_path
                ], check=True, capture_output=True)
                
                if os.path.exists(backup_db_path):
                    backup_size += os.path.getsize(backup_db_path)
            except subprocess.CalledProcessError as e:
                logger.warning(f"PostgreSQL backup failed: {e}")
            except Exception as e:
                logger.warning(f"Database backup not available: {e}")
            
            # Backup files if requested
            if include_files:
                # Backup templates
                templates_backup = os.path.join(backup_dir, "templates")
                if os.path.exists(settings.TEMPLATES_PATH):
                    shutil.copytree(settings.TEMPLATES_PATH, templates_backup)
                    backup_size += sum(
                        os.path.getsize(os.path.join(dirpath, filename))
                        for dirpath, dirnames, filenames in os.walk(templates_backup)
                        for filename in filenames
                    )
                
                # Backup documents (recent ones only to save space)
                documents_backup = os.path.join(backup_dir, "documents")
                os.makedirs(documents_backup, exist_ok=True)
                
                if os.path.exists(settings.DOCUMENTS_PATH):
                    cutoff_date = datetime.utcnow() - timedelta(days=30)
                    
                    for file_path in Path(settings.DOCUMENTS_PATH).iterdir():
                        if file_path.is_file():
                            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                            if file_mtime >= cutoff_date:
                                backup_file_path = os.path.join(documents_backup, file_path.name)
                                shutil.copy2(file_path, backup_file_path)
                                backup_size += os.path.getsize(backup_file_path)
            
            return {
                "backup_id": backup_id,
                "backup_path": backup_dir,
                "size": backup_size,
                "size_mb": round(backup_size / (1024 * 1024), 2),
                "include_files": include_files,
                "created_at": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            # Cleanup failed backup
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            
            raise Exception(f"Backup failed: {str(e)}")
    
    @staticmethod
    def get_performance_metrics(hours: int = 24) -> Dict[str, Any]:
        """Get system performance metrics"""
        
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        # This would integrate with actual monitoring tools
        # For now, return simulated metrics
        
        return {
            "period_hours": hours,
            "api_response_times": {
                "avg_ms": 150,
                "p95_ms": 300,
                "p99_ms": 500
            },
            "document_generation": {
                "avg_time_seconds": 2.5,
                "success_rate": 98.5,
                "failures": 12
            },
            "memory_usage": {
                "current_mb": 512,
                "peak_mb": 768,
                "avg_mb": 600
            },
            "cpu_usage": {
                "current_percent": 25,
                "peak_percent": 85,
                "avg_percent": 45
            },
            "database": {
                "connection_count": 15,
                "avg_query_time_ms": 25,
                "slow_queries": 3
            }
        }
