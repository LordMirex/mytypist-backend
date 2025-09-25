"""
Performance Tracking Service
Track document generation times, user productivity, and time-saved calculations
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, func, desc
from database import Base

logger = logging.getLogger(__name__)


class DocumentGenerationMetric(Base):
    """Track document generation performance metrics"""
    __tablename__ = "document_generation_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=True, index=True)
    template_id = Column(Integer, ForeignKey('templates.id'), nullable=False, index=True)

    # Performance metrics
    generation_time_ms = Column(Integer, nullable=False)  # Time to generate document
    processing_time_ms = Column(Integer, nullable=True)  # Backend processing time
    user_input_time_ms = Column(Integer, nullable=True)  # Time user spent filling form

    # Document details
    document_type = Column(String(100), nullable=True)
    placeholder_count = Column(Integer, default=0)
    document_size_bytes = Column(Integer, nullable=True)

    # Time savings calculation
    estimated_manual_time_minutes = Column(Integer, nullable=True)  # How long manually
    actual_time_minutes = Column(Float, nullable=True)  # Actual time with system
    time_saved_minutes = Column(Float, nullable=True)  # Calculated time saved

    # Quality metrics
    user_satisfaction_score = Column(Integer, nullable=True)  # 1-5 rating
    generation_success = Column(Boolean, default=True)
    error_details = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class UserProductivityMetric(Base):
    """Track user productivity and activity metrics"""
    __tablename__ = "user_productivity_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    # Daily metrics
    date = Column(DateTime, nullable=False, index=True)
    documents_created = Column(Integer, default=0)
    time_spent_minutes = Column(Float, default=0.0)
    time_saved_minutes = Column(Float, default=0.0)

    # Activity metrics
    login_count = Column(Integer, default=0)
    page_views = Column(Integer, default=0)
    templates_browsed = Column(Integer, default=0)
    drafts_created = Column(Integer, default=0)

    # Efficiency metrics
    average_generation_time_ms = Column(Integer, nullable=True)
    success_rate_percentage = Column(Float, default=100.0)
    tokens_spent = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SystemPerformanceMetric(Base):
    """Track overall system performance"""
    __tablename__ = "system_performance_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # Time period
    date = Column(DateTime, nullable=False, index=True)
    hour = Column(Integer, nullable=True)  # For hourly metrics

    # System metrics
    total_documents_generated = Column(Integer, default=0)
    average_generation_time_ms = Column(Integer, nullable=True)
    peak_generation_time_ms = Column(Integer, nullable=True)
    fastest_generation_time_ms = Column(Integer, nullable=True)

    # User metrics
    active_users = Column(Integer, default=0)
    new_registrations = Column(Integer, default=0)
    total_time_saved_minutes = Column(Float, default=0.0)

    # Error tracking
    generation_errors = Column(Integer, default=0)
    system_uptime_percentage = Column(Float, default=100.0)

    created_at = Column(DateTime, default=datetime.utcnow)


class PerformanceTrackingService:
    """Service for tracking and calculating performance metrics"""

    @staticmethod
    def start_document_generation_tracking(
        db: Session,
        user_id: Optional[int],
        template_id: int,
        placeholder_count: int = 0
    ) -> Dict[str, Any]:
        """Start tracking a document generation process"""
        try:
            tracking_data = {
                "start_time": datetime.utcnow(),
                "user_id": user_id,
                "template_id": template_id,
                "placeholder_count": placeholder_count
            }

            return {
                "success": True,
                "tracking_id": f"track_{user_id or 'guest'}_{template_id}_{int(datetime.utcnow().timestamp())}",
                "tracking_data": tracking_data
            }

        except Exception as e:
            logger.error(f"Failed to start generation tracking: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def complete_document_generation_tracking(
        db: Session,
        tracking_data: Dict[str, Any],
        document_id: Optional[int] = None,
        user_input_time_seconds: Optional[float] = None,
        generation_success: bool = True,
        error_details: Optional[str] = None
    ) -> Dict[str, Any]:
        """Complete document generation tracking and calculate metrics"""
        try:
            end_time = datetime.utcnow()
            start_time = tracking_data.get("start_time", end_time)

            # Calculate generation time
            generation_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Estimate manual time based on document type and complexity
            estimated_manual_time = PerformanceTrackingService._estimate_manual_time(
                tracking_data.get("template_id"),
                tracking_data.get("placeholder_count", 0),
                db
            )

            # Calculate actual time user spent
            actual_time_minutes = (user_input_time_seconds or 0) / 60
            if generation_time_ms > 0:
                actual_time_minutes += generation_time_ms / 60000  # Add generation time

            # Calculate time saved
            time_saved_minutes = max(0, estimated_manual_time - actual_time_minutes)

            # Create metric record
            metric = DocumentGenerationMetric(
                user_id=tracking_data.get("user_id"),
                document_id=document_id,
                template_id=tracking_data.get("template_id"),
                generation_time_ms=generation_time_ms,
                user_input_time_ms=int((user_input_time_seconds or 0) * 1000),
                placeholder_count=tracking_data.get("placeholder_count", 0),
                estimated_manual_time_minutes=int(estimated_manual_time),
                actual_time_minutes=actual_time_minutes,
                time_saved_minutes=time_saved_minutes,
                generation_success=generation_success,
                error_details=error_details
            )

            db.add(metric)
            db.commit()

            # Update user productivity metrics
            if tracking_data.get("user_id"):
                PerformanceTrackingService._update_user_productivity_metrics(
                    db,
                    tracking_data["user_id"],
                    generation_time_ms,
                    time_saved_minutes,
                    generation_success
                )

            # Update system metrics
            PerformanceTrackingService._update_system_metrics(
                db, generation_time_ms, time_saved_minutes, generation_success
            )

            logger.info(f"Generation tracking completed: {generation_time_ms}ms, saved {time_saved_minutes:.1f} minutes")

            return {
                "success": True,
                "metrics": {
                    "generation_time_ms": generation_time_ms,
                    "generation_time_seconds": generation_time_ms / 1000,
                    "estimated_manual_time_minutes": estimated_manual_time,
                    "actual_time_minutes": round(actual_time_minutes, 2),
                    "time_saved_minutes": round(time_saved_minutes, 2),
                    "efficiency_percentage": round((time_saved_minutes / max(estimated_manual_time, 1)) * 100, 1)
                },
                "user_message": PerformanceTrackingService._generate_user_message(
                    generation_time_ms, time_saved_minutes
                )
            }

        except Exception as e:
            logger.error(f"Failed to complete generation tracking: {e}")
            raise

    @staticmethod
    def get_user_performance_stats(
        db: Session,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get user performance statistics"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            # Get generation metrics
            generation_metrics = db.query(DocumentGenerationMetric).filter(
                DocumentGenerationMetric.user_id == user_id,
                DocumentGenerationMetric.created_at >= start_date
            ).all()

            if not generation_metrics:
                return {
                    "success": True,
                    "period_days": days,
                    "stats": {
                        "documents_created": 0,
                        "total_time_saved_minutes": 0,
                        "average_generation_time_ms": 0,
                        "total_time_saved_hours": 0,
                        "efficiency_score": 0
                    }
                }

            # Calculate statistics
            total_documents = len(generation_metrics)
            total_time_saved = sum(m.time_saved_minutes or 0 for m in generation_metrics)
            avg_generation_time = sum(m.generation_time_ms for m in generation_metrics) // total_documents
            fastest_generation = min(m.generation_time_ms for m in generation_metrics)

            # Get productivity metrics
            productivity_metrics = db.query(UserProductivityMetric).filter(
                UserProductivityMetric.user_id == user_id,
                UserProductivityMetric.date >= start_date
            ).all()

            total_time_spent = sum(m.time_spent_minutes for m in productivity_metrics)

            # Calculate efficiency score (0-100)
            efficiency_score = min(100, (total_time_saved / max(total_time_spent, 1)) * 10)

            return {
                "success": True,
                "period_days": days,
                "stats": {
                    "documents_created": total_documents,
                    "total_time_saved_minutes": round(total_time_saved, 1),
                    "total_time_saved_hours": round(total_time_saved / 60, 1),
                    "average_generation_time_ms": avg_generation_time,
                    "average_generation_time_seconds": round(avg_generation_time / 1000, 1),
                    "fastest_generation_ms": fastest_generation,
                    "fastest_generation_seconds": round(fastest_generation / 1000, 1),
                    "efficiency_score": round(efficiency_score, 1),
                    "documents_per_day": round(total_documents / max(days, 1), 1),
                    "time_saved_per_document": round(total_time_saved / max(total_documents, 1), 1)
                },
                "recent_generations": [
                    {
                        "date": m.created_at.isoformat(),
                        "generation_time_ms": m.generation_time_ms,
                        "time_saved_minutes": m.time_saved_minutes,
                        "template_id": m.template_id
                    } for m in generation_metrics[-10:]  # Last 10 generations
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get user performance stats: {e}")
            raise

    @staticmethod
    def get_system_performance_stats(
        db: Session,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get system-wide performance statistics"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            # Get all generation metrics
            all_metrics = db.query(DocumentGenerationMetric).filter(
                DocumentGenerationMetric.created_at >= start_date
            ).all()

            if not all_metrics:
                return {
                    "success": True,
                    "period_days": days,
                    "stats": {
                        "total_documents": 0,
                        "average_generation_time_ms": 0,
                        "total_time_saved_hours": 0,
                        "active_users": 0
                    }
                }

            # Calculate system stats
            total_documents = len(all_metrics)
            avg_generation_time = sum(m.generation_time_ms for m in all_metrics) // total_documents
            total_time_saved = sum(m.time_saved_minutes or 0 for m in all_metrics)
            active_users = len(set(m.user_id for m in all_metrics if m.user_id))

            # Success rate
            successful_generations = len([m for m in all_metrics if m.generation_success])
            success_rate = (successful_generations / total_documents) * 100

            # Peak performance times
            hourly_stats = {}
            for metric in all_metrics:
                hour = metric.created_at.hour
                if hour not in hourly_stats:
                    hourly_stats[hour] = []
                hourly_stats[hour].append(metric.generation_time_ms)

            peak_hour = max(hourly_stats.keys(), key=lambda h: len(hourly_stats[h])) if hourly_stats else 0

            return {
                "success": True,
                "period_days": days,
                "stats": {
                    "total_documents": total_documents,
                    "average_generation_time_ms": avg_generation_time,
                    "average_generation_time_seconds": round(avg_generation_time / 1000, 1),
                    "total_time_saved_minutes": round(total_time_saved, 1),
                    "total_time_saved_hours": round(total_time_saved / 60, 1),
                    "active_users": active_users,
                    "success_rate_percentage": round(success_rate, 1),
                    "documents_per_day": round(total_documents / max(days, 1), 1),
                    "peak_hour": peak_hour,
                    "fastest_generation_ms": min(m.generation_time_ms for m in all_metrics),
                    "slowest_generation_ms": max(m.generation_time_ms for m in all_metrics)
                },
                "daily_breakdown": PerformanceTrackingService._get_daily_breakdown(all_metrics, days)
            }

        except Exception as e:
            logger.error(f"Failed to get system performance stats: {e}")
            raise

    @staticmethod
    def get_template_performance_stats(
        db: Session,
        template_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get performance statistics for a specific template"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            metrics = db.query(DocumentGenerationMetric).filter(
                DocumentGenerationMetric.template_id == template_id,
                DocumentGenerationMetric.created_at >= start_date
            ).all()

            if not metrics:
                return {
                    "success": True,
                    "template_id": template_id,
                    "stats": {
                        "usage_count": 0,
                        "average_generation_time_ms": 0,
                        "total_time_saved_minutes": 0
                    }
                }

            usage_count = len(metrics)
            avg_generation_time = sum(m.generation_time_ms for m in metrics) // usage_count
            total_time_saved = sum(m.time_saved_minutes or 0 for m in metrics)
            unique_users = len(set(m.user_id for m in metrics if m.user_id))

            return {
                "success": True,
                "template_id": template_id,
                "period_days": days,
                "stats": {
                    "usage_count": usage_count,
                    "unique_users": unique_users,
                    "average_generation_time_ms": avg_generation_time,
                    "average_generation_time_seconds": round(avg_generation_time / 1000, 1),
                    "total_time_saved_minutes": round(total_time_saved, 1),
                    "average_time_saved_per_use": round(total_time_saved / usage_count, 1),
                    "popularity_rank": PerformanceTrackingService._get_template_popularity_rank(
                        db, template_id, start_date
                    )
                }
            }

        except Exception as e:
            logger.error(f"Failed to get template performance stats: {e}")
            raise

    @staticmethod
    def _estimate_manual_time(template_id: int, placeholder_count: int, db: Session) -> float:
        """Estimate how long it would take to create document manually"""
        try:
            # Get template info for better estimation
            from app.models.template import Template
            template = db.query(Template).filter(Template.id == template_id).first()

            # Base time estimates (in minutes)
            base_times = {
                "letter": 15,
                "invoice": 20,
                "contract": 45,
                "certificate": 10,
                "report": 60,
                "form": 25
            }

            # Determine document type from template name
            template_name = template.name.lower() if template else "document"

            base_time = 30  # Default
            for doc_type, time_estimate in base_times.items():
                if doc_type in template_name:
                    base_time = time_estimate
                    break

            # Add time based on complexity (placeholder count)
            complexity_time = placeholder_count * 2  # 2 minutes per placeholder

            # Add formatting and review time
            formatting_time = base_time * 0.3  # 30% of base time for formatting

            total_time = base_time + complexity_time + formatting_time

            return max(5, total_time)  # Minimum 5 minutes

        except Exception:
            # Fallback estimation
            return max(15, placeholder_count * 3)

    @staticmethod
    def _update_user_productivity_metrics(
        db: Session,
        user_id: int,
        generation_time_ms: int,
        time_saved_minutes: float,
        success: bool
    ):
        """Update user productivity metrics for today"""
        try:
            today = datetime.utcnow().date()

            # Get or create today's metric record
            metric = db.query(UserProductivityMetric).filter(
                UserProductivityMetric.user_id == user_id,
                func.date(UserProductivityMetric.date) == today
            ).first()

            if not metric:
                metric = UserProductivityMetric(
                    user_id=user_id,
                    date=datetime.combine(today, datetime.min.time())
                )
                db.add(metric)

            # Update metrics
            metric.documents_created += 1
            metric.time_saved_minutes += time_saved_minutes
            metric.time_spent_minutes += generation_time_ms / 60000  # Convert to minutes

            # Update average generation time
            if metric.average_generation_time_ms:
                metric.average_generation_time_ms = int(
                    (metric.average_generation_time_ms + generation_time_ms) / 2
                )
            else:
                metric.average_generation_time_ms = generation_time_ms

            # Update success rate
            if success:
                metric.success_rate_percentage = min(100, metric.success_rate_percentage + 1)
            else:
                metric.success_rate_percentage = max(0, metric.success_rate_percentage - 5)

            metric.updated_at = datetime.utcnow()
            db.commit()

        except Exception as e:
            logger.error(f"Failed to update user productivity metrics: {e}")

    @staticmethod
    def _update_system_metrics(
        db: Session,
        generation_time_ms: int,
        time_saved_minutes: float,
        success: bool
    ):
        """Update system-wide metrics"""
        try:
            today = datetime.utcnow().date()

            # Get or create today's system metric record
            metric = db.query(SystemPerformanceMetric).filter(
                func.date(SystemPerformanceMetric.date) == today,
                SystemPerformanceMetric.hour.is_(None)  # Daily record, not hourly
            ).first()

            if not metric:
                metric = SystemPerformanceMetric(
                    date=datetime.combine(today, datetime.min.time())
                )
                db.add(metric)

            # Update metrics
            metric.total_documents_generated += 1
            metric.total_time_saved_minutes += time_saved_minutes

            # Update generation times
            if metric.average_generation_time_ms:
                metric.average_generation_time_ms = int(
                    (metric.average_generation_time_ms + generation_time_ms) / 2
                )
            else:
                metric.average_generation_time_ms = generation_time_ms

            if not metric.fastest_generation_time_ms or generation_time_ms < metric.fastest_generation_time_ms:
                metric.fastest_generation_time_ms = generation_time_ms

            if not metric.peak_generation_time_ms or generation_time_ms > metric.peak_generation_time_ms:
                metric.peak_generation_time_ms = generation_time_ms

            # Update error count
            if not success:
                metric.generation_errors += 1

            db.commit()

        except Exception as e:
            logger.error(f"Failed to update system metrics: {e}")

    @staticmethod
    def _generate_user_message(generation_time_ms: int, time_saved_minutes: float) -> str:
        """Generate user-friendly message about performance"""
        generation_seconds = generation_time_ms / 1000

        if generation_seconds < 5:
            speed_msg = f"Document created in {generation_seconds:.1f} seconds - Lightning fast! ⚡"
        elif generation_seconds < 10:
            speed_msg = f"Document created in {generation_seconds:.1f} seconds - Super quick! 🚀"
        else:
            speed_msg = f"Document created in {generation_seconds:.1f} seconds"

        if time_saved_minutes > 60:
            time_msg = f"You saved approximately {time_saved_minutes/60:.1f} hours! 🎉"
        elif time_saved_minutes > 10:
            time_msg = f"You saved approximately {time_saved_minutes:.0f} minutes! 👏"
        else:
            time_msg = f"You saved approximately {time_saved_minutes:.1f} minutes!"

        return f"{speed_msg} {time_msg}"

    @staticmethod
    def _get_daily_breakdown(metrics: List[DocumentGenerationMetric], days: int) -> List[Dict]:
        """Get daily breakdown of metrics"""
        daily_data = {}

        for metric in metrics:
            date_str = metric.created_at.date().isoformat()
            if date_str not in daily_data:
                daily_data[date_str] = {
                    "date": date_str,
                    "documents": 0,
                    "total_time_ms": 0,
                    "time_saved_minutes": 0
                }

            daily_data[date_str]["documents"] += 1
            daily_data[date_str]["total_time_ms"] += metric.generation_time_ms
            daily_data[date_str]["time_saved_minutes"] += metric.time_saved_minutes or 0

        # Calculate averages
        for data in daily_data.values():
            if data["documents"] > 0:
                data["avg_time_ms"] = data["total_time_ms"] // data["documents"]
                data["avg_time_seconds"] = round(data["avg_time_ms"] / 1000, 1)

        return sorted(daily_data.values(), key=lambda x: x["date"])

    @staticmethod
    def _get_template_popularity_rank(db: Session, template_id: int, start_date: datetime) -> int:
        """Get popularity rank of template"""
        try:
            # Get usage count for all templates
            template_usage = db.query(
                DocumentGenerationMetric.template_id,
                func.count(DocumentGenerationMetric.id).label('usage_count')
            ).filter(
                DocumentGenerationMetric.created_at >= start_date
            ).group_by(
                DocumentGenerationMetric.template_id
            ).order_by(
                func.count(DocumentGenerationMetric.id).desc()
            ).all()

            # Find rank of current template
            for rank, (tid, count) in enumerate(template_usage, 1):
                if tid == template_id:
                    return rank

            return len(template_usage) + 1  # Not found, lowest rank

        except Exception:
            return 0
